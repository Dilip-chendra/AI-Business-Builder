"""Tests for the /businesses endpoints."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_generate_business_returns_structured_payload(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/businesses/generate",
        json={"interests": "fitness coaching"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"]
    assert data["headline"]
    assert data["monetization_model"]
    assert data["seo_title"]
    assert data["seo_description"]
    assert "id" in data
    assert "created_at" in data


async def test_generate_business_with_all_fields(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/businesses/generate",
        json={
            "interests": "online education",
            "niche_preferences": "coding bootcamps",
            "target_audience": "career changers",
            "goals": "generate passive income",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["target_audience"]
    assert data["brand_tone"]


async def test_generate_business_sets_active_context(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/businesses/generate",
        json={"interests": "creator tools"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    business = response.json()

    context_response = await client.get("/api/v1/context/active", headers=auth_headers)
    assert context_response.status_code == 200
    payload = context_response.json()
    assert payload["active"]["business_id"] == business["id"]
    assert payload["active"]["workspace_id"] == business["workspace_id"]
    assert payload["active"]["project_id"] == business["project_id"]


async def test_generate_business_missing_interests_returns_422(client: AsyncClient, auth_headers: dict):
    response = await client.post("/api/v1/businesses/generate", json={}, headers=auth_headers)
    assert response.status_code == 422


async def test_list_businesses_empty(client: AsyncClient, auth_headers: dict):
    response = await client.get("/api/v1/businesses", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == []


async def test_list_businesses_after_generation(client: AsyncClient, auth_headers: dict, generated_business: dict):
    response = await client.get("/api/v1/businesses", headers=auth_headers)
    assert response.status_code == 200
    ids = [b["id"] for b in response.json()]
    assert generated_business["id"] in ids


async def test_get_business_by_id(client: AsyncClient, auth_headers: dict, generated_business: dict):
    response = await client.get(f"/api/v1/businesses/{generated_business['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == generated_business["id"]


async def test_get_business_not_found(client: AsyncClient, auth_headers: dict):
    response = await client.get(
        "/api/v1/businesses/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_get_landing_page(client: AsyncClient, generated_business: dict):
    """Landing page is a public endpoint — no auth needed."""
    response = await client.get(f"/api/v1/businesses/{generated_business['id']}/landing-page")
    assert response.status_code == 200
    data = response.json()
    assert data["headline"]
    assert data["cta_text"]
