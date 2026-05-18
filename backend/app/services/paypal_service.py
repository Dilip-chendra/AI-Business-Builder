from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import BillingPlan, PaymentTransaction, UserSubscription
from app.models.product import Product
from app.models.user import User


DEFAULT_PLANS = [
    {
        "name": "Free",
        "slug": "free",
        "description": "Starter plan for solo builders validating an idea.",
        "price_cents": 0,
        "currency": "USD",
        "interval": "free",
        "features_json": {
            "headline": "Launch your first AI business flow",
            "highlights": ["50 AI requests", "3 browser runs", "2 campaigns", "1 project"],
        },
        "limits_json": {
            "ai_request": 50,
            "browser_agent_run": 3,
            "marketing_campaign": 2,
            "image_generation": 2,
            "project": 1,
            "team_member": 1,
            "code_edit": 25,
            "seo_generation": 2,
        },
    },
    {
        "name": "Pro Monthly",
        "slug": "pro_monthly",
        "description": "For founders running multiple launches every month.",
        "price_cents": 1900,
        "currency": "USD",
        "interval": "month",
        "features_json": {
            "headline": "Serious operating room for one growth team",
            "highlights": ["5000 AI requests", "100 browser runs", "100 campaigns", "10 projects"],
        },
        "limits_json": {
            "ai_request": 5000,
            "browser_agent_run": 100,
            "marketing_campaign": 100,
            "image_generation": 100,
            "project": 10,
            "team_member": 3,
            "code_edit": 2000,
            "seo_generation": 100,
        },
    },
    {
        "name": "Pro Yearly",
        "slug": "pro_yearly",
        "description": "Annual Pro plan with a lower effective monthly cost.",
        "price_cents": 19900,
        "currency": "USD",
        "interval": "year",
        "features_json": {
            "headline": "Best value for a full year of execution",
            "highlights": ["5000 AI requests", "100 browser runs", "100 campaigns", "2 months free"],
        },
        "limits_json": {
            "ai_request": 5000,
            "browser_agent_run": 100,
            "marketing_campaign": 100,
            "image_generation": 100,
            "project": 10,
            "team_member": 3,
            "code_edit": 2000,
            "seo_generation": 100,
        },
    },
    {
        "name": "Team Monthly",
        "slug": "team_monthly",
        "description": "For teams operating multiple businesses and channels together.",
        "price_cents": 4900,
        "currency": "USD",
        "interval": "month",
        "features_json": {
            "headline": "A shared AI operating system for the whole team",
            "highlights": ["20000 AI requests", "500 browser runs", "Unlimited campaigns", "10 seats"],
        },
        "limits_json": {
            "ai_request": 20000,
            "browser_agent_run": 500,
            "marketing_campaign": None,
            "image_generation": 500,
            "project": None,
            "team_member": 10,
            "code_edit": 10000,
            "seo_generation": 500,
        },
    },
]


class PayPalService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @property
    def enabled(self) -> bool:
        return bool(settings.paypal_client_id and settings.paypal_client_secret)

    @property
    def base_url(self) -> str:
        if settings.paypal_env.lower() == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"

    async def ensure_default_plans(self) -> list[BillingPlan]:
        plans: list[BillingPlan] = []
        for seed in DEFAULT_PLANS:
            result = await self.db.execute(select(BillingPlan).where(BillingPlan.slug == seed["slug"]))
            plan = result.scalars().first()
            if not plan:
                plan = BillingPlan(**seed)
                self.db.add(plan)
            else:
                for key, value in seed.items():
                    setattr(plan, key, value)
            plans.append(plan)
        await self.db.commit()
        for plan in plans:
            await self.db.refresh(plan)
        return plans

    async def _get_access_token(self) -> str:
        if not self.enabled:
            raise HTTPException(status_code=503, detail="PayPal credentials are not configured on the backend")
        credentials = f"{settings.paypal_client_id}:{settings.paypal_client_secret}".encode()
        auth_header = base64.b64encode(credentials).decode()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/oauth2/token",
                headers={
                    "Authorization": f"Basic {auth_header}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"PayPal token request failed: {response.text}")
        return response.json()["access_token"]

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        token: str | None = None,
    ) -> dict[str, Any]:
        access_token = token or await self._get_access_token()
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json=json_body,
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"PayPal API error: {response.text}")
        if response.status_code == 204:
            return {}
        return response.json()

    async def _ensure_paypal_product(self, plan: BillingPlan, token: str) -> BillingPlan:
        if plan.paypal_product_id:
            return plan
        payload = {
            "name": f"AI Business Builder {plan.name}",
            "description": plan.description,
            "type": "SERVICE",
            "category": "SOFTWARE",
        }
        product = await self._request("POST", "/v1/catalogs/products", json_body=payload, token=token)
        plan.paypal_product_id = product["id"]
        self.db.add(plan)
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def _ensure_paypal_plan(self, plan: BillingPlan, token: str) -> BillingPlan:
        if plan.interval == "free":
            return plan
        plan = await self._ensure_paypal_product(plan, token)
        if plan.paypal_plan_id:
            return plan
        interval_unit = "YEAR" if plan.interval == "year" else "MONTH"
        plan_payload = {
            "product_id": plan.paypal_product_id,
            "name": plan.name,
            "description": plan.description,
            "status": "ACTIVE",
            "billing_cycles": [
                {
                    "frequency": {"interval_unit": interval_unit, "interval_count": 1},
                    "tenure_type": "REGULAR",
                    "sequence": 1,
                    "total_cycles": 0,
                    "pricing_scheme": {
                        "fixed_price": {
                            "value": f"{plan.price_cents / 100:.2f}",
                            "currency_code": plan.currency,
                        }
                    },
                }
            ],
            "payment_preferences": {
                "auto_bill_outstanding": True,
                "setup_fee_failure_action": "CONTINUE",
                "payment_failure_threshold": 1,
            },
        }
        created = await self._request("POST", "/v1/billing/plans", json_body=plan_payload, token=token)
        plan.paypal_plan_id = created["id"]
        self.db.add(plan)
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def list_plans(self) -> list[BillingPlan]:
        return await self.ensure_default_plans()

    async def get_or_create_free_subscription(self, user: User) -> UserSubscription:
        await self.ensure_default_plans()
        result = await self.db.execute(
            select(UserSubscription)
            .where(UserSubscription.user_id == user.id)
            .order_by(UserSubscription.created_at.desc())
        )
        subscription = result.scalars().first()
        if subscription:
            return subscription
        plan = (await self.db.execute(select(BillingPlan).where(BillingPlan.slug == "free"))).scalars().one()
        subscription = UserSubscription(
            user_id=user.id,
            billing_plan_id=plan.id,
            provider="paypal",
            status="free",
            raw_provider_payload={},
        )
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)
        return subscription

    async def get_current_subscription(self, user: User) -> UserSubscription:
        await self.ensure_default_plans()
        result = await self.db.execute(
            select(UserSubscription)
            .where(UserSubscription.user_id == user.id)
            .order_by(UserSubscription.created_at.desc())
        )
        subscription = result.scalars().first()
        if not subscription:
            subscription = await self.get_or_create_free_subscription(user)
        return subscription

    async def create_subscription(self, user: User, plan_slug: str) -> dict[str, str]:
        plans = await self.ensure_default_plans()
        plan = next((item for item in plans if item.slug == plan_slug and item.is_active), None)
        if not plan or plan.interval == "free":
            raise HTTPException(status_code=400, detail="Choose a paid plan to create a PayPal subscription")
        token = await self._get_access_token()
        plan = await self._ensure_paypal_plan(plan, token)
        payload = {
            "plan_id": plan.paypal_plan_id,
            "subscriber": {
                "email_address": user.email,
                "name": {"given_name": (user.full_name or "Customer").split()[0]},
            },
            "application_context": {
                "brand_name": "AI Business Builder",
                "user_action": "SUBSCRIBE_NOW",
                "return_url": f"{settings.app_base_url}/billing/success",
                "cancel_url": f"{settings.app_base_url}/billing/cancel",
            },
        }
        response = await self._request("POST", "/v1/billing/subscriptions", json_body=payload, token=token)
        approval_url = next((link["href"] for link in response.get("links", []) if link.get("rel") == "approve"), None)
        if not approval_url:
            raise HTTPException(status_code=502, detail="PayPal did not return an approval URL")
        subscription = UserSubscription(
            user_id=user.id,
            billing_plan_id=plan.id,
            provider="paypal",
            provider_subscription_id=response["id"],
            status="approval_pending",
            raw_provider_payload=response,
        )
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)
        return {"paypal_subscription_id": response["id"], "approval_url": approval_url}

    async def sync_subscription(self, subscription_id: str) -> UserSubscription:
        token = await self._get_access_token()
        response = await self._request("GET", f"/v1/billing/subscriptions/{subscription_id}", token=token)
        result = await self.db.execute(
            select(UserSubscription).where(UserSubscription.provider_subscription_id == subscription_id)
        )
        subscription = result.scalars().first()
        if not subscription:
            raise HTTPException(status_code=404, detail="Subscription not found")
        subscription.status = (response.get("status") or subscription.status).lower()
        billing_info = response.get("billing_info") or {}
        subscription.current_period_start = billing_info.get("last_payment", {}).get("time")
        subscription.current_period_end = billing_info.get("next_billing_time")
        subscription.raw_provider_payload = response
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)
        return subscription

    async def cancel_subscription(self, user: User) -> UserSubscription:
        subscription = await self.get_current_subscription(user)
        if not subscription.provider_subscription_id or subscription.status not in {"active", "approval_pending"}:
            raise HTTPException(status_code=400, detail="No cancellable PayPal subscription found")
        token = await self._get_access_token()
        await self._request(
            "POST",
            f"/v1/billing/subscriptions/{subscription.provider_subscription_id}/cancel",
            json_body={"reason": "Cancelled by customer from billing dashboard"},
            token=token,
        )
        subscription.status = "cancelled"
        subscription.cancel_at_period_end = True
        self.db.add(subscription)
        await self.db.commit()
        await self.db.refresh(subscription)
        return subscription

    async def verify_webhook_signature(self, headers: dict[str, str], payload: dict[str, Any]) -> bool:
        if not settings.paypal_webhook_id:
            raise HTTPException(status_code=503, detail="PayPal webhook ID is not configured")
        token = await self._get_access_token()
        verification = await self._request(
            "POST",
            "/v1/notifications/verify-webhook-signature",
            json_body={
                "auth_algo": headers.get("paypal-auth-algo"),
                "cert_url": headers.get("paypal-cert-url"),
                "transmission_id": headers.get("paypal-transmission-id"),
                "transmission_sig": headers.get("paypal-transmission-sig"),
                "transmission_time": headers.get("paypal-transmission-time"),
                "webhook_id": settings.paypal_webhook_id,
                "webhook_event": payload,
            },
            token=token,
        )
        return verification.get("verification_status") == "SUCCESS"

    async def handle_webhook(self, headers: dict[str, str], payload: dict[str, Any]) -> None:
        verified = await self.verify_webhook_signature(headers, payload)
        if not verified:
            raise HTTPException(status_code=400, detail="Invalid PayPal webhook signature")

        event_type = payload.get("event_type")
        resource = payload.get("resource") or {}
        subscription_id = resource.get("id") or resource.get("billing_agreement_id")
        if subscription_id:
            result = await self.db.execute(
                select(UserSubscription).where(UserSubscription.provider_subscription_id == subscription_id)
            )
            subscription = result.scalars().first()
        else:
            subscription = None

        if event_type == "BILLING.SUBSCRIPTION.ACTIVATED" and subscription:
            subscription.status = "active"
            subscription.current_period_end = (resource.get("billing_info") or {}).get("next_billing_time")
            subscription.raw_provider_payload = payload
            self.db.add(subscription)
        elif event_type == "BILLING.SUBSCRIPTION.CANCELLED" and subscription:
            subscription.status = "cancelled"
            subscription.raw_provider_payload = payload
            self.db.add(subscription)
        elif event_type == "BILLING.SUBSCRIPTION.SUSPENDED" and subscription:
            subscription.status = "suspended"
            subscription.raw_provider_payload = payload
            self.db.add(subscription)
        elif event_type == "BILLING.SUBSCRIPTION.EXPIRED" and subscription:
            subscription.status = "expired"
            subscription.raw_provider_payload = payload
            self.db.add(subscription)
        elif event_type == "BILLING.SUBSCRIPTION.PAYMENT.FAILED" and subscription:
            subscription.status = "payment_failed"
            subscription.raw_provider_payload = payload
            self.db.add(subscription)

        if event_type in {"PAYMENT.SALE.COMPLETED", "PAYMENT.CAPTURE.COMPLETED"} and subscription:
            amount = resource.get("amount") or resource.get("seller_receivable_breakdown", {}).get("gross_amount") or {}
            transaction = PaymentTransaction(
                user_id=subscription.user_id,
                business_id=None,
                product_id=None,
                provider="paypal",
                provider_payment_id=resource.get("id"),
                provider_order_id=resource.get("supplementary_data", {}).get("related_ids", {}).get("order_id"),
                provider_subscription_id=subscription_id,
                amount_cents=int(round(float(amount.get("value", 0)) * 100)),
                currency=(amount.get("currency_code") or "USD"),
                status="completed",
                type="subscription" if subscription_id else "one_time",
                raw_provider_payload=payload,
            )
            self.db.add(transaction)
        await self.db.commit()

    async def create_order(self, user: User, product: Product, business_id: UUID | None = None) -> dict[str, str]:
        token = await self._get_access_token()
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": str(product.id),
                    "description": product.name,
                    "amount": {
                        "currency_code": product.currency.upper(),
                        "value": f"{float(product.price):.2f}",
                    },
                }
            ],
            "application_context": {
                "return_url": f"{settings.app_base_url}/billing/success",
                "cancel_url": f"{settings.app_base_url}/billing/cancel",
                "brand_name": "AI Business Builder",
            },
        }
        response = await self._request("POST", "/v2/checkout/orders", json_body=payload, token=token)
        approval_url = next((link["href"] for link in response.get("links", []) if link.get("rel") == "approve"), None)
        if not approval_url:
            raise HTTPException(status_code=502, detail="PayPal did not return an approval URL for the order")
        transaction = PaymentTransaction(
            user_id=user.id,
            business_id=business_id,
            product_id=product.id,
            provider="paypal",
            provider_order_id=response["id"],
            amount_cents=int(round(float(product.price) * 100)),
            currency=product.currency.upper(),
            status="created",
            type="subscription" if product.billing_type == "subscription" else "one_time",
            raw_provider_payload=response,
        )
        self.db.add(transaction)
        await self.db.commit()
        return {"order_id": response["id"], "approval_url": approval_url}

    async def capture_order(self, order_id: str) -> PaymentTransaction:
        token = await self._get_access_token()
        response = await self._request("POST", f"/v2/checkout/orders/{order_id}/capture", token=token)
        result = await self.db.execute(select(PaymentTransaction).where(PaymentTransaction.provider_order_id == order_id))
        transaction = result.scalars().first()
        if not transaction:
            raise HTTPException(status_code=404, detail="Payment transaction not found")
        captures = (
            response.get("purchase_units", [{}])[0]
            .get("payments", {})
            .get("captures", [{}])
        )
        capture = captures[0] if captures else {}
        transaction.provider_payment_id = capture.get("id")
        transaction.status = (capture.get("status") or "completed").lower()
        transaction.raw_provider_payload = response
        self.db.add(transaction)
        await self.db.commit()
        await self.db.refresh(transaction)
        return transaction
