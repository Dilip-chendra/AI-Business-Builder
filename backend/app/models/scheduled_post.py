"""Scheduled Post model — queued campaign posts for future publishing."""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ScheduledPost(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scheduled_posts"

    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("marketing_campaigns.id", ondelete="CASCADE"),
        index=True, nullable=False
    )
    business_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("businesses.id", ondelete="CASCADE"),
        index=True, nullable=False
    )
    platform: Mapped[str] = mapped_column(String(40), nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    scheduled_at_utc: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(60), nullable=False, default="UTC")
    # pending | published | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    published_at: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    business = relationship("Business", foreign_keys=[business_id])

    def to_dict(self) -> dict:
        import json as _json
        return {
            "id": str(self.id),
            "campaign_id": str(self.campaign_id),
            "business_id": str(self.business_id),
            "platform": self.platform,
            "content": _json.loads(self.content_json or "{}"),
            "scheduled_at_utc": self.scheduled_at_utc,
            "timezone": self.timezone,
            "status": self.status,
            "published_at": self.published_at,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
