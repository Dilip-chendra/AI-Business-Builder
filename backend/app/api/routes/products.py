from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.analytics import AnalyticsEventCreate
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate
from app.services.analytics_service import AnalyticsService
from app.services.business_service import BusinessService
from app.services.product_service import ProductService

router = APIRouter()


async def _verify_business_ownership(
    business_id: UUID, user: User, db: AsyncSession
) -> None:
    """Raise 404 if the business doesn't belong to the current user."""
    business = await BusinessService(db).get(business_id, user_id=user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business not found")


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProductRead:
    await _verify_business_ownership(payload.business_id, current_user, db)
    product = await ProductService(db).create(payload)
    await AnalyticsService(db).track(
        AnalyticsEventCreate(
            business_id=product.business_id,
            product_id=product.id,
            event_type="product_created",
            source="products_page",
            metadata_json={"product_name": product.name, "status": product.status, "product_type": product.product_type},
        )
    )
    return product


@router.get("", response_model=list[ProductRead])
async def list_products(
    business_id: UUID | None = None,
    project_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProductRead]:
    if business_id:
        await _verify_business_ownership(business_id, current_user, db)
    return await ProductService(db).list(business_id, project_id)


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProductRead:
    product = await ProductService(db).get(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await _verify_business_ownership(product.business_id, current_user, db)
    return product


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProductRead:
    product = await ProductService(db).get(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await _verify_business_ownership(product.business_id, current_user, db)
    updated = await ProductService(db).update(product_id, payload)
    return updated


@router.post("/{product_id}/duplicate", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def duplicate_product(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProductRead:
    product = await ProductService(db).get(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await _verify_business_ownership(product.business_id, current_user, db)
    duplicated = await ProductService(db).duplicate(product_id)
    if not duplicated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await AnalyticsService(db).track(
        AnalyticsEventCreate(
            business_id=duplicated.business_id,
            product_id=duplicated.id,
            event_type="product_duplicated",
            source="products_page",
            metadata_json={"source_product_id": str(product_id), "product_name": duplicated.name},
        )
    )
    return duplicated


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    product = await ProductService(db).get(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await _verify_business_ownership(product.business_id, current_user, db)
    await ProductService(db).delete(product_id)
