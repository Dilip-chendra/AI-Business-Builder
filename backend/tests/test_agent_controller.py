"""Tests for the AgentController and ToolExecutor."""
import pytest
from httpx import AsyncClient

from app.agents.safety.permissions import Role
from app.agents.safety.cost_tracker import CostTracker, CostLimitExceededError
from app.agents.tools.registry import ToolRegistry, ToolDefinition, ToolResult
from app.agents.tools.executor import ToolExecutor

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def reset_tool_registry():
    """Reset the ToolRegistry singleton between tests to prevent pollution."""
    # Save original state
    original_tools = dict(ToolRegistry._tools)
    original_categories = set(ToolRegistry._registered_categories)
    yield
    # Restore original state
    ToolRegistry._tools = original_tools
    ToolRegistry._registered_categories = original_categories


# ── ToolExecutor tests ────────────────────────────────────────────────────────

async def test_executor_blocks_unregistered_tool():
    """ToolExecutor returns failure for tools not in the registry."""
    tracker = CostTracker()
    executor = ToolExecutor(role=Role.USER, cost_tracker=tracker)
    result = await executor.execute("nonexistent_tool", {})
    assert result.success is False
    assert "not found" in result.error.lower()


async def test_executor_blocks_forbidden_action():
    """AGENT role cannot execute create_product."""
    # Register a dummy create_product tool
    registry = ToolRegistry.get()
    async def dummy_handler(params, **_):
        return ToolResult(success=True, tool_name="create_product", data={"created": True})

    registry.register(ToolDefinition(
        name="create_product",
        description="test",
        category="internal",
        params_schema={},
        handler=dummy_handler,
    ))

    tracker = CostTracker()
    executor = ToolExecutor(role=Role.AGENT, cost_tracker=tracker)
    result = await executor.execute("create_product", {"name": "Test", "price": 10})
    assert result.success is False
    assert "cannot execute" in result.error.lower() or "forbidden" in result.error.lower()


async def test_executor_blocks_always_blocked_action():
    """submit_payment is always blocked regardless of role."""
    # Register it to bypass the registry check
    registry = ToolRegistry.get()
    async def dummy_payment(params, **_):
        return ToolResult(success=True, tool_name="submit_payment", data={})

    registry.register(ToolDefinition(
        name="submit_payment",
        description="test",
        category="internal",
        params_schema={},
        handler=dummy_payment,
    ))

    tracker = CostTracker()
    executor = ToolExecutor(role=Role.ADMIN, cost_tracker=tracker)
    result = await executor.execute("submit_payment", {})
    assert result.success is False
    assert "blocked" in result.error.lower()


async def test_executor_detects_duplicate_actions():
    """Same action with same params 3 times should be blocked."""
    registry = ToolRegistry.get()
    call_count = 0

    async def counting_handler(params, **_):
        nonlocal call_count
        call_count += 1
        return ToolResult(success=True, tool_name="get_analytics", data={"count": call_count})

    registry.register(ToolDefinition(
        name="get_analytics",
        description="test",
        category="internal",
        params_schema={},
        handler=counting_handler,
    ))

    tracker = CostTracker()
    executor = ToolExecutor(role=Role.USER, cost_tracker=tracker)

    # First two calls succeed
    r1 = await executor.execute("get_analytics", {"business_id": "test-id"})
    r2 = await executor.execute("get_analytics", {"business_id": "test-id"})
    # Third call with same params should be blocked
    r3 = await executor.execute("get_analytics", {"business_id": "test-id"})

    assert r1.success is True
    assert r2.success is True
    assert r3.success is False
    assert "DUPLICATE_ACTION" in r3.error


async def test_executor_stops_on_cost_limit():
    """Executor raises CostLimitExceededError when tracker limit is hit."""
    registry = ToolRegistry.get()

    async def fast_handler(params, **_):
        return ToolResult(success=True, tool_name="get_business", data={})

    registry.register(ToolDefinition(
        name="get_business",
        description="test",
        category="internal",
        params_schema={},
        handler=fast_handler,
    ))

    tracker = CostTracker(max_requests=1)
    tracker.record_request(provider="ollama")  # Use up the limit

    executor = ToolExecutor(role=Role.USER, cost_tracker=tracker)
    with pytest.raises(CostLimitExceededError):
        await executor.execute("get_business", {"business_id": "abc"})


async def test_executor_logs_executions():
    """Executor maintains an execution log."""
    registry = ToolRegistry.get()

    async def log_handler(params, **_):
        return ToolResult(success=True, tool_name="list_products", data=[])

    registry.register(ToolDefinition(
        name="list_products",
        description="test",
        category="internal",
        params_schema={},
        handler=log_handler,
    ))

    tracker = CostTracker()
    executor = ToolExecutor(role=Role.USER, cost_tracker=tracker)
    await executor.execute("list_products", {})

    log = executor.get_execution_log()
    assert len(log) >= 1
    assert log[-1]["tool"] == "list_products"


# ── API endpoint tests ────────────────────────────────────────────────────────

async def test_agent_run_endpoint_requires_auth(client: AsyncClient):
    """Agent run endpoint requires authentication."""
    response = await client.post(
        "/api/v1/agent/run",
        json={"goal": "Get my business analytics"},
    )
    assert response.status_code == 401


async def test_agent_run_with_goal(
    client: AsyncClient,
    auth_headers: dict,
    generated_business: dict,
    monkeypatch,
):
    """Agent run returns a structured result."""
    from app.agents.controller import AgentController

    async def mock_run(self, goal: str):
        from app.agents.controller import AgentRun, STATUS_DONE
        run = AgentRun(run_id="test-run-123", goal=goal, business_id=self.business_id)
        run.add_step({
            "thought": "I will get the analytics",
            "action": "get_analytics",
            "params": {"business_id": self.business_id},
            "result": {"visitors": 0},
            "success": True,
        })
        run.finish(STATUS_DONE, result="Analytics retrieved successfully.")
        return run

    monkeypatch.setattr(AgentController, "run", mock_run)

    response = await client.post(
        "/api/v1/agent/run",
        json={
            "goal": "Get my business analytics",
            "business_id": generated_business["id"],
            "apply_actions": False,
            "max_steps": 3,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "done"
    assert data["run_id"] == "test-run-123"
    assert len(data["steps"]) == 1
    assert data["result"] == "Analytics retrieved successfully."


async def test_agent_run_wrong_business(
    client: AsyncClient,
    auth_headers: dict,
):
    """Agent run returns 404 for a business that doesn't belong to the user."""
    response = await client.post(
        "/api/v1/agent/run",
        json={
            "goal": "Do something",
            "business_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=auth_headers,
    )
    assert response.status_code == 404


async def test_browser_agent_endpoint_requires_auth(client: AsyncClient):
    """Browser agent endpoint requires authentication."""
    response = await client.post(
        "/api/v1/agent/browser/run",
        json={"goal": "Find competitor pricing"},
    )
    assert response.status_code == 401


async def test_browser_agent_run(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch,
):
    """Browser agent returns structured result (mocked)."""
    from app.agents.browser_agent import BrowserAgent, BrowserAgentResult

    async def mock_run(self, goal: str):
        result = BrowserAgentResult(run_id="browser-run-456", goal=goal)
        result.add_step("search_google", {"query": goal}, {"title": "Results"}, True, "Searching")
        result.add_source("https://example.com")
        result.finish("done", result="Found 3 competitor pricing pages.")
        return result

    monkeypatch.setattr(BrowserAgent, "run", mock_run)

    response = await client.post(
        "/api/v1/agent/browser/run",
        json={"goal": "Find competitor pricing for AI SaaS"},
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "done"
    assert data["run_id"] == "browser-run-456"
    assert "https://example.com" in data["sources"]
    assert len(data["steps"]) == 1
