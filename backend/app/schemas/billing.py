from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BillingPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: str
    price_cents: int
    currency: str
    interval: str
    features_json: dict[str, Any]
    limits_json: dict[str, Any]
    is_active: bool


class UsageSummary(BaseModel):
    feature_key: str
    used: int
    limit: int | None
    remaining: int | None
    unlimited: bool = False


class SubscriptionRead(BaseModel):
    subscription_id: UUID | None = None
    provider: str = "paypal"
    provider_subscription_id: str | None = None
    status: str
    current_period_start: str | None = None
    current_period_end: str | None = None
    cancel_at_period_end: bool = False
    plan: BillingPlanRead
    usage: list[UsageSummary]


class CreateSubscriptionRequest(BaseModel):
    plan_slug: str = Field(pattern="^(pro_monthly|pro_yearly|team_monthly)$")


class CreateSubscriptionResponse(BaseModel):
    paypal_subscription_id: str
    approval_url: str


class CancelSubscriptionResponse(BaseModel):
    status: str
    subscription_id: str | None = None


class CreateOrderRequest(BaseModel):
    product_id: UUID
    business_id: UUID | None = None


class CaptureOrderRequest(BaseModel):
    order_id: str


class PaymentTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    provider_payment_id: str | None
    provider_order_id: str | None
    provider_subscription_id: str | None
    amount_cents: int
    currency: str
    status: str
    type: str
    created_at: datetime
