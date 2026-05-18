"""Tests for infrastructure endpoints."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "env" in data


async def test_request_id_header_present(client: AsyncClient):
    response = await client.get("/health")
    assert "x-request-id" in response.headers


async def test_request_id_echoed_when_provided(client: AsyncClient):
    response = await client.get("/health", headers={"X-Request-ID": "test-trace-123"})
    assert response.headers.get("x-request-id") == "test-trace-123"
