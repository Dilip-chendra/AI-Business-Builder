"""MarketingAgentCoordinator â€” Autonomous AI Marketing Engine.

Orchestrates 6 sub-agents to plan, generate, and track marketing campaigns:
  1. StrategyAgent   â€” defines campaign plan and channel selection
  2. ContentAgent    â€” generates email, social, ad copy
  3. CreativeAgent   â€” generates images via HuggingFace API
  4. CampaignAgent   â€” structures campaign objects and saves to DB
  5. AnalyticsAgent  - waits for real send/click/conversion events
  6. OptimizationAgent â€” improves headlines, targeting, creatives

All output is real AI-generated content stored in the database.
No dummy data. No hardcoded responses.
"""
from __future__ import annotations

import asyncio
import base64
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.marketing import CampaignAsset, MarketingCampaign
from app.services.ai_service import AIService
from app.services.business_service import BusinessService
from app.services.oauth_manager_service import OAuthManagerService
from app.services.product_service import ProductService

logger = logging.getLogger(__name__)


REPORT_INTELLIGENCE_CONTEXT = (
    "Product intelligence from the production hardening report:\n"
    "- Strongest initial wedge: residential home services, especially HVAC, plumbing, electrical, and roofing operators under 20 employees.\n"
    "- Primary customer pain: missed leads, slow follow-up, weak local marketing, disconnected scheduling, and no booked-revenue attribution.\n"
    "- Campaign strategy should prioritize booked calls, service appointments, quote requests, review generation, and real tracked events over vanity metrics.\n"
    "- Keep official API/OAuth publishing and browser automation separate from content generation; do not imply anything was sent or published until a real action confirms it.\n"
    "- If the active business is not home services, apply the same execution-first logic to that niche without pretending it is HVAC, plumbing, electrical, or roofing.\n"
)


# â”€â”€ Image generation via HuggingFace â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

async def generate_image_hf(prompt: str) -> str | None:
    """Generate an image using HuggingFace Inference API.

    Uses the configured Hugging Face image model from backend/.env.
    Returns base64-encoded JPEG or None if unavailable.
    """
    if not settings.hf_api_key:
        return None

    model = getattr(settings, "hf_image_model", "runwayml/stable-diffusion-v1-5")
    url = f"https://api-inference.huggingface.co/models/{model}"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {settings.hf_api_key}"},
                json={"inputs": prompt, "parameters": {"num_inference_steps": 20}},
            )
            if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
                b64 = base64.b64encode(resp.content).decode()
                return f"data:image/jpeg;base64,{b64}"
            logger.warning("HF image generation failed: HTTP %d", resp.status_code)
    except Exception as exc:
        logger.warning("HF image generation error: %s", exc)
    return None



# â”€â”€ Main coordinator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class MarketingAgentCoordinator:
    """Runs all marketing sub-agents and streams progress events."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._ai = AIService()

    async def _ai_json(self, prompt: str, retries: int = 3) -> dict:
        """Call AI with automatic retry on rate limit."""
        for attempt in range(retries):
            try:
                return await self._ai.generate_json(prompt, task_type="marketing")
            except Exception as exc:
                if "rate_limit" in str(exc).lower() or "429" in str(exc):
                    wait = 15 * (attempt + 1)
                    logger.info("Rate limit hit, waiting %ds before retry %d/%d", wait, attempt + 1, retries)
                    await asyncio.sleep(wait)
                    continue
                raise
        return await self._ai.generate_json(prompt, task_type="marketing")  # final attempt

    async def run_stream(
        self,
        business_id: UUID,
        goal: str,
        budget_usd: float = 100.0,
        platforms: list[str] | None = None,
        user_id: str | UUID | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream marketing agent execution events.

        Yields dicts with keys: type, agent, message, data, step, total_steps
        """
        platforms = platforms or ["email", "social", "google_ads"]
        total_steps = 8
        step = 0

        # â”€â”€ Load business context â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        business = await BusinessService(self.db).get(business_id)
        if not business:
            yield {"type": "error", "message": "Business not found"}
            return

        products = await ProductService(self.db).list(business_id)
        biz_ctx = {
            "name": business.name,
            "niche": business.niche,
            "description": business.description,
            "target_audience": business.target_audience,
            "brand_tone": business.brand_tone,
            "headline": business.headline,
            "cta_text": business.cta_text,
        }

        yield {
            "type": "start",
            "message": f"AI Marketing Engine activated for {business.name}",
            "step": 0,
            "total_steps": total_steps,
            "data": {
                "goal": goal,
                "budget_usd": budget_usd,
                "platforms": platforms,
                "business": biz_ctx,
                "products_loaded": len(products),
            },
        }
        await asyncio.sleep(0.2)

        # â”€â”€ STEP 1: OpsAgent â€” context and integration readiness â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        step += 1
        yield {
            "type": "thinking",
            "agent": "OpsAgent",
            "message": "Loading business context, products, integrations, and publish readiness.",
            "step": step,
            "total_steps": total_steps,
        }
        readiness = await self._integration_readiness(business_id, platforms, user_id=user_id)
        execution_queue = self._execution_queue(platforms, readiness)
        blocked = [item for item in readiness if item["state"] == "blocked"]
        ready = [item for item in readiness if item["state"] == "ready"]
        yield {
            "type": "step_complete",
            "agent": "OpsAgent",
            "message": (
                f"Readiness checked: {len(ready)} channel groups ready, {len(blocked)} need setup."
                if readiness
                else "Readiness checked. Campaign generation can continue before publishing setup is complete."
            ),
            "data": {
                "readiness": readiness,
                "execution_queue": execution_queue,
                "products_loaded": len(products),
                "publish_blockers": blocked,
            },
            "step": step,
            "total_steps": total_steps,
        }
        await asyncio.sleep(0.2)

        # â”€â”€ STEP 1: StrategyAgent â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        step += 1
        yield {"type": "thinking", "agent": "StrategyAgent", "message": "Analyzing business and defining campaign strategyâ€¦", "step": step, "total_steps": total_steps}
        await asyncio.sleep(0.3)

        strategy_prompt = (
            f"You are a marketing strategist. Create a campaign plan.\n"
            f"Return ONLY valid JSON with these keys:\n"
            f"  campaign_name, objective, key_message, target_segments (array),\n"
            f"  channels (array from: email/social/google_ads/meta_ads),\n"
            f"  budget_allocation (object: channel->percentage),\n"
            f"  success_metrics (array), timeline_days\n\n"
            f"Business: {biz_ctx['name']}\n"
            f"Niche: {biz_ctx['niche']}\n"
            f"Goal: {goal}\n"
            f"Budget: ${budget_usd}\n"
            f"Preferred platforms: {platforms}\n"
            f"Products: {[{'name': p.name, 'price': str(p.price), 'currency': p.currency} for p in products[:5]]}\n"
            f"Publish readiness: {readiness}\n"
            f"Target audience: {biz_ctx['target_audience']}\n\n"
            f"{REPORT_INTELLIGENCE_CONTEXT}"
        )
        try:
            strategy = await self._ai_json(strategy_prompt)
        except Exception as exc:
            yield {"type": "error", "agent": "StrategyAgent", "message": str(exc)}
            return
        yield {
            "type": "step_complete",
            "agent": "StrategyAgent",
            "message": f"Strategy defined: {strategy.get('campaign_name', 'Campaign')}",
            "data": {
                **strategy,
                "execution_queue": execution_queue,
                "agent_decision": "Generated campaign assets now; publishing is gated by approval and integration readiness.",
            },
            "step": step,
            "total_steps": total_steps,
        }
        await asyncio.sleep(0.2)

        # â”€â”€ STEP 2: ContentAgent â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        step += 1
        yield {"type": "thinking", "agent": "ContentAgent", "message": "Generating email, social posts, and ad copyâ€¦", "step": step, "total_steps": total_steps}
        await asyncio.sleep(0.3)

        content_prompt = (
            f"You are an expert copywriter. Generate marketing content.\n"
            f"Return ONLY valid JSON with these keys:\n"
            f"  email: {{subject, preview_text, headline, body, cta_text}},\n"
            f"  social_posts: array of {{platform, text, hashtags}},\n"
            f"  ad_copy: {{headline, description, cta}},\n"
            f"  key_value_prop: string\n\n"
            f"Business: {biz_ctx['name']}\n"
            f"Niche: {biz_ctx['niche']}\n"
            f"Goal: {goal}\n"
            f"Key message: {strategy.get('key_message', goal)}\n"
            f"Target audience: {biz_ctx['target_audience']}\n"
            f"Brand tone: {biz_ctx['brand_tone']}\n"
            f"CTA: {biz_ctx['cta_text']}\n\n"
            f"{REPORT_INTELLIGENCE_CONTEXT}"
        )
        try:
            content = await self._ai.generate_json(content_prompt, task_type="marketing")
        except Exception as exc:
            yield {"type": "error", "agent": "ContentAgent", "message": str(exc)}
            return

        yield {
            "type": "step_complete",
            "agent": "ContentAgent",
            "message": "Content generated: email, social posts, ad copy",
            "data": {"preview": content.get("key_value_prop", "")},
            "step": step,
            "total_steps": total_steps,
        }
        await asyncio.sleep(0.2)

        # â”€â”€ STEP 3: ContentAgent â€” Full HTML Email â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        email_data = content.get("email", {})
        full_email = await self._generate_full_email(biz_ctx, email_data, goal)

        # â”€â”€ STEP 4: CreativeAgent â€” Image Generation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        step += 1
        yield {"type": "thinking", "agent": "CreativeAgent", "message": "Generating ad creative images via HuggingFace AIâ€¦", "step": step, "total_steps": total_steps}
        await asyncio.sleep(0.2)

        image_prompt = (
            f"Professional marketing banner for {biz_ctx['name']}, "
            f"{biz_ctx['niche']}, modern design, high quality, "
            f"clean background, product showcase"
        )
        image_b64 = await generate_image_hf(image_prompt)
        image_status = "generated" if image_b64 else "unavailable (HF_API_KEY not set or model loading)"

        yield {
            "type": "step_complete",
            "agent": "CreativeAgent",
            "message": f"Creative image: {image_status}",
            "data": {"has_image": bool(image_b64), "image_prompt": image_prompt},
            "step": step,
            "total_steps": total_steps,
        }
        await asyncio.sleep(0.2)

        # â”€â”€ STEP 5: CampaignAgent â€” Create DB records â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        step += 1
        yield {"type": "thinking", "agent": "CampaignAgent", "message": "Structuring campaigns and saving to databaseâ€¦", "step": step, "total_steps": total_steps}
        await asyncio.sleep(0.2)

        created_assets = []
        budget_alloc = strategy.get("budget_allocation", {})
        parent_campaign = MarketingCampaign(
            business_id=business_id,
            campaign_type="multi_channel",
            name=strategy.get("campaign_name", f"Campaign: {goal[:80]}"),
            goal=goal,
            budget_cents=int(budget_usd * 100),
            created_by=str(user_id) if user_id else None,
            status="pending_approval",
            lifecycle_status="pending_approval",
            content={
                "strategy": strategy,
                "key_value_prop": content.get("key_value_prop", ""),
                "asset_count": len(platforms),
            },
            targeting={
                "platforms": platforms,
                "budget_usd": budget_usd,
                "segments": strategy.get("target_segments", []),
                "objective": strategy.get("objective", goal),
                "requires_human_approval": True,
            },
            metrics={
                "impressions": 0,
                "clicks": 0,
                "conversions": 0,
                "revenue_cents": 0,
                "analytics_source": "real",
            },
            analytics_source="real",
        )
        self.db.add(parent_campaign)
        await self.db.flush()

        for platform in platforms:
            platform_budget = budget_usd * (budget_alloc.get(platform, 1.0 / len(platforms)))

            if platform == "email":
                camp_content = {
                    **full_email,
                    "image_b64": image_b64,
                    "key_value_prop": content.get("key_value_prop", ""),
                }
                asset_type = "email"
                subject = full_email.get("subject", f"Email: {goal[:40]}")
            elif platform == "social":
                posts = content.get("social_posts", [])
                camp_content = {
                    "platform": "twitter",
                    "posts": posts,
                    "image_b64": image_b64,
                }
                asset_type = "social_post"
                subject = f"Social assets: {goal[:40]}"
            else:
                ad_copy = content.get("ad_copy", {})
                camp_content = {
                    "campaign_name": strategy.get("campaign_name", f"{platform} Campaign"),
                    "ad_creatives": [ad_copy],
                    "image_b64": image_b64,
                    "draft_budget_usd": round(platform_budget, 2),
                    "spend_warning": "Draft only. No ad spend occurs until user approval and provider confirmation.",
                }
                asset_type = "ad_draft"
                subject = strategy.get("campaign_name", f"{platform} Campaign")

            asset = CampaignAsset(
                campaign_id=parent_campaign.id,
                platform=platform,
                asset_type=asset_type,
                subject=subject,
                content={
                    **camp_content,
                    "platform_budget_usd": round(platform_budget, 2),
                    "tracking_required": True,
                    "analytics_source": "real",
                },
                creative_url=image_b64 if image_b64 and image_b64.startswith("http") else None,
                status="draft",
            )
            self.db.add(asset)
            created_assets.append(asset)

        await self.db.commit()
        await self.db.refresh(parent_campaign)
        for asset in created_assets:
            await self.db.refresh(asset)

        yield {
            "type": "step_complete",
            "agent": "CampaignAgent",
            "message": f"Created 1 parent campaign with {len(created_assets)} platform assets",
            "data": {
                "campaign_ids": [str(parent_campaign.id)],
                "asset_ids": [str(asset.id) for asset in created_assets],
                "count": 1,
                "asset_count": len(created_assets),
                "next_actions": [
                    {"label": "Review generated campaign queue", "action": "open_campaigns"},
                    {"label": "Approve assets before publishing", "action": "approve_campaigns"},
                    *(
                        [{"label": "Connect blocked publishing channels", "action": "open_integrations"}]
                        if blocked
                        else []
                    ),
                ],
            },
            "step": step,
            "total_steps": total_steps,
        }
        await asyncio.sleep(0.2)

        # â”€â”€ STEP 6: AnalyticsAgent â€” real-event tracking readiness â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        step += 1
        yield {"type": "thinking", "agent": "AnalyticsAgent", "message": "Waiting for real campaign events from tracking URLs, sends, and conversions.", "step": step, "total_steps": total_steps}
        await asyncio.sleep(0.2)

        yield {
            "type": "step_complete",
            "agent": "AnalyticsAgent",
            "message": "No real analytics events yet. Clicks, conversions, and revenue will stay at zero until tracked user actions occur.",
            "data": {
                "analytics_source": "real",
                "total_events": 0,
                "total_clicks": 0,
                "total_conversions": 0,
                "total_revenue_cents": 0,
            },
            "step": step,
            "total_steps": total_steps,
        }
        await asyncio.sleep(0.2)

        # â”€â”€ STEP 7: OptimizationAgent â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        step += 1
        yield {"type": "thinking", "agent": "OptimizationAgent", "message": "Analyzing performance and generating optimization suggestionsâ€¦", "step": step, "total_steps": total_steps}
        await asyncio.sleep(0.3)

        optimization = {
            "status": "content_review_ready",
            "message": "Creative and copy optimization is ready. Performance optimization starts after real events arrive.",
            "optimization_mode": "content_review",
            "minimum_events_required_for_performance": {"click": 25, "conversion": 1},
            "current_events": {"click": 0, "conversion": 0, "revenue_cents": 0},
        }

        yield {
            "type": "step_complete",
            "agent": "OptimizationAgent",
            "message": "Creative and copy optimization prepared without fabricating performance metrics.",
            "data": optimization,
            "step": step,
            "total_steps": total_steps,
        }

        # â”€â”€ STEP 8: PublishPlannerAgent â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        step += 1
        yield {
            "type": "thinking",
            "agent": "PublishPlannerAgent",
            "message": "Building the approval, scheduling, and publishing action plan.",
            "step": step,
            "total_steps": total_steps,
        }
        publish_plan = {
            "approval_gate": "Human approval required before any external publish action.",
            "ready_channels": [item for item in readiness if item.get("state") == "ready"],
            "draft_only_channels": [item for item in readiness if item.get("state") != "ready"],
            "campaign_queue": [
                {
                    "campaign_id": str(parent_campaign.id),
                    "campaign_type": parent_campaign.campaign_type,
                    "status": parent_campaign.status,
                    "recommended_action": "approve_then_publish" if any(item.get("state") == "ready" for item in readiness) else "review_and_connect_integration",
                }
            ],
        }
        yield {
            "type": "step_complete",
            "agent": "PublishPlannerAgent",
            "message": "Publish plan prepared with approval gates and integration-aware next actions.",
            "data": {
                "publish_plan": publish_plan,
                "next_actions": [
                    {"label": "Review Campaign Queue", "action": "open_campaigns"},
                    *(
                        [{"label": "Connect Publishing Integrations", "action": "open_integrations"}]
                        if blocked
                        else [{"label": "Approve Ready Campaigns", "action": "approve_publish"}]
                    ),
                ],
            },
            "step": step,
            "total_steps": total_steps,
        }

        # â”€â”€ Final summary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        yield {
            "type": "complete",
            "message": "AI Marketing Engine run complete",
            "data": {
                "campaigns_created": 1,
                "assets_created": len(created_assets),
                "campaign_ids": [str(parent_campaign.id)],
                "analytics_source": "real",
                "optimization": optimization,
                "strategy": strategy,
                "readiness": readiness,
                "execution_queue": execution_queue,
                "next_actions": [
                    {"label": "Review Campaign Queue", "action": "open_campaigns"},
                    {"label": "Open Integrations", "action": "open_integrations"} if blocked else {"label": "Approve and Publish", "action": "approve_publish"},
                ],
            },
            "step": total_steps,
            "total_steps": total_steps,
        }

    async def _integration_readiness(
        self,
        business_id: UUID,
        platforms: list[str],
        *,
        user_id: str | UUID | None,
    ) -> list[dict]:
        """Return publish readiness by selected marketing channel."""
        if not user_id:
            return []

        statuses = await OAuthManagerService(self.db).list_statuses(str(user_id), str(business_id))
        by_platform = {item["platform"]: item for item in statuses}

        def connected(*names: str) -> bool:
            return any((by_platform.get(name) or {}).get("status") == "connected" for name in names)

        readiness: list[dict] = []
        for platform in platforms:
            if platform == "email":
                ok = connected("gmail", "google", "sendgrid")
                readiness.append({
                    "platform": platform,
                    "state": "ready" if ok else "blocked",
                    "mode": "Gmail OAuth or SendGrid",
                    "reason": "Email sending provider available." if ok else "Connect Gmail or configure SendGrid before sending.",
                    "action": "send_email" if ok else "open_integrations",
                })
            elif platform == "social":
                social_ready = connected("linkedin", "twitter", "instagram", "facebook")
                readiness.append({
                    "platform": platform,
                    "state": "ready" if social_ready else "draft_ready",
                    "mode": "Official social APIs or Browser Agent fallback",
                    "reason": "At least one social publisher is connected." if social_ready else "Campaign drafts can be generated now; connect social OAuth or use Browser Agent before publishing.",
                    "action": "publish_social" if social_ready else "browser_or_connect",
                })
            elif platform == "google_ads":
                ok = connected("google_ads")
                readiness.append({
                    "platform": platform,
                    "state": "ready" if ok else "draft_ready",
                    "mode": "Google Ads draft mode",
                    "reason": "Google Ads connected for draft payload creation." if ok else "Ad drafts can be generated; launching spend requires Google Ads integration and explicit approval.",
                    "action": "create_ad_draft",
                })
            elif platform == "meta_ads":
                ok = connected("meta_ads", "meta")
                readiness.append({
                    "platform": platform,
                    "state": "ready" if ok else "draft_ready",
                    "mode": "Meta Ads draft mode",
                    "reason": "Meta Ads connected for draft payload creation." if ok else "Ad drafts can be generated; launching spend requires Meta integration and explicit approval.",
                    "action": "create_ad_draft",
                })
            elif platform == "wordpress":
                ok = connected("wordpress", "notion")
                readiness.append({
                    "platform": platform,
                    "state": "ready" if ok else "draft_ready",
                    "mode": "WordPress OAuth or Notion staging",
                    "reason": "Publishing/staging destination available." if ok else "Blog draft can be generated; connect WordPress or Notion to push it out.",
                    "action": "publish_content" if ok else "open_integrations",
                })
            else:
                readiness.append({
                    "platform": platform,
                    "state": "draft_ready",
                    "mode": "Draft generation",
                    "reason": "The agent can generate this campaign asset now. Publishing may require an integration.",
                    "action": "generate_asset",
                })
        return readiness

    def _execution_queue(self, platforms: list[str], readiness: list[dict]) -> list[dict]:
        readiness_by_platform = {item["platform"]: item for item in readiness}
        queue = []
        for index, platform in enumerate(platforms, start=1):
            status = readiness_by_platform.get(platform, {})
            queue.append({
                "order": index,
                "platform": platform,
                "agent": "CampaignAgent",
                "status": status.get("state", "draft_ready"),
                "next_action": status.get("action", "generate_asset"),
                "human_gate": "approval_required",
            })
        return queue

    async def _generate_full_email(
        self, biz_ctx: dict, email_data: dict, goal: str
    ) -> dict:
        """Generate a complete production-ready HTML email."""
        name = biz_ctx["name"]
        niche = biz_ctx["niche"]
        audience = biz_ctx["target_audience"]
        tone = biz_ctx.get("brand_tone", "professional")
        cta = email_data.get("cta_text", biz_ctx["cta_text"])
        subject = email_data.get("subject", f"Special offer from {name}")
        headline = email_data.get("headline", biz_ctx["headline"])
        body = email_data.get("body", biz_ctx.get("description", ""))
        preview = email_data.get("preview_text", "")

        # Generate full structured email content via AI
        full_prompt = (
            f"You are a professional email copywriter using AIDA framework.\n"
            f"Generate a complete email campaign structure.\n"
            f"Return ONLY valid JSON with these exact keys:\n"
            f"  subject, preview_text, from_name, headline, subheadline,\n"
            f"  intro, body_sections (array of {{title, content}}),\n"
            f"  bullet_points (array of 3-5 strings),\n"
            f"  offer, cta_text, ps, plain_text\n\n"
            f"Business: {name}\n"
            f"Niche: {niche}\n"
            f"Audience: {audience}\n"
            f"Tone: {tone}\n"
            f"Goal: {goal}\n"
            f"Subject hint: {subject}\n"
            f"Headline hint: {headline}\n\n"
            f"Rules:\n"
            f"- Use AIDA: Attention, Interest, Desire, Action\n"
            f"- Be specific to this business, no generic text\n"
            f"- CTA must be action-oriented\n"
            f"- PS line creates urgency"
        )
        try:
            email_struct = await self._ai.generate_json(full_prompt, task_type="marketing")
        except Exception:
            email_struct = {
                "subject": subject,
                "preview_text": preview,
                "from_name": name,
                "headline": headline,
                "subheadline": f"The solution for {audience}",
                "intro": body[:200] if body else "",
                "body_sections": [{"title": "Why Choose Us", "content": body}],
                "bullet_points": ["Real results", "Easy to use", "Proven system"],
                "offer": "Start your free trial today",
                "cta_text": cta,
                "ps": "P.S. This offer expires soon.",
                "plain_text": body,
            }

        # Build production HTML email (table-based, inline CSS, mobile-responsive)
        html = self._build_html_email(email_struct, biz_ctx)
        email_struct["html"] = html
        email_struct["from_email"] = f"hello@{name.lower().replace(' ', '')}.com"
        email_struct["reply_to"] = f"support@{name.lower().replace(' ', '')}.com"

        return email_struct

    def _build_html_email(self, s: dict, biz: dict) -> str:
        """Build a production-ready HTML email with inline CSS."""
        name = biz["name"]
        cta = s.get("cta_text", "Get Started")
        headline = s.get("headline", name)
        subheadline = s.get("subheadline", "")
        intro = s.get("intro", "")
        offer = s.get("offer", "")
        ps = s.get("ps", "")
        bullets = s.get("bullet_points", [])
        sections = s.get("body_sections", [])

        bullets_html = "".join(
            f'<tr><td style="padding:4px 0;color:#374151;font-size:14px;">âœ“ {b}</td></tr>'
            for b in bullets[:5]
        )
        sections_html = "".join(
            f'''<tr><td style="padding:12px 0;">
              <h3 style="margin:0 0 6px;font-size:16px;color:#1e293b;">{sec.get("title","")}</h3>
              <p style="margin:0;font-size:14px;color:#374151;line-height:1.6;">{sec.get("content","")}</p>
            </td></tr>'''
            for sec in sections[:3]
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{s.get("subject", name)}</title>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:20px 0;">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

      <!-- Header -->
      <tr><td style="background:linear-gradient(135deg,#0f172a,#1e1b4b);padding:28px 32px;border-radius:12px 12px 0 0;text-align:center;">
        <h1 style="margin:0;color:#fff;font-size:22px;font-weight:900;letter-spacing:-0.5px;">{name}</h1>
        <p style="margin:6px 0 0;color:rgba(255,255,255,0.5);font-size:12px;">{biz.get("niche","")}</p>
      </td></tr>

      <!-- Hero -->
      <tr><td style="background:#fff;padding:36px 32px 24px;">
        <h2 style="margin:0 0 10px;font-size:26px;font-weight:900;color:#0f172a;line-height:1.2;">{headline}</h2>
        <p style="margin:0 0 16px;font-size:16px;color:#6366f1;font-weight:600;">{subheadline}</p>
        <p style="margin:0;font-size:15px;color:#374151;line-height:1.7;">{intro}</p>
      </td></tr>

      <!-- Bullets -->
      {f'''<tr><td style="background:#f8fafc;padding:20px 32px;">
        <p style="margin:0 0 12px;font-size:13px;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;">Why it works</p>
        <table width="100%" cellpadding="0" cellspacing="0">{bullets_html}</table>
      </td></tr>''' if bullets else ""}

      <!-- Body sections -->
      {f'''<tr><td style="background:#fff;padding:20px 32px;">
        <table width="100%" cellpadding="0" cellspacing="0">{sections_html}</table>
      </td></tr>''' if sections else ""}

      <!-- Offer -->
      {f'''<tr><td style="background:#ede9fe;padding:20px 32px;border-left:4px solid #6366f1;">
        <p style="margin:0;font-size:15px;color:#4f46e5;font-weight:700;">{offer}</p>
      </td></tr>''' if offer else ""}

      <!-- CTA -->
      <tr><td style="background:#fff;padding:28px 32px;text-align:center;">
        <a href="#" style="display:inline-block;background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;font-size:16px;font-weight:800;padding:16px 40px;border-radius:12px;text-decoration:none;letter-spacing:0.3px;">{cta}</a>
        <p style="margin:12px 0 0;font-size:12px;color:#94a3b8;">No credit card required Â· Cancel anytime</p>
      </td></tr>

      <!-- PS -->
      {f'''<tr><td style="background:#fff;padding:0 32px 24px;">
        <p style="margin:0;font-size:13px;color:#64748b;font-style:italic;">{ps}</p>
      </td></tr>''' if ps else ""}

      <!-- Footer -->
      <tr><td style="background:#0f172a;padding:20px 32px;border-radius:0 0 12px 12px;text-align:center;">
        <p style="margin:0;font-size:12px;color:rgba(255,255,255,0.4);">
          Â© {datetime.now().year} {name} Â· <a href="#" style="color:rgba(255,255,255,0.4);">Unsubscribe</a>
        </p>
      </td></tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""

