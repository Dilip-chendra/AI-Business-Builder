"""File upload endpoint for product images."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.business_service import BusinessService
from app.services.product_service import ProductService
from app.services.upload_service import UploadService

router = APIRouter()

_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
_ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


@router.post("/product/{product_id}/image")
async def upload_product_image(
    product_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload an image for a product and store the public URL."""
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type. Allowed: {', '.join(_ALLOWED_TYPES)}",
        )

    data = await file.read()
    if len(data) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File too large. Maximum size is 5 MB.",
        )

    product = await ProductService(db).get(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    # Verify business ownership
    business = await BusinessService(db).get(product.business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    url = await UploadService().upload_product_image(
        file_bytes=data,
        filename=file.filename or "image.jpg",
        content_type=file.content_type,
    )

    # Persist the URL on the product
    from app.schemas.product import ProductUpdate
    await ProductService(db).update(product_id, ProductUpdate(image_url=url))

    return {"url": url, "product_id": str(product_id)}
