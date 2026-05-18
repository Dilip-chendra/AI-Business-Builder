"""AI optimization service for landing page copy, pricing, and positioning."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.schemas.analytics import AnalyticsSummaryRead
from app.services.ai_service import AIService
from app.services.analytics_service import AnalyticsService
from app.services.business_service import BusinessService


class OptimizationSuggestion:
    """Structured output from the AI optimization pass."""

    def __init__(
        self,
        headline: str | None = None,
        cta_text: str | None = None,
        pricing_note: str | None = None,
        positioning_note: str | None = None,
        raw: dict | None = None,
    ) -> None:
        self.headline = headline
        self.cta_text = cta_text
        self.pricing_note = pricing_note
        self.positioning_note = positioning_note
        self.raw = raw or {}

    def to_dict(self) -> dict:
        return {
            "headline": self.headline,
            "cta_text": self.cta_text,
            "pricing_note": self.pricing_note,
            "positioning_note": self.positioning_note,
        }


class OptimizationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def suggest(self, business_id: UUID) -> OptimizationSuggestion:
        business = await BusinessService(self.db).get(business_id)
        if not business:
            return OptimizationSuggestion(positioning_note="Business not found.")

        summary = await AnalyticsService(self.db).summary(business_id)
        parsed = await AIService().generate_json(self._build_prompt(business, summary), task_type="ai_studio")
        return OptimizationSuggestion(
            headline=parsed.get("headline"),
            cta_text=parsed.get("cta_text"),
            pricing_note=parsed.get("pricing_note"),
            positioning_note=parsed.get("positioning_note"),
            raw=parsed,
        )

    def _build_prompt(self, business: Business, summary: AnalyticsSummaryRead) -> str:
        return (
            "You are a conversion-rate optimization expert for an AI SaaS business builder.\n"
            "Return ONLY valid JSON with exactly these keys: headline, cta_text, pricing_note, positioning_note.\n"
            "Do not include markdown or prose outside the JSON.\n"
            "Keep each value under 120 characters and make every recommendation specific.\n\n"
            f"Business: {business.name}\n"
            f"Niche: {business.niche}\n"
            f"Current headline: {business.headline}\n"
            f"Current CTA: {business.cta_text}\n"
            f"Target audience: {business.target_audience}\n"
            f"Visitors: {summary.visitors}\n"
            f"Clicks: {summary.clicks}\n"
            f"Conversions: {summary.conversions}\n"
            f"Conversion rate: {summary.conversion_rate:.1%}\n"
            f"Revenue cents: {summary.revenue_cents}\n"
        )
