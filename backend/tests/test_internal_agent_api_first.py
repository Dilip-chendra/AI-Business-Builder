import json

import pytest


def _events_from_sse(text: str) -> list[dict]:
    events: list[dict] = []
    for line in text.splitlines():
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line.removeprefix("data: ")))
    return events


@pytest.mark.anyio
async def test_internal_agent_escalates_empty_products_to_api_first_research(client, auth_headers, generated_business):
    token = auth_headers["Authorization"].removeprefix("Bearer ")

    response = await client.get(
        "/api/v1/agent/stream",
        params={
            "goal": "Find top 3 competitors pricing for AI SaaS tools",
            "mode": "internal",
            "business_id": generated_business["id"],
            "max_steps": 12,
            "token": token,
        },
    )

    assert response.status_code == 200
    events = _events_from_sse(response.text)
    steps = [event for event in events if event["type"] == "step"]
    result = next(event for event in events if event["type"] == "result")
    done = events[-1]

    list_product_steps = [event for event in steps if event.get("action") == "list_products"]
    assert len(list_product_steps) == 1
    assert any(event.get("strategy") == "internal_agent_router" for event in events if event["type"] == "thinking")
    assert any(event.get("tool") == "Browser Agent Route" for event in steps)
    assert result["text"]
    assert "No products found" not in result["text"]
    assert "Live Website Evidence Required" in result["text"]
    assert result["status"] == "needs_browser_agent"
    assert result["report"]["status"] == "needs_browser_agent"
    assert result["report"]["next_action"]["action"] == "run_browser_agent"
    assert result["evidence"] == []
    assert done["status"] == "needs_browser_agent"
    assert done["state"] == "needs_browser_agent"


@pytest.mark.anyio
async def test_agent_run_controller_uses_api_first_research_for_empty_products(client, auth_headers, generated_business):
    response = await client.post(
        "/api/v1/agent/run",
        json={
            "goal": "Find top 3 competitors pricing for AI SaaS tools",
            "business_id": generated_business["id"],
            "apply_actions": False,
            "max_steps": 8,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["result"]
    assert "No products found" not in data["result"]
    assert "live website evidence required" in data["result"].lower()

    product_steps = [step for step in data["steps"] if step.get("action") == "list_products"]
    assert len(product_steps) == 1
    assert any(step.get("strategy") == "browser_required" for step in data["steps"])


@pytest.mark.anyio
async def test_internal_agent_completes_seo_keyword_suggestions_with_ai_reasoning(client, auth_headers, generated_business):
    token = auth_headers["Authorization"].removeprefix("Bearer ")
    response = await client.get(
        "/api/v1/agent/stream",
        params={
            "goal": "Find SEO keywords for fitness coaching businesses",
            "mode": "internal",
            "business_id": generated_business["id"],
            "max_steps": 12,
            "token": token,
        },
    )

    assert response.status_code == 200
    events = _events_from_sse(response.text)
    steps = [event for event in events if event["type"] == "step"]
    result = next(event for event in events if event["type"] == "result")

    assert not any("manual research" in str(step.get("thought", "")).lower() for step in steps)
    assert not any(str(step.get("action")) == "none" for step in steps)
    assert "live website evidence required" not in result["text"].lower()
    assert "insufficient evidence" not in result["text"].lower()
    assert result["status"] == "completed"
    assert result["report"]["evidence_type"] == "ai_reasoning"
    assert result["report"]["confidence"] > 0
    assert result["evidence"] == []
    assert events[-1]["state"] == "completed"


@pytest.mark.anyio
async def test_internal_agent_routes_current_pricing_to_browser_without_fake_values(client, auth_headers, generated_business):
    token = auth_headers["Authorization"].removeprefix("Bearer ")
    response = await client.get(
        "/api/v1/agent/stream",
        params={
            "goal": "Analyze pricing strategies for online course platforms",
            "mode": "internal",
            "business_id": generated_business["id"],
            "max_steps": 12,
            "token": token,
        },
    )

    assert response.status_code == 200
    events = _events_from_sse(response.text)
    result = next(event for event in events if event["type"] == "result")

    text = result["text"].lower()
    assert "live website evidence required" not in text
    assert result["status"] == "completed"
    assert result["report"]["evidence_type"] == "ai_reasoning"


@pytest.mark.anyio
async def test_internal_agent_routes_current_competitor_pricing_to_browser(client, auth_headers, generated_business):
    token = auth_headers["Authorization"].removeprefix("Bearer ")
    response = await client.get(
        "/api/v1/agent/stream",
        params={
            "goal": "Find current pricing for Jasper AI",
            "mode": "internal",
            "business_id": generated_business["id"],
            "max_steps": 12,
            "token": token,
        },
    )

    assert response.status_code == 200
    events = _events_from_sse(response.text)
    result = next(event for event in events if event["type"] == "result")

    text = result["text"].lower()
    assert "live website evidence required" in text
    assert result["status"] == "needs_browser_agent"
    assert len(result["evidence"]) == 0
    assert result["progress"]["progress_score"] == 0
    assert result["progress"]["useful_sources"] == 0
    assert events[-1]["state"] == "needs_browser_agent"
