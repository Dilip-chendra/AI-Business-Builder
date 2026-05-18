from uuid import UUID

from pydantic import BaseModel, Field


class CheckoutSessionCreate(BaseModel):
    product_id: UUID
    customer_email: str | None = None
    quantity: int = Field(default=1, ge=1, le=99)


class CheckoutSessionRead(BaseModel):
    checkout_url: str
    session_id: str
