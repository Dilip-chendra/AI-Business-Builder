from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.payment import CheckoutSessionCreate, CheckoutSessionRead
from app.services.business_service import BusinessService
from app.services.payment_service import PaymentService

router = APIRouter()


@router.post("/checkout", response_model=CheckoutSessionRead)
async def create_checkout_session(
    payload: CheckoutSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckoutSessionRead:
    session = await PaymentService(db).create_checkout_session(payload)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return session


@router.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Public endpoint — called by Stripe servers, no auth required."""
    raw_body = await request.body()
    signature = request.headers.get("stripe-signature")
    await PaymentService(db).handle_webhook(raw_body, signature)
    return {"status": "accepted"}


@router.get("/orders/{business_id}")
async def list_orders(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify business belongs to user
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return await PaymentService(db).list_orders(business_id)
