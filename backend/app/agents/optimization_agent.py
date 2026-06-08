"""Optimization agent for autonomous landing page improvements."""
from __future__ import annotations

import logging

from app.agents.base_agent import AgentDecision, AgentInput, AgentResult, BaseAgent
from app.models.business import Business
from app.services.ai_service import AIService

logger = logging.getLogger(__name__)


class OptimizationAgent(BaseAgent):
    agent_type = "optimization"

    async def analyze(self, input_data: AgentInput) -> AgentResult:
        business = input_data.business_data
        analytics = input_data.analytics_data
        visitors = analytics.get("visitors", 0)
        conversion_rate = analytics.get("conversion_rate", 0.0)

        if visitors < 5:
            return AgentResult(
                agent_type=self.agent_type,
                decisions=[],
                insights=["Not enough traffic for autonomous optimization yet."],
            )

        suggestions = await self._ai_optimize(business, analytics)
        decisions: list[AgentDecision] = []

        if suggestions.get("headline"):
            decisions.append(
                AgentDecision(
                    action_type="update_headline",
                    summary=f"Replace headline with: '{suggestions['headline']}'",
                    payload={
                        "field": "headline",
                        "old_value": business.get("headline"),
                        "new_value": suggestions["headline"],
                        "reason": suggestions.get("reason", f"Conversion rate is {conversion_rate:.1%}"),
                    },
                    confidence=0.75,
                    auto_apply=True,
                )
            )
        if suggestions.get("cta_text"):
            decisions.append(
                AgentDecision(
                    action_type="update_cta",
                    summary=f"Replace CTA with: '{suggestions['cta_text']}'",
                    payload={
                        "field": "cta_text",
                        "old_value": business.get("cta_text"),
                        "new_value": suggestions["cta_text"],
                        "reason": suggestions.get("reason", f"Conversion rate is {conversion_rate:.1%}"),
                    },
                    confidence=0.7,
                    auto_apply=True,
                )
            )

        return AgentResult(
            agent_type=self.agent_type,
            decisions=decisions,
            insights=[str(suggestions.get("insight", "AI optimization completed."))],
        )

    async def _execute(self, decision: AgentDecision, input_data: AgentInput) -> None:
        if decision.action_type not in ("update_headline", "update_cta"):
            return
        field = decision.payload.get("field")
        new_value = decision.payload.get("new_value")
        if not field or not new_value:
            return
        business = await self.db.get(Business, input_data.business_id)
        if not business:
            return
        setattr(business, field, new_value)
        await self.db.commit()
        logger.info("OptimizationAgent applied field=%s business_id=%s", field, input_data.business_id)

    async def _ai_optimize(self, business: dict, analytics: dict) -> dict:
        prompt = (
            "You are a CRO expert. Return ONLY valid JSON with keys headline, cta_text, reason, insight. "
            "Keep headline and cta_text under 80 characters.\n\n"
            f"Business JSON:\n{business}\n"
            f"Analytics JSON:\n{analytics}"
        )
        return await AIService().generate_json(prompt)
