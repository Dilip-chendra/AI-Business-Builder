"""Usage limit service for tracking and enforcing per-user AI quotas."""
from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.usage_limit import UsageLimit
from app.models.user import User

logger = logging.getLogger(__name__)


class UsageLimitError(Exception):
    """Raised when a user exceeds their usage quota."""


class GatedFeature(str, enum.Enum):
    """Features gated behind Pro or Enterprise tier."""
    AI_STUDIO_MULTI_STEP = "ai_studio_multi_step"
    CODE_EDITOR_RAG = "code_editor_rag"
    DEPLOYMENT_SYSTEM = "deployment_system"
    WORKSPACE_TEAM = "workspace_team"


@dataclass
class GateResult:
    allowed: bool
    tier: str
    required_tier: str
    feature: str


# Features available per tier
_TIER_FEATURES: dict[str, set[str]] = {
    "free": set(),
    "pro": {f.value for f in GatedFeature},
    "enterprise": {f.value for f in GatedFeature},
}


class UsageLimitService:
    """Service for managing usage limits and quotas."""

    # Plan-based limits
    PLAN_LIMITS = {
        "free": {
            "monthly_request_limit": 100,
            "monthly_token_limit": 50_000,
        },
        "pro": {
            "monthly_request_limit": 10_000,
            "monthly_token_limit": 10_000_000,
        },
        "enterprise": {
            "monthly_request_limit": 1_000_000,
            "monthly_token_limit": 1_000_000_000,
        },
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_limit(
        self,
        user_id: UUID | str,
        plan_type: str = "free",
    ) -> UsageLimit:
        """Get existing limit or create new one for user."""
        user_id_str = str(user_id)  # always string for SQLite compatibility

        # Try to get existing limit
        result = await self.db.execute(
            select(UsageLimit).where(UsageLimit.user_id == user_id_str)
        )
        limit = result.scalar_one_or_none()

        if limit:
            # Check if billing cycle has reset
            now = datetime.utcnow()
            cycle_end = datetime.fromisoformat(limit.billing_cycle_end)
            if now >= cycle_end:
                await self._reset_billing_cycle(limit)
            return limit

        # Create new limit
        now = datetime.utcnow()
        cycle_start = now.replace(day=1)
        cycle_end = (cycle_start + timedelta(days=32)).replace(day=1)

        plan_config = self.PLAN_LIMITS.get(plan_type, self.PLAN_LIMITS["free"])

        limit = UsageLimit(
            user_id=user_id_str,
            plan_type=plan_type,
            monthly_request_limit=plan_config["monthly_request_limit"],
            monthly_token_limit=plan_config["monthly_token_limit"],
            requests_used_this_month=0,
            tokens_used_this_month=0,
            billing_cycle_start=cycle_start.isoformat(),
            billing_cycle_end=cycle_end.isoformat(),
            is_enforced=True,
        )
        self.db.add(limit)
        await self.db.commit()
        await self.db.refresh(limit)

        logger.info(
            "Usage limit created  user_id=%s  plan=%s  requests=%d  tokens=%d",
            user_id_str,
            plan_type,
            limit.monthly_request_limit,
            limit.monthly_token_limit,
        )
        return limit

    async def check_usage(self, user_id: UUID | str) -> dict:
        """Check if user is within quotas. Raises UsageLimitError if exceeded."""
        limit = await self.get_or_create_limit(user_id)

        if not limit.is_enforced:
            logger.debug("Usage limits not enforced for user %s", user_id)
            return {"allowed": True, "message": "Limits not enforced"}

        if limit.is_at_limit:
            logger.warning(
                "Usage limit exceeded  user_id=%s  requests=%d/%d",
                user_id,
                limit.requests_used_this_month,
                limit.monthly_request_limit,
            )
            raise UsageLimitError(
                f"Monthly quota exceeded. "
                f"Used: {limit.requests_used_this_month}/{limit.monthly_request_limit} requests, "
                f"{limit.tokens_used_this_month:,}/{limit.monthly_token_limit:,} tokens. "
                f"Resets on {limit.billing_cycle_end}."
            )

        return {
            "allowed": True,
            "requests_remaining": limit.requests_remaining,
            "tokens_remaining": limit.tokens_remaining,
            "request_usage_percent": limit.request_usage_percent,
        }

    async def record_usage(
        self,
        user_id: UUID | str,
        requests: int = 1,
        tokens: int = 0,
    ) -> None:
        """Record AI usage for a user."""
        limit = await self.get_or_create_limit(user_id)

        limit.requests_used_this_month += requests
        limit.tokens_used_this_month += tokens

        # Track when hard limit is exceeded
        if limit.is_at_limit and not limit.hard_limit_exceeded_at:
            limit.hard_limit_exceeded_at = datetime.utcnow().isoformat()

        # Track warnings at 80% and 100%
        if limit.request_usage_percent >= 80 and not limit.warned_at_80_percent:
            limit.warned_at_80_percent = True
            logger.warning(
                "User approaching quota  user_id=%s  usage=80%%  "
                "requests=%d/%d",
                user_id,
                limit.requests_used_this_month,
                limit.monthly_request_limit,
            )

        if limit.is_at_limit and not limit.warned_at_100_percent:
            limit.warned_at_100_percent = True
            logger.error(
                "User quota exceeded  user_id=%s  usage=100%%  "
                "requests=%d/%d  tokens=%d/%d",
                user_id,
                limit.requests_used_this_month,
                limit.monthly_request_limit,
                limit.tokens_used_this_month,
                limit.monthly_token_limit,
            )

        await self.db.commit()
        logger.debug(
            "Usage recorded  user_id=%s  requests=%d  tokens=%d  "
            "total_requests=%d  total_tokens=%d",
            user_id,
            requests,
            tokens,
            limit.requests_used_this_month,
            limit.tokens_used_this_month,
        )

    async def get_usage_stats(self, user_id: UUID | str) -> dict:
        """Get detailed usage statistics for a user."""
        limit = await self.get_or_create_limit(user_id)
        return limit.to_dict()

    async def upgrade_plan(
        self,
        user_id: UUID | str,
        new_plan: str,
    ) -> UsageLimit:
        """Upgrade user to a new plan."""
        limit = await self.get_or_create_limit(user_id)

        if new_plan not in self.PLAN_LIMITS:
            raise ValueError(f"Invalid plan: {new_plan}")

        plan_config = self.PLAN_LIMITS[new_plan]
        limit.plan_type = new_plan
        limit.monthly_request_limit = plan_config["monthly_request_limit"]
        limit.monthly_token_limit = plan_config["monthly_token_limit"]

        await self.db.commit()
        await self.db.refresh(limit)

        logger.info("Plan upgraded  user_id=%s  new_plan=%s", user_id, new_plan)
        return limit

    async def reset_billing_cycle(self, user_id: UUID | str) -> UsageLimit:
        """Manually reset the billing cycle for a user."""
        limit = await self.get_or_create_limit(user_id)
        await self._reset_billing_cycle(limit)
        return limit

    async def _reset_billing_cycle(self, limit: UsageLimit) -> None:
        """Internal: Reset billing cycle counters."""
        now = datetime.utcnow()
        cycle_start = now.replace(day=1)
        cycle_end = (cycle_start + timedelta(days=32)).replace(day=1)

        limit.requests_used_this_month = 0
        limit.tokens_used_this_month = 0
        limit.billing_cycle_start = cycle_start.isoformat()
        limit.billing_cycle_end = cycle_end.isoformat()
        limit.warned_at_80_percent = False
        limit.warned_at_100_percent = False
        limit.hard_limit_exceeded_at = None

        await self.db.commit()
        logger.info(
            "Billing cycle reset  user_id=%s  cycle_start=%s  cycle_end=%s",
            limit.user_id,
            cycle_start.isoformat(),
            cycle_end.isoformat(),
        )

    async def disable_enforcement(self, user_id: UUID | str) -> None:
        """Disable usage limit enforcement for a user (e.g., enterprise accounts)."""
        limit = await self.get_or_create_limit(user_id)
        limit.is_enforced = False
        await self.db.commit()
        logger.warning("Usage limit enforcement disabled  user_id=%s", user_id)

    async def enable_enforcement(self, user_id: UUID | str) -> None:
        """Re-enable usage limit enforcement for a user."""
        limit = await self.get_or_create_limit(user_id)
        limit.is_enforced = True
        await self.db.commit()
        logger.info("Usage limit enforcement enabled  user_id=%s", user_id)

    async def check_feature_gate(
        self,
        user_id: UUID | str,
        feature: GatedFeature,
    ) -> GateResult:
        """Check if a user's tier allows access to a gated feature."""
        limit = await self.get_or_create_limit(user_id)
        tier = limit.plan_type or "free"
        allowed_features = _TIER_FEATURES.get(tier, set())
        allowed = feature.value in allowed_features
        required_tier = "pro" if feature.value in _TIER_FEATURES["pro"] else "enterprise"
        return GateResult(
            allowed=allowed,
            tier=tier,
            required_tier=required_tier,
            feature=feature.value,
        )
