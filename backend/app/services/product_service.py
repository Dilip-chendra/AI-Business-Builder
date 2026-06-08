from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate


class ProductService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, payload: ProductCreate) -> Product:
        product = Product(**payload.model_dump())
        self.db.add(product)
        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def list(self, business_id: UUID | None = None, project_id: UUID | None = None) -> list[Product]:
        query = select(Product).order_by(Product.created_at.desc())
        if business_id:
            query = query.where(Product.business_id == business_id)
        if project_id:
            query = query.where(Product.project_id == project_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get(self, product_id: UUID) -> Product | None:
        return await self.db.get(Product, product_id)

    async def update(self, product_id: UUID, payload: ProductUpdate) -> Product | None:
        product = await self.get(product_id)
        if not product:
            return None
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(product, key, value)
        await self.db.commit()
        await self.db.refresh(product)
        return product

    async def duplicate(self, product_id: UUID) -> Product | None:
        product = await self.get(product_id)
        if not product:
            return None
        duplicated = Product(
            business_id=product.business_id,
            project_id=product.project_id,
            name=f"{product.name} Copy",
            description=product.description,
            price=product.price,
            currency=product.currency,
            category=product.category,
            status="draft",
            product_type=product.product_type,
            image_url=product.image_url,
            purchase_link=product.purchase_link,
            stripe_price_id=product.stripe_price_id,
            payment_provider=product.payment_provider,
            paypal_product_id=product.paypal_product_id,
            paypal_plan_id=product.paypal_plan_id,
            paypal_checkout_url=product.paypal_checkout_url,
            billing_type=product.billing_type,
        )
        self.db.add(duplicated)
        await self.db.commit()
        await self.db.refresh(duplicated)
        return duplicated

    async def delete(self, product_id: UUID) -> bool:
        product = await self.get(product_id)
        if not product:
            return False
        await self.db.delete(product)
        await self.db.commit()
        return True
