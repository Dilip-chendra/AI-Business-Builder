from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.analytics import AnalyticsEvent
from app.models.job import Job, JobStatus
from app.models.marketing import MarketingCampaign
from app.models.order import Order
from app.schemas.analytics import (
    AnalyticsDashboardRead,
    AnalyticsEventCreate,
    AnalyticsSummaryRead,
    ProductPerformanceRead,
    UsagePointRead,
)
from app.core.cache import cache

_SUMMARY_TTL = 60  # seconds – refresh analytics cache every minute


class AnalyticsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def track(self, payload: AnalyticsEventCreate) -> None:
        self.db.add(AnalyticsEvent(**payload.model_dump()))
        await self.db.commit()
        # Invalidate cached summary so the next read reflects the new event
        await cache.delete(f"analytics_summary:{payload.business_id}")

    async def ensure_business_analytics(self, business_id: UUID) -> None:
        exists = await self.db.execute(
            select(AnalyticsEvent.id).where(
                AnalyticsEvent.business_id == business_id,
                AnalyticsEvent.event_type == "generated",
            )
        )
        if exists.scalar_one_or_none():
            return
        self.db.add(AnalyticsEvent(business_id=business_id, event_type="generated", source="system"))
        await self.db.commit()

    async def summary(self, business_id: UUID) -> AnalyticsSummaryRead:
        cache_key = f"analytics_summary:{business_id}"
        cached = await cache.get(cache_key)
        if cached is not None:
            # Reconstruct from cached dict
            try:
                return AnalyticsSummaryRead.model_validate(cached)
            except Exception:
                pass  # stale/invalid cache — recompute

        result = await self._compute_summary(business_id)
        # Store as dict so it's JSON-serialisable
        await cache.set(cache_key, result.model_dump(mode="json"), ttl=_SUMMARY_TTL)
        return result

    async def _compute_summary(self, business_id: UUID) -> AnalyticsSummaryRead:
        event_counts = await self.db.execute(
            select(AnalyticsEvent.event_type, func.count(AnalyticsEvent.id))
            .where(AnalyticsEvent.business_id == business_id)
            .group_by(AnalyticsEvent.event_type)
        )
        counts = {row[0]: row[1] for row in event_counts.all()}

        revenue = await self.db.execute(
            select(func.coalesce(func.sum(Order.amount_cents), 0)).where(
                Order.business_id == business_id,
                Order.status == "paid",
            )
        )
        revenue_cents = int(revenue.scalar_one())

        product_rows = await self.db.execute(
            select(
                AnalyticsEvent.product_id,
                func.count(AnalyticsEvent.id),
                func.coalesce(func.sum(AnalyticsEvent.value_cents), 0),
            )
            .where(AnalyticsEvent.business_id == business_id)
            .group_by(AnalyticsEvent.product_id)
        )
        product_performance = [
            ProductPerformanceRead(product_id=row[0], events=row[1], revenue_cents=row[2])
            for row in product_rows.all()
        ]
        visitors = int(counts.get("visit", 0))
        conversions = int(counts.get("conversion", 0))
        return AnalyticsSummaryRead(
            business_id=business_id,
            visitors=visitors,
            clicks=int(counts.get("click", 0)),
            conversions=conversions,
            revenue_cents=revenue_cents,
            conversion_rate=(conversions / visitors) if visitors else 0,
            product_performance=product_performance,
        )

    async def dashboard_summary(self, business_id: UUID) -> AnalyticsDashboardRead:
        ai_requests_q = await self.db.execute(
            select(func.count(Job.id)).where(Job.business_id == business_id)
        )
        ai_requests = int(ai_requests_q.scalar() or 0)

        campaigns_q = await self.db.execute(
            select(func.count(MarketingCampaign.id)).where(MarketingCampaign.business_id == business_id)
        )
        campaigns_generated = int(campaigns_q.scalar() or 0)

        success_q = await self.db.execute(
            select(
                func.sum(case((Job.status == JobStatus.COMPLETED, 1), else_=0)),
                func.sum(case((Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]), 1), else_=0)),
            ).where(Job.business_id == business_id)
        )
        completed, finished = success_q.one()
        success_rate = (float(completed or 0) / float(finished or 1)) if (finished or 0) > 0 else 0.0

        usage_rows = await self.db.execute(
            select(
                func.date(Job.created_at).label("d"),
                func.count(Job.id).label("ai_count"),
            )
            .where(Job.business_id == business_id)
            .group_by(func.date(Job.created_at))
            .order_by(func.date(Job.created_at).desc())
            .limit(14)
        )
        campaign_rows = await self.db.execute(
            select(
                func.date(MarketingCampaign.created_at).label("d"),
                func.count(MarketingCampaign.id).label("campaign_count"),
            )
            .where(MarketingCampaign.business_id == business_id)
            .group_by(func.date(MarketingCampaign.created_at))
        )
        campaign_map = {str(row.d): int(row.campaign_count) for row in campaign_rows.all()}

        points = [
            UsagePointRead(
                date=str(row.d),
                ai_requests=int(row.ai_count or 0),
                campaigns_generated=campaign_map.get(str(row.d), 0),
            )
            for row in usage_rows.all()
        ]

        return AnalyticsDashboardRead(
            business_id=business_id,
            ai_requests=ai_requests,
            campaigns_generated=campaigns_generated,
            success_rate=success_rate,
            usage_over_time=points,
        )
