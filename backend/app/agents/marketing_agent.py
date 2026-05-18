"""Marketing agent for channel prioritization and AI-generated campaign assets."""
from __future__ import annotations

from app.agents.base_agent import AgentDecision, AgentInput, AgentResult, BaseAgent
from app.services.ai_service import AIService


class MarketingAgent(BaseAgent):
    agent_type = "marketing"

    async def analyze(self, input_data: AgentInput) -> AgentResult:
        business = input_data.business_data
        analytics = input_data.analytics_data
        visitors = analytics.get("visitors", 0)

        if visitors < 50:
            channel = "social_media"
            insight = "Traffic is low; prioritize fast social distribution."
        elif visitors < 200:
            channel = "seo_blog"
            insight = "Traffic is growing; publish search content that compounds."
        else:
            channel = "email_campaign"
            insight = "Traffic is established; convert existing visitors through email."

        content = await self._generate_content(business, channel)
        ad_copy = await self._generate_ad_copy(business)

        return AgentResult(
            agent_type=self.agent_type,
            insights=[insight],
            decisions=[
                AgentDecision(
                    action_type=f"generate_{channel}_content",
                    summary=f"Generated {channel.replace('_', ' ')} content for {business.get('name')}",
                    payload={"channel": channel, "content": content},
                    confidence=0.8,
                    auto_apply=False,
                ),
                AgentDecision(
                    action_type="ad_copy",
                    summary="Generated short-form ad copy for paid channels",
                    payload=ad_copy,
                    confidence=0.75,
                    auto_apply=False,
                ),
            ],
        )

    async def _generate_content(self, business: dict, channel: str) -> dict:
        channel_instructions = {
            "social_media": "Write 3 short social posts. Return JSON with key posts as an array.",
            "seo_blog": "Write an SEO outline. Return JSON with title, meta_description, sections.",
            "email_campaign": "Write an email campaign. Return JSON with subject, preview, body.",
        }
        prompt = (
            "You are an expert digital marketer. Return ONLY valid JSON.\n"
            f"{channel_instructions[channel]}\n\n"
            f"Business JSON:\n{business}"
        )
        return await AIService().generate_json(prompt)

    async def _generate_ad_copy(self, business: dict) -> dict:
        prompt = (
            "Create short paid-channel ad copy. Return ONLY valid JSON with keys headline, body, cta.\n"
            f"Business JSON:\n{business}"
        )
        return await AIService().generate_json(prompt)
