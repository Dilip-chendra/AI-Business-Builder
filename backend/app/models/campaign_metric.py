"""Campaign Metric model — time-series performance data per campaign."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class CampaignMetric(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "campaign_metrics"

    campaign_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("marketing_campaigns.id", ondelete="CASCADE"),
        index=True, nullable=False
    )
    recorded_at: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    impressions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    clicks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    conversions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spend_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    engagement: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    platform: Mapped[str] = mapped_column(String(40), nullable=False, default="")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "campaign_id": str(self.campaign_id),
            "recorded_at": self.recorded_at,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "conversions": self.conversions,
            "spend_cents": self.spend_cents,
            "engagement": self.engagement,
            "platform": self.platform,
            "ctr": round(self.clicks / max(self.impressions, 1) * 100, 2),
            "cpc_cents": round(self.spend_cents / max(self.clicks, 1), 2),
        }
