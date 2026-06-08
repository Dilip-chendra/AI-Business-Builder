from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class AnalyticsEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "analytics_events"

    business_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), index=True)
    campaign_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("marketing_campaigns.id", ondelete="SET NULL"), index=True)
    asset_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("campaign_assets.id", ondelete="SET NULL"), index=True)
    contact_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), index=True)
    event_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    source: Mapped[str | None] = mapped_column(String(120))
    value_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revenue_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(12), nullable=False, default="USD")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    business = relationship("Business", back_populates="analytics_events")
    product = relationship("Product", back_populates="analytics_events")
