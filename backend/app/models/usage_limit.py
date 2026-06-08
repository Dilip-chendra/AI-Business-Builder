"""Usage limits model for tracking per-user AI request quotas."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class UsageLimit(UUIDMixin, TimestampMixin, Base):
    """Tracks AI usage and quota limits per user."""

    __tablename__ = "usage_limits"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, unique=True
    )

    # Monthly quota (resets on billing cycle)
    monthly_request_limit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    monthly_token_limit: Mapped[int] = mapped_column(Integer, default=1_000_000, nullable=False)

    # Current usage (resets at billing cycle)
    requests_used_this_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_used_this_month: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Billing cycle info
    billing_cycle_start: Mapped[str] = mapped_column(String(255), nullable=False)  # ISO format date
    billing_cycle_end: Mapped[str] = mapped_column(String(255), nullable=False)    # ISO format date

    # Limits can be customized per plan
    plan_type: Mapped[str] = mapped_column(
        String(50), default="free", nullable=False, index=True
    )  # free, pro, enterprise

    # Hard limit enforcement
    is_enforced: Mapped[bool] = mapped_column(default=True, nullable=False)
    hard_limit_exceeded_at: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Notification flags
    warned_at_80_percent: Mapped[bool] = mapped_column(default=False, nullable=False)
    warned_at_100_percent: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Extra data (stored as 'metadata' in DB)
    extra_data: Mapped[dict] = mapped_column(
        "metadata", JSON, default=dict, nullable=False
    )

    # Relationships — no back_populates on User to avoid circular import issues
    user = relationship("User", foreign_keys=[user_id])

    @property
    def requests_remaining(self) -> int:
        """Calculate remaining requests in current billing cycle."""
        return max(0, self.monthly_request_limit - self.requests_used_this_month)

    @property
    def tokens_remaining(self) -> int:
        """Calculate remaining tokens in current billing cycle."""
        return max(0, self.monthly_token_limit - self.tokens_used_this_month)

    @property
    def request_usage_percent(self) -> float:
        """Calculate percentage of monthly request quota used."""
        if self.monthly_request_limit == 0:
            return 0.0
        return (self.requests_used_this_month / self.monthly_request_limit) * 100

    @property
    def token_usage_percent(self) -> float:
        """Calculate percentage of monthly token quota used."""
        if self.monthly_token_limit == 0:
            return 0.0
        return (self.tokens_used_this_month / self.monthly_token_limit) * 100

    @property
    def is_at_limit(self) -> bool:
        """Check if user has exceeded any quota."""
        return (
            self.requests_used_this_month >= self.monthly_request_limit
            or self.tokens_used_this_month >= self.monthly_token_limit
        )

    @property
    def is_approaching_limit(self) -> bool:
        """Check if user is at 80% of quota."""
        return self.request_usage_percent >= 80 or self.token_usage_percent >= 80

    def to_dict(self) -> dict:
        """Convert to dict for API responses."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "plan_type": self.plan_type,
            "monthly_request_limit": self.monthly_request_limit,
            "monthly_token_limit": self.monthly_token_limit,
            "requests_used_this_month": self.requests_used_this_month,
            "tokens_used_this_month": self.tokens_used_this_month,
            "requests_remaining": self.requests_remaining,
            "tokens_remaining": self.tokens_remaining,
            "request_usage_percent": round(self.request_usage_percent, 2),
            "token_usage_percent": round(self.token_usage_percent, 2),
            "is_at_limit": self.is_at_limit,
            "is_approaching_limit": self.is_approaching_limit,
            "billing_cycle_start": self.billing_cycle_start,
            "billing_cycle_end": self.billing_cycle_end,
            "is_enforced": self.is_enforced,
            "hard_limit_exceeded_at": self.hard_limit_exceeded_at,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
