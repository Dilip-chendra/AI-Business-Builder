from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.agent import AgentLog
from app.models.ai_studio import AIStudioMessage
from app.models.analytics import AnalyticsEvent
from app.models.code_version import CodeVersion
from app.models.marketing import MarketingCampaign
from app.models.product import Product
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


@router.get("/{business_id}/operating-summary")
async def get_operating_summary(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return real cross-module activity for the active business dashboard."""
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Business not found")

    async def count(query) -> int:
        result = await db.execute(query)
        return int(result.scalar() or 0)

    product_count = await count(select(func.count(Product.id)).where(Product.business_id == business_id))
    campaign_count = await count(select(func.count(MarketingCampaign.id)).where(MarketingCampaign.business_id == business_id))
    agent_report_count = await count(
        select(func.count(AgentLog.id)).where(AgentLog.business_id == business_id, AgentLog.log_type == "report")
    )
    studio_action_count = await count(
        select(func.count(AIStudioMessage.id)).where(
            AIStudioMessage.business_id == str(business_id),
            AIStudioMessage.role == "assistant",
            AIStudioMessage.action_type.is_not(None),
        )
    )
    code_version_count = await count(select(func.count(CodeVersion.id)).where(CodeVersion.business_id == str(business_id)))
    analytics_event_count = await count(select(func.count(AnalyticsEvent.id)).where(AnalyticsEvent.business_id == business_id))

    recent_campaigns_result = await db.execute(
        select(MarketingCampaign)
        .where(MarketingCampaign.business_id == business_id)
        .order_by(MarketingCampaign.created_at.desc())
        .limit(4)
    )
    recent_reports_result = await db.execute(
        select(AgentLog)
        .where(AgentLog.business_id == business_id, AgentLog.log_type == "report")
        .order_by(AgentLog.created_at.desc())
        .limit(4)
    )
    recent_studio_result = await db.execute(
        select(AIStudioMessage)
        .where(
            AIStudioMessage.business_id == str(business_id),
            AIStudioMessage.role == "assistant",
            AIStudioMessage.action_type.is_not(None),
        )
        .order_by(AIStudioMessage.created_at.desc())
        .limit(4)
    )

    recent_activity: list[dict] = []
    for campaign in recent_campaigns_result.scalars().all():
        recent_activity.append(
            {
                "id": str(campaign.id),
                "type": "campaign",
                "label": campaign.name,
                "detail": f"{campaign.campaign_type.replace('_', ' ')} - {campaign.status}",
                "href": f"/marketing?tab=campaigns&campaign_id={campaign.id}&business_id={business_id}",
                "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
            }
        )
    for report in recent_reports_result.scalars().all():
        payload = report.payload or {}
        recent_activity.append(
            {
                "id": str(report.id),
                "type": "agent_report",
                "label": str(payload.get("goal") or report.summary),
                "detail": report.agent_type.replace("_", " "),
                "href": f"/agent-live?business_id={business_id}",
                "created_at": report.created_at.isoformat() if report.created_at else None,
            }
        )
    for message in recent_studio_result.scalars().all():
        recent_activity.append(
            {
                "id": str(message.id),
                "type": "studio_action",
                "label": message.content,
                "detail": (message.action_type or "AI Studio").replace("_", " "),
                "href": "/ai-studio",
                "created_at": message.created_at.isoformat() if message.created_at else None,
            }
        )
    recent_activity.sort(key=lambda item: item.get("created_at") or "", reverse=True)

    return {
        "business_id": str(business_id),
        "counts": {
            "products": product_count,
            "campaigns": campaign_count,
            "agent_reports": agent_report_count,
            "studio_actions": studio_action_count,
            "code_versions": code_version_count,
            "analytics_events": analytics_event_count,
        },
        "recent_activity": recent_activity[:8],
    }


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
