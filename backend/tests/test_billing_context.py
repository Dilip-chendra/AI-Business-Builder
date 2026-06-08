import pytest


@pytest.mark.asyncio
async def test_active_context_bootstraps_workspace_and_free_subscription(client, auth_headers):
    response = await client.get("/api/v1/context/active", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["active"]["workspace_id"] is not None
    assert isinstance(payload["workspaces"], list)
    assert len(payload["workspaces"]) >= 1

    sub_response = await client.get("/api/v1/billing/subscription", headers=auth_headers)
    assert sub_response.status_code == 200
    subscription = sub_response.json()
    assert subscription["plan"]["slug"] == "free"
    assert subscription["status"] in {"free", "approval_pending", "active"}


@pytest.mark.asyncio
async def test_billing_plans_seeded_and_visible(client, auth_headers):
    response = await client.get("/api/v1/billing/plans", headers=auth_headers)
    assert response.status_code == 200
    plans = response.json()
    slugs = {plan["slug"] for plan in plans}
    assert {"free", "pro_monthly", "pro_yearly", "team_monthly"}.issubset(slugs)


@pytest.mark.asyncio
async def test_setting_active_business_updates_context(client, auth_headers, generated_business):
    current = await client.get("/api/v1/context/active", headers=auth_headers)
    assert current.status_code == 200
    workspace_id = current.json()["active"]["workspace_id"]

    response = await client.put(
        "/api/v1/context/active",
        json={
            "workspace_id": workspace_id,
            "business_id": generated_business["id"],
            "project_id": None,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["active"]["business_id"] == generated_business["id"]
