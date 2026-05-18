"""Analytics interpretation agent."""
from __future__ import annotations

from app.agents.base_agent import AgentDecision, AgentInput, AgentResult, BaseAgent
from app.services.ai_service import AIService


class AnalyticsAgent(BaseAgent):
    agent_type = "analytics"

    async def analyze(self, input_data: AgentInput) -> AgentResult:
        analytics = input_data.analytics_data
        visitors = analytics.get("visitors", 0)
        conversions = analytics.get("conversions", 0)
        conversion_rate = analytics.get("conversion_rate", 0.0)
        decisions: list[AgentDecision] = []

        if conversion_rate < 0.01 and visitors > 0:
            decisions.append(
                AgentDecision(
                    action_type="flag_low_conversion",
                    summary="Conversion rate is below 1%; landing page or offer needs review",
                    payload={"conversion_rate": conversion_rate, "visitors": visitors},
                    confidence=0.95,
                    auto_apply=False,
                )
            )
        if visitors > 100 and conversions == 0:
            decisions.append(
                AgentDecision(
                    action_type="flag_zero_conversions",
                    summary="100+ visitors with zero conversions",
                    payload={"visitors": visitors, "conversions": conversions},
                    confidence=0.9,
                    auto_apply=False,
                )
            )

        insight = await self._ai_interpret(analytics, input_data.business_data)
        return AgentResult(agent_type=self.agent_type, decisions=decisions, insights=[insight])

    async def _ai_interpret(self, analytics: dict, business: dict) -> str:
        prompt = (
            "You are a concise analytics expert. Return ONLY valid JSON with key insight.\n"
            "The insight must be one sentence and identify the highest-leverage next action.\n\n"
            f"Business JSON:\n{business}\n"
            f"Analytics JSON:\n{analytics}"
        )
        parsed = await AIService().generate_json(prompt)
        return str(parsed["insight"])
