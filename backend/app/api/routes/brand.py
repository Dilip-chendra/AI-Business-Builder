"""Brand System routes.

GET  /brand/{business_id}  — get brand system
POST /brand/{business_id}  — create or update brand system
"""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.brand_system_service import BrandSystemService
from app.services.business_service import BusinessService

router = APIRouter()


class BrandSystemUpdate(BaseModel):
    primary_color: str = "#6366f1"
    secondary_color: str = "#8b5cf6"
    tone_of_voice: str = "professional"
    target_audience: str = ""
    industry: str = ""
    competitors: list[str] = []
    website_url: str | None = None
    logo_description: str | None = None


@router.get("/{business_id}")
async def get_brand_system(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return the brand system for a business."""
    biz = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    brand = await BrandSystemService(db).get(str(business_id))
    if not brand:
        raise HTTPException(status_code=404, detail="No brand system found for this business")
    return brand.to_dict()


@router.post("/{business_id}")
async def save_brand_system(
    business_id: UUID,
    payload: BrandSystemUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create or update the brand system for a business."""
    biz = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")
    brand = await BrandSystemService(db).upsert(str(business_id), payload.model_dump())
    return brand.to_dict()
