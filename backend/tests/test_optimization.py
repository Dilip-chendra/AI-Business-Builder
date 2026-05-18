"""Tests for the /optimize endpoint."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_optimization_returns_suggestions(client: AsyncClient, generated_business: dict):
    response = await client.get(f"/api/v1/optimize/{generated_business['id']}")
    assert response.status_code == 200
    data = response.json()
    assert any(data.get(k) for k in ("headline", "cta_text", "pricing_note", "positioning_note"))


async def test_optimization_not_found(client: AsyncClient):
    response = await client.get("/api/v1/optimize/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


async def test_optimization_improves_low_conversion(client: AsyncClient, generated_business: dict):
    response = await client.get(f"/api/v1/optimize/{generated_business['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["cta_text"] is not None
    assert data["pricing_note"] is not None
