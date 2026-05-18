"""Tests for the /analytics endpoints."""
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_track_event(client: AsyncClient, generated_business: dict):
    """Track event is public — no auth needed."""
    response = await client.post(
        "/api/v1/analytics/track",
        json={
            "business_id": generated_business["id"],
            "event_type": "visit",
            "source": "direct",
        },
    )
    assert response.status_code == 202
    assert response.json()["status"] == "tracked"


async def test_track_event_with_product(client: AsyncClient, created_product: dict, generated_business: dict):
    response = await client.post(
        "/api/v1/analytics/track",
        json={
            "business_id": generated_business["id"],
            "product_id": created_product["id"],
            "event_type": "click",
            "source": "landing_page",
            "value_cents": 0,
        },
    )
    assert response.status_code == 202


async def test_track_event_invalid_value_cents(client: AsyncClient, generated_business: dict):
    response = await client.post(
        "/api/v1/analytics/track",
        json={
            "business_id": generated_business["id"],
            "event_type": "click",
            "value_cents": -1,
        },
    )
    assert response.status_code == 422


async def test_analytics_summary_empty(client: AsyncClient, auth_headers: dict, generated_business: dict):
    response = await client.get(
        f"/api/v1/analytics/{generated_business['id']}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["visitors"] == 0
    assert data["clicks"] == 0
    assert data["conversions"] == 0
    assert data["revenue_cents"] == 0
    assert data["conversion_rate"] == 0.0


async def test_analytics_summary_counts_events(client: AsyncClient, auth_headers: dict, generated_business: dict):
    business_id = generated_business["id"]

    # Track 3 visits, 2 clicks, 1 conversion (track is public)
    for _ in range(3):
        await client.post(
            "/api/v1/analytics/track",
            json={"business_id": business_id, "event_type": "visit"},
        )
    for _ in range(2):
        await client.post(
            "/api/v1/analytics/track",
            json={"business_id": business_id, "event_type": "click"},
        )
    await client.post(
        "/api/v1/analytics/track",
        json={"business_id": business_id, "event_type": "conversion", "value_cents": 4900},
    )

    response = await client.get(f"/api/v1/analytics/{business_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["visitors"] == 3
    assert data["clicks"] == 2
    assert data["conversions"] == 1
    assert abs(data["conversion_rate"] - (1 / 3)) < 0.001


async def test_analytics_summary_has_product_performance(
    client: AsyncClient, auth_headers: dict, generated_business: dict, created_product: dict
):
    business_id = generated_business["id"]
    product_id = created_product["id"]

    await client.post(
        "/api/v1/analytics/track",
        json={"business_id": business_id, "product_id": product_id, "event_type": "click"},
    )

    response = await client.get(f"/api/v1/analytics/{business_id}", headers=auth_headers)
    assert response.status_code == 200
    perf = response.json()["product_performance"]
    assert any(p["product_id"] == product_id for p in perf)
