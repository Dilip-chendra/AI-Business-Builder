"""Business strategy agent."""
from __future__ import annotations

from app.agents.base_agent import AgentDecision, AgentInput, AgentResult, BaseAgent
from app.services.ai_service import AIService


class StrategyAgent(BaseAgent):
    agent_type = "strategy"

    async def analyze(self, input_data: AgentInput) -> AgentResult:
        business = input_data.business_data
        analytics = input_data.analytics_data
        products = input_data.products
        decisions: list[AgentDecision] = []
        insights: list[str] = []

        if not products:
            decisions.append(
                AgentDecision(
                    action_type="suggest_create_product",
                    summary="No products exist; create a monetizable starter offer",
                    payload={"niche": business.get("niche"), "audience": business.get("target_audience")},
                    confidence=0.99,
                    auto_apply=False,
                )
            )
        elif len(products) == 1:
            decisions.append(
                AgentDecision(
                    action_type="suggest_product_expansion",
                    summary="One product exists; add a second tier or bundle",
                    payload={"existing_product": products[0].get("name")},
                    confidence=0.65,
                    auto_apply=False,
                )
            )

        ai_advice = await self._ai_strategy(business, analytics, products)
        insights.append(str(ai_advice.get("insight", ai_advice.get("summary", ""))))
        decisions.append(
            AgentDecision(
                action_type="ai_strategic_advice",
                summary=ai_advice.get("summary", "AI strategic recommendation"),
                payload=ai_advice,
                confidence=0.75,
                auto_apply=False,
            )
        )
        return AgentResult(agent_type=self.agent_type, decisions=decisions, insights=[i for i in insights if i])

    async def _ai_strategy(self, business: dict, analytics: dict, products: list[dict]) -> dict:
        prompt = (
            "You are a startup strategy advisor. Return ONLY valid JSON with keys "
            "summary, insight, action, priority. Be specific and actionable.\n\n"
            f"Business JSON:\n{business}\n"
            f"Analytics JSON:\n{analytics}\n"
            f"Products JSON:\n{products}"
        )
        return await AIService().generate_json(prompt)
