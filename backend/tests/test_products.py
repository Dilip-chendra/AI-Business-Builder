"""Tests for the /products endpoints."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_product(client: AsyncClient, auth_headers: dict, generated_business: dict):
    response = await client.post(
        "/api/v1/products",
        json={
            "business_id": generated_business["id"],
            "name": "Launch Kit",
            "description": "A practical starter kit for new founders.",
            "price": "29.00",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Launch Kit"
    assert data["price"] == "29.00"
    assert data["currency"] == "usd"
    assert data["category"] == "digital"


async def test_create_product_invalid_price(client: AsyncClient, auth_headers: dict, generated_business: dict):
    response = await client.post(
        "/api/v1/products",
        json={
            "business_id": generated_business["id"],
            "name": "Bad Product",
            "description": "Should fail.",
            "price": "-5.00",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422


async def test_list_products_for_business(
    client: AsyncClient, auth_headers: dict, created_product: dict, generated_business: dict
):
    response = await client.get(
        f"/api/v1/products?business_id={generated_business['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    ids = [p["id"] for p in response.json()]
    assert created_product["id"] in ids


async def test_list_products_all(client: AsyncClient, auth_headers: dict, created_product: dict):
    response = await client.get("/api/v1/products", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_get_product_by_id(client: AsyncClient, auth_headers: dict, created_product: dict):
    response = await client.get(f"/api/v1/products/{created_product['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == created_product["id"]


async def test_get_product_not_found(client: AsyncClient, auth_headers: dict):
    response = await client.get(
        "/api/v1/products/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_update_product_price(client: AsyncClient, auth_headers: dict, created_product: dict):
    response = await client.patch(
        f"/api/v1/products/{created_product['id']}",
        json={"price": "99.00"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["price"] == "99.00"


async def test_update_product_name_and_category(client: AsyncClient, auth_headers: dict, created_product: dict):
    response = await client.patch(
        f"/api/v1/products/{created_product['id']}",
        json={"name": "Premium Kit", "category": "subscription"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Premium Kit"
    assert data["category"] == "subscription"


async def test_duplicate_product(client: AsyncClient, auth_headers: dict, created_product: dict):
    response = await client.post(
        f"/api/v1/products/{created_product['id']}/duplicate",
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] != created_product["id"]
    assert data["name"].endswith("Copy")
    assert data["business_id"] == created_product["business_id"]
    assert data["status"] == "draft"


async def test_update_product_not_found(client: AsyncClient, auth_headers: dict):
    response = await client.patch(
        "/api/v1/products/00000000-0000-0000-0000-000000000000",
        json={"price": "10.00"},
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_delete_product(client: AsyncClient, auth_headers: dict, created_product: dict):
    response = await client.delete(
        f"/api/v1/products/{created_product['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 204
    # Confirm it's gone
    get_response = await client.get(
        f"/api/v1/products/{created_product['id']}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


async def test_delete_product_not_found(client: AsyncClient, auth_headers: dict):
    response = await client.delete(
        "/api/v1/products/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404
