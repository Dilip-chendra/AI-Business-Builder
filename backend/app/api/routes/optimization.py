"""AI optimization endpoint for landing page and pricing improvements."""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.ai_service import AIProviderError
from app.services.optimization_service import OptimizationService

router = APIRouter()


class OptimizationRead(BaseModel):
    headline: str | None = None
    cta_text: str | None = None
    pricing_note: str | None = None
    positioning_note: str | None = None


@router.get("/{business_id}", response_model=OptimizationRead)
async def get_optimization(
    business_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> OptimizationRead:
    try:
        suggestion = await OptimizationService(db).suggest(business_id)
    except AIProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if suggestion.positioning_note == "Business not found.":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
    return OptimizationRead(**suggestion.to_dict())
