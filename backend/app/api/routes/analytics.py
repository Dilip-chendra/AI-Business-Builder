from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.analytics import AnalyticsDashboardRead, AnalyticsEventCreate, AnalyticsSummaryRead
from app.services.analytics_service import AnalyticsService
from app.services.business_service import BusinessService
from app.core.cache import cache

router = APIRouter()


@router.post("/track", status_code=status.HTTP_202_ACCEPTED)
async def track_event(payload: AnalyticsEventCreate, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Public endpoint — tracking pixels / JS clients call this without auth."""
    await AnalyticsService(db).track(payload)
    # Invalidate cached summary so next fetch is fresh
    await cache.delete(f"analytics:summary:{payload.business_id}")
    await cache.delete(f"analytics:dashboard:{payload.business_id}")
    return {"status": "tracked"}


@router.get("/{business_id}", response_model=AnalyticsSummaryRead)
async def get_summary(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSummaryRead:
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Business not found")

    cache_key = f"analytics:summary:{business_id}:{current_user.id}"
    cached = await cache.get(cache_key)
    if cached:
        return AnalyticsSummaryRead.model_validate(cached)

    result = await AnalyticsService(db).summary(business_id)
    await cache.set(cache_key, result.model_dump(), ttl=60)  # 60s cache
    return result


@router.get("/{business_id}/dashboard", response_model=AnalyticsDashboardRead)
async def get_dashboard_summary(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsDashboardRead:
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Business not found")

    cache_key = f"analytics:dashboard:{business_id}:{current_user.id}"
    cached = await cache.get(cache_key)
    if cached:
        return AnalyticsDashboardRead.model_validate(cached)

    result = await AnalyticsService(db).dashboard_summary(business_id)
    await cache.set(cache_key, result.model_dump(), ttl=60)
    return result
