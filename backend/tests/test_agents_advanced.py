"""Tests for the agent system — coordinator, execution, and logging."""
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_agent_pipeline_runs(client: AsyncClient, auth_headers: dict, generated_business: dict):
    """Running the agent pipeline should return decisions and insights."""
    business_id = generated_business["id"]
    response = await client.post(
        f"/api/v1/agents/{business_id}/run",
        json={"apply_decisions": False},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "analytics" in data
    assert "strategy" in data
    assert "marketing" in data
    assert "optimization" in data
    assert "execution" in data
    assert "summary" in data
    assert isinstance(data["summary"]["total_decisions"], int)


@pytest.mark.asyncio
async def test_agent_pipeline_with_apply(client: AsyncClient, auth_headers: dict, generated_business: dict):
    """Running with apply_decisions=True should produce applied actions."""
    business_id = generated_business["id"]
    # First track some visits to give agents data to work with
    for _ in range(10):
        await client.post(
            "/api/v1/analytics/track",
            json={"business_id": business_id, "event_type": "visit"},
        )

    response = await client.post(
        f"/api/v1/agents/{business_id}/run",
        json={"apply_decisions": True},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["apply_decisions"] is True


@pytest.mark.asyncio
async def test_agent_logs_created(client: AsyncClient, auth_headers: dict, generated_business: dict):
    """Running the agent pipeline should create log entries."""
    business_id = generated_business["id"]
    # Run pipeline
    await client.post(
        f"/api/v1/agents/{business_id}/run",
        json={"apply_decisions": False},
        headers=auth_headers,
    )

    # Check logs exist
    response = await client.get(
        f"/api/v1/agents/{business_id}/logs",
        headers=auth_headers,
    )
    assert response.status_code == 200
    logs = response.json()
    assert isinstance(logs, list)
    assert len(logs) > 0  # Coordinator always creates at least one log


@pytest.mark.asyncio
async def test_agent_logs_filter_by_type(client: AsyncClient, auth_headers: dict, generated_business: dict):
    """Agent logs can be filtered by agent_type."""
    business_id = generated_business["id"]
    await client.post(
        f"/api/v1/agents/{business_id}/run",
        json={"apply_decisions": False},
        headers=auth_headers,
    )

    response = await client.get(
        f"/api/v1/agents/{business_id}/logs",
        params={"agent_type": "coordinator"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    logs = response.json()
    for log in logs:
        assert log["agent_type"] == "coordinator"


@pytest.mark.asyncio
async def test_agent_pipeline_requires_auth(client: AsyncClient, generated_business: dict):
    """Agent pipeline should require authentication."""
    business_id = generated_business["id"]
    response = await client.post(
        f"/api/v1/agents/{business_id}/run",
        json={"apply_decisions": False},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_agent_pipeline_wrong_business(client: AsyncClient, auth_headers: dict):
    """Agent pipeline should return 404 for nonexistent business."""
    response = await client.post(
        "/api/v1/agents/00000000-0000-0000-0000-000000000999/run",
        json={"apply_decisions": False},
        headers=auth_headers,
    )
    assert response.status_code == 404
