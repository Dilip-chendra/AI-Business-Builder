"""Usage limits API endpoints for viewing and managing user quotas."""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.usage_limit_service import UsageLimitService, UsageLimitError

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class UsageLimitRead(BaseModel):
    """Response model for usage limit stats."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    plan_type: str
    monthly_request_limit: int
    monthly_token_limit: int
    requests_used_this_month: int
    tokens_used_this_month: int
    requests_remaining: int
    tokens_remaining: int
    request_usage_percent: float
    token_usage_percent: float
    is_at_limit: bool
    is_approaching_limit: bool
    billing_cycle_start: str
    billing_cycle_end: str
    is_enforced: bool
    hard_limit_exceeded_at: str | None
    created_at: str | None
    updated_at: str | None


class PlanUpgradeRequest(BaseModel):
    """Request to upgrade user plan."""
    plan_type: str = Field(description="free | pro | enterprise")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/my-usage", response_model=UsageLimitRead)
async def get_my_usage(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageLimitRead:
    """Get current user's usage statistics and quota info."""
    svc = UsageLimitService(db)
    stats = await svc.get_usage_stats(current_user.id)
    return UsageLimitRead.model_validate(stats)


@router.get("/check", response_model=dict)
async def check_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check if user can perform an AI request.

    Returns 200 if allowed, 429 if quota exceeded.
    """
    svc = UsageLimitService(db)
    try:
        result = await svc.check_usage(current_user.id)
        return result
    except UsageLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
            headers={"Retry-After": "86400"},  # Retry after 24 hours
        )


@router.get("/check-gate")
async def check_feature_gate(
    feature: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check if the current user's tier allows access to a gated feature."""
    from app.services.usage_limit_service import GatedFeature
    try:
        gated = GatedFeature(feature)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown feature: {feature}. Valid: {[f.value for f in GatedFeature]}",
        )
    svc = UsageLimitService(db)
    result = await svc.check_feature_gate(current_user.id, gated)
    return {
        "allowed": result.allowed,
        "tier": result.tier,
        "required_tier": result.required_tier,
        "feature": result.feature,
    }


@router.post("/upgrade", response_model=UsageLimitRead)
async def upgrade_plan(
    request: PlanUpgradeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UsageLimitRead:
    """Upgrade user to a higher-tier plan.

    Note: In production, this should verify payment before allowing upgrade.
    """
    valid_plans = ["free", "pro", "enterprise"]
    if request.plan_type not in valid_plans:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan. Must be one of: {', '.join(valid_plans)}",
        )

    svc = UsageLimitService(db)
    limit = await svc.upgrade_plan(current_user.id, request.plan_type)

    logger.info("User upgraded plan  user_id=%s  new_plan=%s", current_user.id, request.plan_type)
    return UsageLimitRead.model_validate(limit.to_dict())


@router.get("/plans", response_model=dict)
async def list_plans() -> dict:
    """List available plans and their limits."""
    from app.services.usage_limit_service import UsageLimitService

    return {
        "plans": {
            plan_name: {
                "name": plan_name.title(),
                "description": {
                    "free": "100 requests/month, 50K tokens",
                    "pro": "10K requests/month, 10M tokens",
                    "enterprise": "Unlimited requests and tokens",
                }.get(plan_name, ""),
                **limits,
            }
            for plan_name, limits in UsageLimitService.PLAN_LIMITS.items()
        }
    }
