from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProductCreate(BaseModel):
    business_id: UUID
    project_id: UUID | None = None
    name: str = Field(min_length=2, max_length=140)
    description: str = Field(min_length=5)
    price: Decimal = Field(gt=0)
    currency: str = Field(default="usd", min_length=3, max_length=3)
    category: str = Field(default="digital", max_length=100)
    status: str = Field(default="draft", max_length=32)
    product_type: str = Field(default="digital", max_length=32)
    image_url: str | None = None
    purchase_link: str | None = None
    stripe_price_id: str | None = None
    payment_provider: str | None = None
    paypal_product_id: str | None = None
    paypal_plan_id: str | None = None
    paypal_checkout_url: str | None = None
    billing_type: str = Field(default="one_time", max_length=32)


class ProductUpdate(BaseModel):
    project_id: UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=140)
    description: str | None = Field(default=None, min_length=5)
    price: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    category: str | None = Field(default=None, max_length=100)
    status: str | None = Field(default=None, max_length=32)
    product_type: str | None = Field(default=None, max_length=32)
    image_url: str | None = None
    purchase_link: str | None = None
    stripe_price_id: str | None = None
    payment_provider: str | None = None
    paypal_product_id: str | None = None
    paypal_plan_id: str | None = None
    paypal_checkout_url: str | None = None
    billing_type: str | None = Field(default=None, max_length=32)


class ProductRead(ProductCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime
