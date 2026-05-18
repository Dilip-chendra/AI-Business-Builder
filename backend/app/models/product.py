from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Product(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "products"

    business_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[str | None] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="usd")
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="digital")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    product_type: Mapped[str] = mapped_column(String(32), nullable=False, default="digital")
    image_url: Mapped[str | None] = mapped_column(String(500))
    purchase_link: Mapped[str | None] = mapped_column(String(500))
    stripe_price_id: Mapped[str | None] = mapped_column(String(255))
    payment_provider: Mapped[str | None] = mapped_column(String(32))
    paypal_product_id: Mapped[str | None] = mapped_column(String(255))
    paypal_plan_id: Mapped[str | None] = mapped_column(String(255))
    paypal_checkout_url: Mapped[str | None] = mapped_column(String(500))
    billing_type: Mapped[str] = mapped_column(String(32), nullable=False, default="one_time")

    business = relationship("Business", back_populates="products")
    project = relationship("Project", back_populates="products")
    orders = relationship("Order", back_populates="product")
    payment_transactions = relationship("PaymentTransaction", back_populates="product")
    analytics_events = relationship("AnalyticsEvent", back_populates="product")
