"""Internal tools — operate on the platform's own database and services.

These tools give the agent the ability to read and write business data,
products, analytics, and trigger platform features.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.agents.tools.registry import ToolDefinition, ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


# ── Tool handlers ─────────────────────────────────────────────────────────────

async def _get_business(params: dict, db=None, **_) -> ToolResult:
    if db is None:
        return ToolResult(success=False, error="No database session provided", tool_name="get_business")
    try:
        from app.services.business_service import BusinessService
        business_id = params.get("business_id")
        if not business_id:
            return ToolResult(success=False, error="business_id is required", tool_name="get_business")
        business = await BusinessService(db).get(UUID(str(business_id)))
        if not business:
            return ToolResult(success=False, error=f"Business {business_id} not found", tool_name="get_business")
        return ToolResult(
            success=True,
            tool_name="get_business",
            data={
                "id": str(business.id),
                "name": business.name,
                "niche": business.niche,
                "headline": business.headline,
                "cta_text": business.cta_text,
                "target_audience": business.target_audience,
                "monetization_model": business.monetization_model,
            },
        )
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), tool_name="get_business")


async def _list_products(params: dict, db=None, **_) -> ToolResult:
    if db is None:
        return ToolResult(success=False, error="No database session provided", tool_name="list_products")
    try:
        from app.services.product_service import ProductService
        business_id = params.get("business_id")
        bid = UUID(str(business_id)) if business_id else None
        products = await ProductService(db).list(bid)
        return ToolResult(
            success=True,
            tool_name="list_products",
            data=[
                {
                    "id": str(p.id),
                    "name": p.name,
                    "price": str(p.price),
                    "category": p.category,
                    "description": p.description[:200],
                }
                for p in products
            ],
        )
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), tool_name="list_products")


async def _create_product(params: dict, db=None, **_) -> ToolResult:
    if db is None:
        return ToolResult(success=False, error="No database session provided", tool_name="create_product")
    try:
        from decimal import Decimal
        from app.schemas.product import ProductCreate
        from app.services.product_service import ProductService
        payload = ProductCreate(
            business_id=UUID(str(params["business_id"])),
            name=params["name"],
            description=params.get("description", "AI-generated product"),
            price=Decimal(str(params.get("price", "29.00"))),
            currency=params.get("currency", "usd"),
            category=params.get("category", "digital"),
        )
        product = await ProductService(db).create(payload)
        return ToolResult(
            success=True,
            tool_name="create_product",
            data={"id": str(product.id), "name": product.name, "price": str(product.price)},
        )
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), tool_name="create_product")


async def _update_product(params: dict, db=None, **_) -> ToolResult:
    if db is None:
        return ToolResult(success=False, error="No database session provided", tool_name="update_product")
    try:
        from app.schemas.product import ProductUpdate
        from app.services.product_service import ProductService
        product_id = UUID(str(params["product_id"]))
        update = ProductUpdate(**{k: v for k, v in params.items() if k != "product_id"})
        product = await ProductService(db).update(product_id, update)
        if not product:
            return ToolResult(success=False, error="Product not found", tool_name="update_product")
        return ToolResult(
            success=True,
            tool_name="update_product",
            data={"id": str(product.id), "name": product.name, "price": str(product.price)},
        )
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), tool_name="update_product")


async def _get_analytics(params: dict, db=None, **_) -> ToolResult:
    if db is None:
        return ToolResult(success=False, error="No database session provided", tool_name="get_analytics")
    try:
        from app.services.analytics_service import AnalyticsService
        business_id = UUID(str(params["business_id"]))
        summary = await AnalyticsService(db).summary(business_id)
        return ToolResult(
            success=True,
            tool_name="get_analytics",
            data={
                "visitors": summary.visitors,
                "clicks": summary.clicks,
                "conversions": summary.conversions,
                "revenue_cents": summary.revenue_cents,
                "conversion_rate": summary.conversion_rate,
            },
        )
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), tool_name="get_analytics")


async def _update_business_field(params: dict, db=None, **_) -> ToolResult:
    if db is None:
        return ToolResult(success=False, error="No database session provided", tool_name="update_business_field")
    try:
        from app.models.business import Business
        business_id = UUID(str(params["business_id"]))
        field = params["field"]
        new_value = params["new_value"]
        business = await db.get(Business, business_id)
        if not business:
            return ToolResult(success=False, error="Business not found", tool_name="update_business_field")
        old_value = getattr(business, field, None)
        setattr(business, field, new_value)
        await db.commit()
        return ToolResult(
            success=True,
            tool_name="update_business_field",
            data={"field": field, "old_value": old_value, "new_value": new_value},
        )
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), tool_name="update_business_field")


async def _send_email(params: dict, **_) -> ToolResult:
    try:
        from app.services.email_service import EmailService
        svc = EmailService()
        await svc.send(
            to=params["to"],
            subject=params["subject"],
            html_body=params.get("body", params.get("html_body", "")),
        )
        return ToolResult(success=True, tool_name="send_email", data={"to": params["to"]})
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), tool_name="send_email")


# ── Registration ──────────────────────────────────────────────────────────────

def register_internal_tools() -> None:
    """Register all internal tools into the global ToolRegistry (idempotent)."""
    registry = ToolRegistry.get()
    if not registry.register_category("internal"):
        return  # Already registered

    registry.register(ToolDefinition(
        name="get_business",
        description="Fetch business details by ID",
        category="internal",
        params_schema={"business_id": "string (UUID)"},
        handler=_get_business,
    ))
    registry.register(ToolDefinition(
        name="list_products",
        description="List products for a business",
        category="internal",
        params_schema={"business_id": "string (UUID, optional)"},
        handler=_list_products,
    ))
    registry.register(ToolDefinition(
        name="create_product",
        description="Create a new product for a business",
        category="internal",
        params_schema={
            "business_id": "string (UUID)",
            "name": "string",
            "description": "string",
            "price": "number",
            "category": "string (optional)",
        },
        handler=_create_product,
    ))
    registry.register(ToolDefinition(
        name="update_product",
        description="Update an existing product",
        category="internal",
        params_schema={"product_id": "string (UUID)", "name": "string (optional)", "price": "number (optional)"},
        handler=_update_product,
    ))
    registry.register(ToolDefinition(
        name="get_analytics",
        description="Get analytics summary for a business",
        category="internal",
        params_schema={"business_id": "string (UUID)"},
        handler=_get_analytics,
    ))
    registry.register(ToolDefinition(
        name="update_business_field",
        description="Update a specific field on a business (headline, cta_text, etc.)",
        category="internal",
        params_schema={
            "business_id": "string (UUID)",
            "field": "string (headline|cta_text|subheading|description|brand_tone|seo_title|seo_description)",
            "new_value": "string",
        },
        handler=_update_business_field,
    ))
    registry.register(ToolDefinition(
        name="send_email",
        description="Send an email notification",
        category="internal",
        params_schema={"to": "string (email)", "subject": "string", "body": "string"},
        handler=_send_email,
        requires_confirmation=True,
    ))
