"""Real click and conversion tracking endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.analytics import AnalyticsEvent

router = APIRouter()


class ConversionPayload(BaseModel):
    business_id: UUID
    campaign_id: UUID
    asset_id: UUID | None = None
    contact_id: UUID | None = None
    source: str = "conversion"
    revenue_amount: float = Field(default=0, ge=0)
    currency: str = "USD"
    metadata: dict = Field(default_factory=dict)


@router.get("/click")
async def track_click(
    business_id: UUID = Query(...),
    campaign_id: UUID = Query(...),
    asset_id: UUID | None = Query(default=None),
    contact_id: UUID | None = Query(default=None),
    redirect: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    db.add(
        AnalyticsEvent(
            business_id=business_id,
            campaign_id=campaign_id,
            asset_id=asset_id,
            contact_id=contact_id,
            event_type="click",
            source="tracking_link",
            value_cents=0,
            revenue_amount=0,
            currency="USD",
            metadata_json={"redirect": redirect},
        )
    )
    await db.commit()
    return RedirectResponse(redirect, status_code=302)


@router.post("/conversion")
async def track_conversion(payload: ConversionPayload, db: AsyncSession = Depends(get_db)) -> dict:
    revenue_cents = int(round(payload.revenue_amount * 100))
    db.add(
        AnalyticsEvent(
            business_id=payload.business_id,
            campaign_id=payload.campaign_id,
            asset_id=payload.asset_id,
            contact_id=payload.contact_id,
            event_type="conversion",
            source=payload.source,
            value_cents=revenue_cents,
            revenue_amount=payload.revenue_amount,
            currency=payload.currency.upper()[:12],
            metadata_json=payload.metadata,
        )
    )
    await db.commit()
    return {"status": "tracked", "analytics_source": "real"}
