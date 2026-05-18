from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.analytics import AnalyticsEventCreate
from app.schemas.business import BusinessCreate, BusinessGenerateRequest, BusinessRead
from app.services.analytics_service import AnalyticsService
from app.services.ai_service import AIProviderError
from app.services.business_service import BusinessService
from app.services.email_service import EmailService
from app.services.usage_service import UsageService
from app.core.cache import cache

router = APIRouter()


@router.post("/generate", response_model=BusinessRead, status_code=status.HTTP_201_CREATED)
async def generate_business(
    payload: BusinessGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessRead:
    await UsageService(db).check_limit(current_user.id, "ai_request")
    try:
        business = await BusinessService(db).generate_and_store(payload, user_id=current_user.id)
    except AIProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    await UsageService(db).increment_usage(
        current_user.id,
        "ai_request",
        business_id=business.id,
        source="business_generate",
        metadata_json={"business_id": str(business.id)},
    )
    background_tasks.add_task(AnalyticsService(db).ensure_business_analytics, business.id)
    await AnalyticsService(db).track(
        AnalyticsEventCreate(
            business_id=business.id,
            event_type="business_created",
            source="generator",
            metadata_json={
                "business_id": str(business.id),
                "workspace_id": str(business.workspace_id) if business.workspace_id else None,
            },
        )
    )
    background_tasks.add_task(
        EmailService().send_business_created,
        to=current_user.email,
        business_name=business.name,
        business_id=str(business.id),
    )
    # Invalidate business list cache
    await cache.delete(f"businesses:list:{current_user.id}")
    return business


@router.post("", response_model=BusinessRead, status_code=status.HTTP_201_CREATED)
async def create_business(
    payload: BusinessCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessRead:
    result = await BusinessService(db).create(payload, user_id=current_user.id)
    await AnalyticsService(db).track(
        AnalyticsEventCreate(
            business_id=result.id,
            event_type="business_created",
            source="manual_create",
            metadata_json={
                "business_id": str(result.id),
                "workspace_id": str(result.workspace_id) if result.workspace_id else None,
            },
        )
    )
    await cache.delete(f"businesses:list:{current_user.id}")
    return result


@router.get("", response_model=list[BusinessRead])
async def list_businesses(
    workspace_id: UUID | None = None,
    project_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[BusinessRead]:
    cache_key = f"businesses:list:{current_user.id}:{workspace_id}:{project_id}"
    cached = await cache.get(cache_key)
    if cached:
        return [BusinessRead.model_validate(b) for b in cached]
    
    from sqlalchemy import select, func
    from app.models.business import Business
    from app.models.product import Product
    
    query = (
        select(Business, func.count(Product.id).label("product_count"))
        .outerjoin(Product, Business.id == Product.business_id)
        .where(Business.user_id == current_user.id)
        .group_by(Business.id)
        .order_by(Business.created_at.desc())
    )
    if workspace_id:
        query = query.where(Business.workspace_id == workspace_id)
    if project_id:
        query = query.where(Business.project_id == project_id)
    result = await db.execute(query)
    rows = result.all()
    
    business_reads = []
    for business_obj, count in rows:
        b_read = BusinessRead.model_validate(business_obj)
        b_read.product_count = count
        business_reads.append(b_read)
        
    await cache.set(cache_key, [b.model_dump(mode="json") for b in business_reads], ttl=120)
    return business_reads


@router.get("/{business_id}", response_model=BusinessRead)
async def get_business(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BusinessRead:
    cache_key = f"business:{business_id}:{current_user.id}"
    cached = await cache.get(cache_key)
    if cached:
        return BusinessRead.model_validate(cached)
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")
        
    from sqlalchemy import select, func
    from app.models.product import Product
    count_res = await db.execute(select(func.count(Product.id)).where(Product.business_id == business.id))
    
    b_read = BusinessRead.model_validate(business)
    b_read.product_count = count_res.scalar() or 0
    
    await cache.set(cache_key, b_read.model_dump(mode="json"), ttl=120)
    return b_read


async def _get_landing_page_impl(*, business_id: UUID, preview: bool, db: AsyncSession) -> BusinessRead:
    cache_key = f"landing:{business_id}"
    if not preview:
        cached = await cache.get(cache_key)
        if cached:
            return BusinessRead.model_validate(cached)
    business = await BusinessService(db).get(business_id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Landing page not found")
    business_read = BusinessRead.model_validate(business)
    if not preview:
        await cache.set(cache_key, business_read.model_dump(mode="json"), ttl=300)  # 5 min cache for public pages
    return business_read


@router.get("/{business_id}/landing-page", response_model=BusinessRead)
async def get_landing_page(business_id: UUID, db: AsyncSession = Depends(get_db)) -> BusinessRead:
    """Public endpoint — landing pages are visible to anyone."""
    return await _get_landing_page_impl(business_id=business_id, preview=False, db=db)


@router.get("/{business_id}/landing-page-preview", response_model=BusinessRead)
async def get_landing_page_preview(business_id: UUID, db: AsyncSession = Depends(get_db)) -> BusinessRead:
    """Preview endpoint that bypasses public cache for studio/editor refreshes."""
    return await _get_landing_page_impl(business_id=business_id, preview=True, db=db)


@router.get("/{business_id}/products-public")
async def get_business_products_public(
    business_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list:
    """Public endpoint — returns products for a business landing page (no auth required)."""
    cache_key = f"products:public:{business_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached
    from app.services.product_service import ProductService
    products = await ProductService(db).list(business_id)
    result = [
        {
            "id": str(p.id),
            "name": p.name,
            "description": p.description,
            "price": str(p.price),
            "currency": p.currency,
            "category": p.category,
        }
        for p in products
    ]
    await cache.set(cache_key, result, ttl=300)
    return result
