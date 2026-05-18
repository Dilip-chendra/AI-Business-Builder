"""Tests for the agent safety layer — permissions, validation, cost tracking."""
import pytest

from app.agents.safety.permissions import ForbiddenError, PermissionService, Role
from app.agents.safety.validator import ActionValidator, ValidationError
from app.agents.safety.cost_tracker import CostTracker, CostLimitExceededError

pytestmark = pytest.mark.asyncio


# ── Permission tests ──────────────────────────────────────────────────────────

def test_agent_can_read():
    PermissionService.check(Role.AGENT, "get_analytics")
    PermissionService.check(Role.AGENT, "get_business")
    PermissionService.check(Role.AGENT, "list_products")


def test_agent_cannot_delete():
    with pytest.raises(ForbiddenError):
        PermissionService.check(Role.AGENT, "delete_product")


def test_user_can_create_product():
    PermissionService.check(Role.USER, "create_product")


def test_user_cannot_delete():
    with pytest.raises(ForbiddenError):
        PermissionService.check(Role.USER, "delete_product")


def test_admin_can_delete():
    PermissionService.check(Role.ADMIN, "delete_product")


def test_unknown_tool_is_denied():
    with pytest.raises(ForbiddenError):
        PermissionService.check(Role.ADMIN, "nonexistent_tool")


def test_is_allowed_returns_bool():
    assert PermissionService.is_allowed(Role.USER, "create_product") is True
    assert PermissionService.is_allowed(Role.AGENT, "delete_product") is False


# ── Validation tests ──────────────────────────────────────────────────────────

def test_valid_create_product():
    ActionValidator.validate({
        "tool": "create_product",
        "params": {"business_id": "abc", "name": "Test Product", "price": 29.99},
    })


def test_blocked_action_submit_payment():
    with pytest.raises(ValidationError):
        ActionValidator.validate({"tool": "submit_payment", "params": {}})


def test_blocked_action_buy():
    with pytest.raises(ValidationError):
        ActionValidator.validate({"tool": "buy", "params": {}})


def test_invalid_price_zero():
    with pytest.raises(ValidationError):
        ActionValidator.validate({
            "tool": "create_product",
            "params": {"business_id": "abc", "name": "Bad", "price": 0},
        })


def test_invalid_price_negative():
    with pytest.raises(ValidationError):
        ActionValidator.validate({
            "tool": "create_product",
            "params": {"business_id": "abc", "name": "Bad", "price": -10},
        })


def test_blocked_url_localhost():
    with pytest.raises(ValidationError):
        ActionValidator.validate({
            "tool": "open_url",
            "params": {"url": "http://localhost:8000/admin"},
        })


def test_blocked_url_internal_ip():
    with pytest.raises(ValidationError):
        ActionValidator.validate({
            "tool": "open_url",
            "params": {"url": "http://192.168.1.1/"},
        })


def test_valid_external_url():
    ActionValidator.validate({
        "tool": "open_url",
        "params": {"url": "https://www.google.com"},
    })


def test_blocked_type_password():
    with pytest.raises(ValidationError):
        ActionValidator.validate({
            "tool": "type_text",
            "params": {"selector": "#pass", "text": "my password is secret"},
        })


def test_update_business_field_invalid_field():
    with pytest.raises(ValidationError):
        ActionValidator.validate({
            "tool": "update_business_field",
            "params": {"business_id": "abc", "field": "user_id", "new_value": "hacked"},
        })


def test_update_business_field_valid():
    ActionValidator.validate({
        "tool": "update_business_field",
        "params": {"business_id": "abc", "field": "headline", "new_value": "New headline text"},
    })


def test_missing_tool_name():
    with pytest.raises(ValidationError):
        ActionValidator.validate({"params": {}})


def test_blocked_payload_pattern():
    with pytest.raises(ValidationError):
        ActionValidator.validate({
            "tool": "create_product",
            "params": {"name": "delete_all products", "price": 10},
        })


# ── Cost tracker tests ────────────────────────────────────────────────────────

def test_cost_tracker_records_requests():
    tracker = CostTracker(max_requests=5)
    tracker.record_request(provider="ollama", input_tokens=100, output_tokens=200)
    assert tracker.total_requests == 1
    assert tracker.total_tokens == 300
    assert tracker.total_cost_usd == 0.0  # Ollama is free


def test_cost_tracker_request_limit():
    tracker = CostTracker(max_requests=2)
    tracker.record_request(provider="ollama")
    tracker.record_request(provider="ollama")
    with pytest.raises(CostLimitExceededError, match="REQUEST_LIMIT_EXCEEDED"):
        tracker.record_request(provider="ollama")


def test_cost_tracker_step_limit():
    tracker = CostTracker(max_steps=3)
    tracker.increment_step()
    tracker.increment_step()
    tracker.increment_step()
    with pytest.raises(CostLimitExceededError, match="STEP_LIMIT_EXCEEDED"):
        tracker.increment_step()


def test_cost_tracker_token_limit():
    tracker = CostTracker(max_tokens=100)
    with pytest.raises(CostLimitExceededError, match="TOKEN_LIMIT_EXCEEDED"):
        tracker.record_request(provider="ollama", input_tokens=50, output_tokens=60)


def test_cost_tracker_summary():
    tracker = CostTracker(max_steps=5)
    tracker.record_request(provider="groq", input_tokens=500, output_tokens=200)
    tracker.increment_step()
    summary = tracker.summary()
    assert summary["total_requests"] == 1
    assert summary["total_tokens"] == 700
    assert summary["current_step"] == 1
    assert "limits" in summary
