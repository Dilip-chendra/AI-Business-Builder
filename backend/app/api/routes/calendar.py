"""Marketing calendar API backed by real database events and optional Google sync."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.marketing import MarketingCalendarEvent
from app.models.user import User
from app.services.business_service import BusinessService
from app.services.oauth_manager_service import OAuthManagerService, _decrypt

router = APIRouter()


class CalendarEventCreate(BaseModel):
    business_id: UUID
    campaign_id: UUID | None = None
    title: str = Field(min_length=2, max_length=300)
    description: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    platform: str | None = None
    sync_google: bool = False


class CalendarSyncRequest(BaseModel):
    business_id: UUID
    days_ahead: int = Field(default=60, ge=1, le=365)


def _serialize_event(event: MarketingCalendarEvent) -> dict:
    return {
        "id": str(event.id),
        "business_id": str(event.business_id),
        "campaign_id": str(event.campaign_id) if event.campaign_id else None,
        "google_event_id": event.google_event_id,
        "title": event.title,
        "description": event.description,
        "start_time": event.start_time.isoformat(),
        "end_time": event.end_time.isoformat() if event.end_time else None,
        "platform": event.platform,
        "status": event.status,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def _scope_set(scopes: object) -> set[str]:
    if isinstance(scopes, str):
        try:
            parsed = json.loads(scopes)
            if isinstance(parsed, list):
                return {str(scope) for scope in parsed}
        except Exception:
            return {scope.strip() for scope in scopes.replace(",", " ").split() if scope.strip()}
    if isinstance(scopes, (list, tuple, set)):
        return {str(scope) for scope in scopes}
    return set()


async def _google_access_token(db: AsyncSession, user: User, business_id: UUID) -> str:
    manager = OAuthManagerService(db)
    token = await manager.get_token(str(user.id), str(business_id), "google")
    if not token:
        token = await manager.get_token(str(user.id), str(business_id), "gmail")
    if not token or token.status != "connected":
        raise HTTPException(status_code=400, detail="Connect Google/Gmail before syncing Google Calendar.")
    scopes = _scope_set(token.scopes)
    if "https://www.googleapis.com/auth/calendar.events" not in scopes:
        raise HTTPException(
            status_code=400,
            detail="Google Calendar permission is missing. Reconnect Gmail/Google so AI Business Builder can request calendar.events scope.",
        )
    token = await manager.refresh_if_needed(token)
    secret = settings.token_encryption_key or settings.encryption_key
    try:
        return _decrypt(token.access_token_enc, secret)
    except Exception:
        return _decrypt(token.access_token_enc, settings.jwt_secret_key)


@router.get("/events")
async def list_calendar_events(
    business_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    result = await db.execute(
        select(MarketingCalendarEvent)
        .where(MarketingCalendarEvent.business_id == business_id)
        .order_by(MarketingCalendarEvent.start_time.asc())
    )
    return [_serialize_event(event) for event in result.scalars().all()]


@router.post("/events", status_code=201)
async def create_calendar_event(
    payload: CalendarEventCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    business = await BusinessService(db).get(payload.business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    event = MarketingCalendarEvent(
        business_id=payload.business_id,
        campaign_id=payload.campaign_id,
        title=payload.title,
        description=payload.description,
        start_time=payload.start_time,
        end_time=payload.end_time,
        platform=payload.platform,
        status="scheduled",
    )
    db.add(event)
    await db.flush()
    if payload.sync_google:
        access_token = await _google_access_token(db, current_user, payload.business_id)
        body = {
            "summary": payload.title,
            "description": payload.description or "",
            "start": {"dateTime": payload.start_time.astimezone(timezone.utc).isoformat()},
            "end": {"dateTime": (payload.end_time or payload.start_time).astimezone(timezone.utc).isoformat()},
        }
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.post(
                "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
                json=body,
            )
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail="Google Calendar rejected the event creation request.")
        event.google_event_id = response.json().get("id")
    await db.commit()
    await db.refresh(event)
    return _serialize_event(event)


@router.post("/sync")
async def sync_google_calendar(
    payload: CalendarSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    business = await BusinessService(db).get(payload.business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    access_token = await _google_access_token(db, current_user, payload.business_id)
    time_min = datetime.now(timezone.utc).isoformat()
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"timeMin": time_min, "singleEvents": "true", "orderBy": "startTime", "maxResults": 50},
        )
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail="Google Calendar sync failed.")
    items = response.json().get("items", [])
    imported = 0
    for item in items:
        google_id = item.get("id")
        if not google_id:
            continue
        existing = await db.execute(
            select(MarketingCalendarEvent.id).where(
                MarketingCalendarEvent.business_id == payload.business_id,
                MarketingCalendarEvent.google_event_id == google_id,
            )
        )
        if existing.scalar_one_or_none():
            continue
        start_raw = (item.get("start") or {}).get("dateTime") or (item.get("start") or {}).get("date")
        if not start_raw:
            continue
        start_time = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
        end_raw = (item.get("end") or {}).get("dateTime") or (item.get("end") or {}).get("date")
        end_time = datetime.fromisoformat(end_raw.replace("Z", "+00:00")) if end_raw else None
        db.add(
            MarketingCalendarEvent(
                business_id=payload.business_id,
                google_event_id=google_id,
                title=item.get("summary") or "Google Calendar event",
                description=item.get("description"),
                start_time=start_time,
                end_time=end_time,
                platform="google_calendar",
                status="synced",
            )
        )
        imported += 1
    await db.commit()
    return {"status": "synced", "imported": imported, "checked": len(items)}
