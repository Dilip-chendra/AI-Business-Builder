from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class BillingPlan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "billing_plans"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    interval: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    paypal_product_id: Mapped[str | None] = mapped_column(String(255))
    paypal_plan_id: Mapped[str | None] = mapped_column(String(255))
    features_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    limits_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    subscriptions = relationship("UserSubscription", back_populates="billing_plan")


class UserSubscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "user_subscriptions"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    billing_plan_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_plans.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="paypal")
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="free", index=True)
    current_period_start: Mapped[str | None] = mapped_column(String(64))
    current_period_end: Mapped[str | None] = mapped_column(String(64))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_provider_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    user = relationship("User", back_populates="subscriptions")
    billing_plan = relationship("BillingPlan", back_populates="subscriptions")


class PaymentTransaction(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "payment_transactions"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    business_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="SET NULL"), index=True
    )
    product_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="paypal")
    provider_payment_id: Mapped[str | None] = mapped_column(String(255), index=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(255), index=True)
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="subscription")
    raw_provider_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    user = relationship("User", back_populates="payment_transactions")
    business = relationship("Business", back_populates="payment_transactions")
    product = relationship("Product", back_populates="payment_transactions")


class UsageLedger(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "usage_ledger"

    user_id: Mapped[str] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    business_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="SET NULL"), index=True
    )
    feature_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    period_start: Mapped[str] = mapped_column(String(64), nullable=False)
    period_end: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="app")
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    user = relationship("User", back_populates="usage_ledger_entries")
    business = relationship("Business", back_populates="usage_ledger_entries")
