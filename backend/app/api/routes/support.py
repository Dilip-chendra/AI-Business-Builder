"""Customer Support Agent API — AI chatbot for visitor interactions."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.business_service import BusinessService
from app.services.product_service import ProductService
from app.services.support_service import SupportService

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class StartConversationRequest(BaseModel):
    visitor_token: str = Field(min_length=4, max_length=255)


class MessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    business_id: UUID
    visitor_token: str
    status: str
    messages: list
    summary: str | None
    created_at: datetime


# ── Public endpoints (visitor-facing) ─────────────────────────────────────────

@router.post("/{business_id}/conversations", response_model=ConversationRead, status_code=201)
async def start_conversation(
    business_id: UUID,
    payload: StartConversationRequest,
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    """Start or resume a support conversation. Public — no auth required."""
    conv = await SupportService(db).get_or_create_conversation(
        business_id=business_id,
        visitor_token=payload.visitor_token,
    )
    return ConversationRead.model_validate(conv)


@router.post("/{business_id}/conversations/{conversation_id}/message")
async def send_message(
    business_id: UUID,
    conversation_id: UUID,
    payload: MessageRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a message and get an AI response. Public — no auth required."""
    from app.models.business import Business
    from app.models.marketing import SupportConversation
    business = await db.get(Business, business_id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    conversation = await db.get(SupportConversation, conversation_id)
    if not conversation or str(conversation.business_id) != str(business_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    products = await ProductService(db).list(business_id)
    result = await SupportService(db).send_message(
        conversation_id=conversation_id,
        user_message=payload.message,
        business_context={
            "name": business.name,
            "niche": business.niche,
            "target_audience": business.target_audience,
            "brand_tone": business.brand_tone,
        },
        products=[{"name": p.name, "price": str(p.price), "description": p.description} for p in products],
    )
    if "error" in result:
        raise HTTPException(status_code=503, detail=result["error"])
    return result


# ── Authenticated endpoints (business owner) ──────────────────────────────────

@router.get("/{business_id}/conversations", response_model=list[ConversationRead])
async def list_conversations(
    business_id: UUID,
    conv_status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationRead]:
    """List all support conversations for a business."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    convs = await SupportService(db).list_conversations(business_id, conv_status)
    return [ConversationRead.model_validate(c) for c in convs]


@router.patch("/{business_id}/conversations/{conversation_id}/resolve", response_model=ConversationRead)
async def resolve_conversation(
    business_id: UUID,
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationRead:
    """Resolve a conversation and generate an AI summary."""
    from app.models.marketing import SupportConversation

    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    existing = await db.get(SupportConversation, conversation_id)
    if not existing or str(existing.business_id) != str(business_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    conv = await SupportService(db).resolve_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationRead.model_validate(conv)
