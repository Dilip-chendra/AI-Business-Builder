"""AI Memory routes — brand context per business.

GET  /ai/memory/{business_id}  — retrieve brand context
POST /ai/memory/{business_id}  — create or update brand context
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.ai_memory_service import AIMemoryService
from app.services.business_service import BusinessService

router = APIRouter()


class AIMemoryUpdate(BaseModel):
    brand_name: str = ""
    tone_of_voice: str = ""
    target_audience: str = ""
    key_differentiators: list[str] = []


@router.get("/memory/{business_id}")
async def get_ai_memory(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the stored brand context for a business."""
    biz = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    mem = await AIMemoryService(db).get_context(str(business_id), str(current_user.id))
    if not mem:
        raise HTTPException(status_code=404, detail="No AI memory found for this business")
    return mem.to_dict()


@router.post("/memory/{business_id}")
async def save_ai_memory(
    business_id: UUID,
    payload: AIMemoryUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create or update the brand context for a business."""
    biz = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    mem = await AIMemoryService(db).save_context(
        str(business_id), str(current_user.id), payload.model_dump()
    )
    return mem.to_dict()
