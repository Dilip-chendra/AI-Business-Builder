from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import BillingPlan, UsageLedger, UserSubscription
from app.services.paypal_service import PayPalService


FREE_PLAN_LIMITS = {
    "ai_request": 50,
    "browser_agent_run": 3,
    "marketing_campaign": 2,
    "image_generation": 2,
    "project": 1,
    "team_member": 1,
    "code_edit": 25,
    "seo_generation": 2,
}


@dataclass
class PlanUsage:
    plan: BillingPlan
    used: int
    limit: int | None
    period_start: datetime
    period_end: datetime


class UsageService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_current_plan(self, user_id: UUID) -> BillingPlan:
        await PayPalService(self.db).ensure_default_plans()
        result = await self.db.execute(
            select(UserSubscription)
            .where(
                UserSubscription.user_id == user_id,
                UserSubscription.status.in_(["active", "approval_pending", "free"]),
            )
            .order_by(UserSubscription.created_at.desc())
        )
        subscription = result.scalars().first()
        if subscription:
            plan = await self.db.get(BillingPlan, subscription.billing_plan_id)
            if plan:
                return plan

        result = await self.db.execute(select(BillingPlan).where(BillingPlan.slug == "free"))
        plan = result.scalars().first()
        if not plan:
            raise HTTPException(status_code=500, detail="Billing plans not initialized")
        return plan

    def _period_for_plan(self, plan: BillingPlan) -> tuple[datetime, datetime]:
        now = datetime.now(UTC)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if plan.interval == "year":
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(year=start.year + 1)
        else:
            if start.month == 12:
                end = start.replace(year=start.year + 1, month=1)
            else:
                end = start.replace(month=start.month + 1)
        return start, end

    async def get_usage(self, user_id: UUID, feature_key: str, plan: BillingPlan | None = None) -> PlanUsage:
        plan = plan or await self.get_current_plan(user_id)
        period_start, period_end = self._period_for_plan(plan)
        result = await self.db.execute(
            select(func.coalesce(func.sum(UsageLedger.quantity), 0)).where(
                UsageLedger.user_id == user_id,
                UsageLedger.feature_key == feature_key,
                UsageLedger.period_start == period_start.isoformat(),
                UsageLedger.period_end == period_end.isoformat(),
            )
        )
        used = int(result.scalar() or 0)
        limit_value = (plan.limits_json or {}).get(feature_key)
        if limit_value in (None, "unlimited", -1):
            limit = None
        else:
            limit = int(limit_value)
        return PlanUsage(plan=plan, used=used, limit=limit, period_start=period_start, period_end=period_end)

    async def check_limit(self, user_id: UUID, feature_key: str) -> PlanUsage:
        usage = await self.get_usage(user_id, feature_key)
        if usage.limit is not None and usage.used >= usage.limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "usage_limit_exceeded",
                    "feature": feature_key,
                    "limit": usage.limit,
                    "used": usage.used,
                    "upgrade_required": True,
                },
            )
        return usage

    async def increment_usage(
        self,
        user_id: UUID,
        feature_key: str,
        quantity: int = 1,
        *,
        business_id: UUID | None = None,
        source: str = "app",
        metadata_json: dict | None = None,
    ) -> UsageLedger:
        usage = await self.get_usage(user_id, feature_key)
        ledger = UsageLedger(
            user_id=user_id,
            business_id=business_id,
            feature_key=feature_key,
            quantity=quantity,
            period_start=usage.period_start.isoformat(),
            period_end=usage.period_end.isoformat(),
            source=source,
            metadata_json=metadata_json or {},
        )
        self.db.add(ledger)
        await self.db.commit()
        await self.db.refresh(ledger)
        return ledger
