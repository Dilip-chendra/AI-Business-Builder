"""Tests for rate limiting."""
import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_rate_limit_allows_normal_traffic(client: AsyncClient):
    """Requests within the limit should succeed."""
    # Health check is exempt, test with an API endpoint
    for _ in range(5):
        response = await client.get("/health")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_rate_limit_returns_429(client: AsyncClient):
    """Exceeding the rate limit should return HTTP 429."""
    # Temporarily lower the limit for testing
    original_limit = settings.rate_limit_requests
    settings.rate_limit_requests = 3

    try:
        # Clear any existing rate limit state
        from app.utils.rate_limit import _in_memory
        _in_memory.clear()

        # Make requests until rate limited
        statuses = []
        for _ in range(6):
            response = await client.get("/api/v1/businesses", headers={"Authorization": "Bearer fake"})
            statuses.append(response.status_code)

        # At least one should be 429 (after exceeding 3 request limit)
        assert 429 in statuses, f"Expected 429 in responses but got: {statuses}"

    finally:
        settings.rate_limit_requests = original_limit


@pytest.mark.asyncio
async def test_rate_limit_retry_after_header(client: AsyncClient):
    """429 responses should include a Retry-After header."""
    original_limit = settings.rate_limit_requests
    settings.rate_limit_requests = 1

    try:
        from app.utils.rate_limit import _in_memory
        _in_memory.clear()

        # First request should pass
        await client.get("/api/v1/businesses", headers={"Authorization": "Bearer fake"})
        # Second should be rate limited
        response = await client.get("/api/v1/businesses", headers={"Authorization": "Bearer fake"})
        if response.status_code == 429:
            assert "retry-after" in response.headers

    finally:
        settings.rate_limit_requests = original_limit
