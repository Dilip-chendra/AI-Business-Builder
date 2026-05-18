"""Tests for the /payments endpoints."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_checkout_session_created_without_stripe(
    client: AsyncClient, auth_headers: dict, created_product: dict
):
    """When STRIPE_SECRET_KEY is not set the service returns a local mock URL."""
    response = await client.post(
        "/api/v1/payments/checkout",
        json={"product_id": created_product["id"]},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "checkout_url" in data
    assert "session_id" in data
    # Local fallback URL contains the product id
    assert created_product["id"] in data["session_id"] or "local_" in data["session_id"]


async def test_checkout_session_product_not_found(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/payments/checkout",
        json={"product_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_checkout_session_invalid_quantity(
    client: AsyncClient, auth_headers: dict, created_product: dict
):
    response = await client.post(
        "/api/v1/payments/checkout",
        json={"product_id": created_product["id"], "quantity": 0},
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_list_orders_empty(client: AsyncClient, auth_headers: dict, generated_business: dict):
    response = await client.get(
        f"/api/v1/payments/orders/{generated_business['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_webhook_ignored_when_stripe_not_configured(client: AsyncClient):
    """Webhook endpoint should return 202 and silently skip when Stripe is not set up. Public."""
    response = await client.post(
        "/api/v1/payments/webhook",
        content=b'{"type":"checkout.session.completed"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 202
