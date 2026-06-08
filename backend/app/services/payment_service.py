import logging
from decimal import Decimal
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.business import Business
from app.models.order import Order
from app.models.product import Product
from app.schemas.payment import CheckoutSessionCreate, CheckoutSessionRead
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class WebhookAlreadyProcessedError(Exception):
    """Raised when a Stripe webhook event has already been stored."""


class PaymentService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        stripe.api_key = settings.stripe_secret_key

    async def create_checkout_session(self, payload: CheckoutSessionCreate) -> CheckoutSessionRead | None:
        product = await self.db.get(Product, payload.product_id)
        if not product:
            return None

        if not settings.stripe_secret_key:
            session_id = f"local_{product.id}"
            return CheckoutSessionRead(
                checkout_url=f"{settings.frontend_url}/checkout/success?session_id={session_id}",
                session_id=session_id,
            )

        amount_cents = int(Decimal(product.price) * 100)
        session = stripe.checkout.Session.create(
            mode="payment",
            customer_email=payload.customer_email,
            line_items=[
                {
                    "price_data": {
                        "currency": product.currency,
                        "unit_amount": amount_cents,
                        "product_data": {"name": product.name, "description": product.description[:500]},
                    },
                    "quantity": payload.quantity,
                }
            ],
            metadata={"business_id": str(product.business_id), "product_id": str(product.id)},
            success_url=f"{settings.frontend_url}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{settings.frontend_url}/checkout/cancel",
        )
        return CheckoutSessionRead(checkout_url=session.url, session_id=session.id)

    async def handle_webhook(self, raw_body: bytes, signature: str | None) -> None:
        if not settings.stripe_secret_key or not settings.stripe_webhook_secret:
            logger.info("Stripe webhook ignored because Stripe is not configured")
            return

        event = stripe.Webhook.construct_event(raw_body, signature, settings.stripe_webhook_secret)
        if event["type"] != "checkout.session.completed":
            return

        session = event["data"]["object"]
        session_id: str = session["id"]

        # ── Idempotency guard ────────────────────────────────────────────────
        existing = await self.db.execute(
            select(Order.id).where(Order.stripe_session_id == session_id)
        )
        if existing.scalar_one_or_none():
            logger.info("Webhook already processed for session %s – skipping", session_id)
            return

        metadata = session.get("metadata", {})
        amount_cents = session.get("amount_total") or 0
        customer_email = session.get("customer_details", {}).get("email")
        order = Order(
            business_id=UUID(metadata["business_id"]),
            product_id=UUID(metadata["product_id"]),
            stripe_session_id=session_id,
            customer_email=customer_email,
            amount_cents=amount_cents,
            currency=session.get("currency", "usd"),
            status="paid",
            raw_payload=dict(session),
        )
        self.db.add(order)
        await self.db.commit()
        logger.info("Order stored for session %s  amount_cents=%s", session_id, amount_cents)

        # ── Send order confirmation email ─────────────────────────────────────
        if customer_email:
            product = await self.db.get(Product, UUID(metadata["product_id"]))
            business = await self.db.get(Business, UUID(metadata["business_id"]))
            product_name = product.name if product else "Product"
            business_name = business.name if business else "Business"
            try:
                await EmailService().send_order_confirmation(
                    to=customer_email,
                    business_name=business_name,
                    product_name=product_name,
                    amount_cents=amount_cents,
                    currency=session.get("currency", "usd"),
                )
            except Exception as exc:
                logger.warning("Order confirmation email failed: %s", exc)

    async def list_orders(self, business_id: UUID) -> list[Order]:
        result = await self.db.execute(select(Order).where(Order.business_id == business_id).order_by(Order.created_at.desc()))
        return list(result.scalars().all())
