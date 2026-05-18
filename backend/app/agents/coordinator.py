"""Multi-Agent Coordinator.

Orchestrates the full agent pipeline:

    Analytics Agent → Strategy Agent → Marketing Agent
                                     ↓
                            Optimization Agent
                                     ↓
                            Execution Agent (applies auto_apply decisions)

Each agent's output feeds into the next, creating a self-improving loop.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.analytics_agent import AnalyticsAgent
from app.agents.base_agent import AgentDecision, AgentInput, AgentResult
from app.agents.execution_agent import ExecutionAgent
from app.agents.marketing_agent import MarketingAgent
from app.agents.optimization_agent import OptimizationAgent
from app.agents.strategy_agent import StrategyAgent
from app.models.agent import AgentLog
from app.services.analytics_service import AnalyticsService
from app.services.business_service import BusinessService
from app.services.product_service import ProductService

logger = logging.getLogger(__name__)


class AgentCoordinator:
    """Runs all agents in sequence and coordinates their outputs."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run_full_pipeline(
        self,
        business_id: UUID,
        apply_decisions: bool = False,
    ) -> dict:
        """Execute the complete agent pipeline for a business.

        Args:
            business_id:      The business to analyse and optimise.
            apply_decisions:  If True, auto_apply decisions are executed.

        Returns:
            A summary dict with all agent results and a combined insight list.
        """
        logger.info(
            "AgentCoordinator starting pipeline  business_id=%s  apply=%s",
            business_id,
            apply_decisions,
        )

        # ── 1. Gather context ─────────────────────────────────────────────────
        business = await BusinessService(self.db).get(business_id)
        if not business:
            return {"error": f"Business {business_id} not found"}

        analytics_summary = await AnalyticsService(self.db).summary(business_id)
        products = await ProductService(self.db).list(business_id)

        input_data = AgentInput(
            business_id=business_id,
            business_data={
                "id": str(business.id),
                "name": business.name,
                "niche": business.niche,
                "description": business.description,
                "target_audience": business.target_audience,
                "monetization_model": business.monetization_model,
                "brand_tone": business.brand_tone,
                "headline": business.headline,
                "subheading": business.subheading,
                "cta_text": business.cta_text,
            },
            analytics_data={
                "visitors": analytics_summary.visitors,
                "clicks": analytics_summary.clicks,
                "conversions": analytics_summary.conversions,
                "revenue_cents": analytics_summary.revenue_cents,
                "conversion_rate": analytics_summary.conversion_rate,
            },
            products=[
                {
                    "id": str(p.id),
                    "name": p.name,
                    "price": str(p.price),
                    "category": p.category,
                }
                for p in products
            ],
        )

        # ── 2. Run agents in sequence ─────────────────────────────────────────
        analytics_result = await AnalyticsAgent(self.db).run(input_data, apply=False)
        strategy_result = await StrategyAgent(self.db).run(input_data, apply=False)
        marketing_result = await MarketingAgent(self.db).run(input_data, apply=False)
        optimization_result = await OptimizationAgent(self.db).run(
            input_data, apply=apply_decisions
        )

        # ── 3. Collect all auto_apply decisions and pass to Execution Agent ───
        all_decisions: list[AgentDecision] = (
            analytics_result.decisions
            + strategy_result.decisions
            + marketing_result.decisions
            + optimization_result.decisions
        )

        execution_result = AgentResult(agent_type="execution", decisions=[], insights=[])
        if apply_decisions:
            execution_result = await ExecutionAgent(self.db).execute_decisions(
                all_decisions, input_data
            )

        # ── 4. Log a coordinator-level summary ────────────────────────────────
        total_decisions = len(all_decisions)
        total_applied = (
            optimization_result.applied_count + execution_result.applied_count
        )
        coordinator_log = AgentLog(
            business_id=business_id,
            agent_type="coordinator",
            log_type="analysis",
            summary=(
                f"Pipeline complete: {total_decisions} decisions, "
                f"{total_applied} applied"
            ),
            payload={
                "analytics_insights": analytics_result.insights,
                "strategy_insights": strategy_result.insights,
                "marketing_insights": marketing_result.insights,
                "optimization_insights": optimization_result.insights,
                "total_decisions": total_decisions,
                "total_applied": total_applied,
            },
            applied=total_applied > 0,
        )
        self.db.add(coordinator_log)
        # Single commit for all agent logs created during this pipeline run
        await self.db.commit()

        logger.info(
            "AgentCoordinator done  business_id=%s  decisions=%d  applied=%d",
            business_id,
            total_decisions,
            total_applied,
        )

        return {
            "business_id": str(business_id),
            "apply_decisions": apply_decisions,
            "analytics": {
                "insights": analytics_result.insights,
                "decisions": _serialize_decisions(analytics_result.decisions),
            },
            "strategy": {
                "insights": strategy_result.insights,
                "decisions": _serialize_decisions(strategy_result.decisions),
            },
            "marketing": {
                "insights": marketing_result.insights,
                "decisions": _serialize_decisions(marketing_result.decisions),
            },
            "optimization": {
                "insights": optimization_result.insights,
                "decisions": _serialize_decisions(optimization_result.decisions),
                "applied_count": optimization_result.applied_count,
            },
            "execution": {
                "applied_count": execution_result.applied_count,
                "insights": execution_result.insights,
            },
            "summary": {
                "total_decisions": total_decisions,
                "total_applied": total_applied,
                "all_insights": (
                    analytics_result.insights
                    + strategy_result.insights
                    + marketing_result.insights
                    + optimization_result.insights
                ),
            },
        }


def _serialize_decisions(decisions: list[AgentDecision]) -> list[dict]:
    return [
        {
            "action_type": d.action_type,
            "summary": d.summary,
            "confidence": d.confidence,
            "auto_apply": d.auto_apply,
            "payload": d.payload,
        }
        for d in decisions
    ]
