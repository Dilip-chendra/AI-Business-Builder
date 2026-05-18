from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.billing import BillingPlan, PaymentTransaction
from app.models.product import Product
from app.models.user import User
from app.schemas.billing import (
    BillingPlanRead,
    CancelSubscriptionResponse,
    CaptureOrderRequest,
    CreateOrderRequest,
    CreateSubscriptionRequest,
    CreateSubscriptionResponse,
    PaymentTransactionRead,
    SubscriptionRead,
    UsageSummary,
)
from app.services.paypal_service import PayPalService
from app.services.usage_service import UsageService

router = APIRouter()


@router.get("/plans", response_model=list[BillingPlanRead])
async def list_billing_plans(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BillingPlanRead]:
    plans = await PayPalService(db).list_plans()
    return [BillingPlanRead.model_validate(plan) for plan in plans if plan.is_active]


@router.get("/subscription", response_model=SubscriptionRead)
async def get_current_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionRead:
    paypal = PayPalService(db)
    usage_service = UsageService(db)
    subscription = await paypal.get_current_subscription(current_user)
    if subscription.provider_subscription_id and subscription.status in {"approval_pending", "active"}:
        try:
            subscription = await paypal.sync_subscription(subscription.provider_subscription_id)
        except HTTPException:
            pass
    plan = await db.get(BillingPlan, subscription.billing_plan_id)
    feature_keys = [
        "ai_request",
        "browser_agent_run",
        "marketing_campaign",
        "image_generation",
        "project",
        "code_edit",
        "seo_generation",
    ]
    usage: list[UsageSummary] = []
    for feature_key in feature_keys:
        snapshot = await usage_service.get_usage(current_user.id, feature_key, plan=plan)
        usage.append(
            UsageSummary(
                feature_key=feature_key,
                used=snapshot.used,
                limit=snapshot.limit,
                remaining=None if snapshot.limit is None else max(snapshot.limit - snapshot.used, 0),
                unlimited=snapshot.limit is None,
            )
        )
    return SubscriptionRead(
        subscription_id=subscription.id,
        provider=subscription.provider,
        provider_subscription_id=subscription.provider_subscription_id,
        status=subscription.status,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=subscription.cancel_at_period_end,
        plan=BillingPlanRead.model_validate(plan),
        usage=usage,
    )


@router.get("/transactions", response_model=list[PaymentTransactionRead])
async def list_payment_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PaymentTransactionRead]:
    result = await db.execute(
        select(PaymentTransaction)
        .where(PaymentTransaction.user_id == current_user.id)
        .order_by(PaymentTransaction.created_at.desc())
        .limit(100)
    )
    return [PaymentTransactionRead.model_validate(item) for item in result.scalars()]


@router.post("/paypal/create-subscription", response_model=CreateSubscriptionResponse)
async def create_paypal_subscription(
    payload: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateSubscriptionResponse:
    result = await PayPalService(db).create_subscription(current_user, payload.plan_slug)
    return CreateSubscriptionResponse(**result)


@router.post("/paypal/cancel-subscription", response_model=CancelSubscriptionResponse)
async def cancel_paypal_subscription(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CancelSubscriptionResponse:
    subscription = await PayPalService(db).cancel_subscription(current_user)
    return CancelSubscriptionResponse(status=subscription.status, subscription_id=subscription.provider_subscription_id)


@router.post("/paypal/webhook", status_code=status.HTTP_202_ACCEPTED)
async def paypal_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    payload = await request.json()
    headers = {k.lower(): v for k, v in request.headers.items()}
    await PayPalService(db).handle_webhook(headers, payload)
    return {"status": "accepted"}


@router.post("/paypal/create-order")
async def create_paypal_order(
    payload: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    product = await db.get(Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return await PayPalService(db).create_order(current_user, product, payload.business_id)


@router.post("/paypal/capture-order", response_model=PaymentTransactionRead)
async def capture_paypal_order(
    payload: CaptureOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaymentTransactionRead:
    transaction = await PayPalService(db).capture_order(payload.order_id)
    if str(transaction.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Payment transaction not found")
    return PaymentTransactionRead.model_validate(transaction)
