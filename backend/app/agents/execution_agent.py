"""Execution Agent — carries out decisions from other agents.

This agent is the actuator of the system. It receives decisions from the
Strategy, Marketing, and Optimization agents and executes them:
- Updates database records
- Creates new products
- Modifies landing page fields
- Triggers email campaigns
- Logs every action taken
"""
from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base_agent import AgentDecision, AgentInput, AgentResult, BaseAgent
from app.models.business import Business
from app.models.product import Product

logger = logging.getLogger(__name__)


class ExecutionAgent(BaseAgent):
    """Executes decisions produced by other agents."""

    agent_type = "execution"

    async def analyze(self, input_data: AgentInput) -> AgentResult:
        """The execution agent doesn't produce its own decisions — it executes others'."""
        return AgentResult(
            agent_type=self.agent_type,
            decisions=[],
            insights=["Execution agent ready. Pass decisions via execute_decisions()."],
        )

    async def execute_decisions(
        self,
        decisions: list[AgentDecision],
        input_data: AgentInput,
    ) -> AgentResult:
        """Execute a list of decisions from other agents."""
        applied: list[AgentDecision] = []
        failed: list[str] = []

        for decision in decisions:
            if not decision.auto_apply:
                continue
            try:
                await self._dispatch(decision, input_data)
                applied.append(decision)
                await self._log(input_data.business_id, decision, applied=True)
                logger.info(
                    "ExecutionAgent applied %s  business_id=%s",
                    decision.action_type,
                    input_data.business_id,
                )
            except Exception as exc:
                failed.append(f"{decision.action_type}: {exc}")
                await self._log(input_data.business_id, decision, applied=False, error=str(exc))
                logger.error(
                    "ExecutionAgent failed %s: %s",
                    decision.action_type,
                    exc,
                )

        insights = [f"Applied {len(applied)} decisions."]
        if failed:
            insights.append(f"Failed: {'; '.join(failed)}")

        return AgentResult(
            agent_type=self.agent_type,
            decisions=applied,
            insights=insights,
            applied_count=len(applied),
        )

    async def _dispatch(self, decision: AgentDecision, input_data: AgentInput) -> None:
        """Route a decision to the correct handler."""
        handlers = {
            "update_headline": self._update_business_field,
            "update_cta": self._update_business_field,
            "update_subheading": self._update_business_field,
            "create_product": self._create_product,
        }
        handler = handlers.get(decision.action_type)
        if handler:
            await handler(decision, input_data)
        else:
            logger.debug("No handler for action_type=%s — logged only", decision.action_type)

    async def _update_business_field(
        self, decision: AgentDecision, input_data: AgentInput
    ) -> None:
        field = decision.payload.get("field")
        new_value = decision.payload.get("new_value")
        if not field or not new_value:
            raise ValueError(f"Missing field/new_value in payload: {decision.payload}")

        business = await self.db.get(Business, input_data.business_id)
        if not business:
            raise ValueError(f"Business {input_data.business_id} not found")

        old_value = getattr(business, field, None)
        setattr(business, field, new_value)
        await self.db.commit()
        logger.info(
            "Updated business.%s  '%s' → '%s'  business_id=%s",
            field,
            old_value,
            new_value,
            input_data.business_id,
        )

    async def _create_product(
        self, decision: AgentDecision, input_data: AgentInput
    ) -> None:
        payload = decision.payload
        product = Product(
            business_id=input_data.business_id,
            name=payload.get("name", "New Product"),
            description=payload.get("description", "AI-suggested product"),
            price=Decimal(str(payload.get("price", "29.00"))),
            currency=payload.get("currency", "usd"),
            category=payload.get("category", "digital"),
        )
        self.db.add(product)
        await self.db.commit()
        logger.info(
            "ExecutionAgent created product '%s'  business_id=%s",
            product.name,
            input_data.business_id,
        )
