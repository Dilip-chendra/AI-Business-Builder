"""Tests for the AI provider system."""
import asyncio

import pytest
from httpx import AsyncClient

from app.services.ai_service import AIProviderError, AIService

pytestmark = pytest.mark.asyncio


async def test_ai_health_shape(client: AsyncClient):
    """Health endpoint returns the correct schema."""
    response = await client.get("/api/v1/ai/health")
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {"featherless", "groq", "huggingface", "ollama", "any_available"}
    # In test environment no real keys are set, so hosted providers should be False
    assert isinstance(data["featherless"], bool)
    assert isinstance(data["groq"], bool)
    assert isinstance(data["huggingface"], bool)
    assert isinstance(data["ollama"], bool)
    assert isinstance(data["any_available"], bool)


async def test_ai_health_is_public(client: AsyncClient):
    """Health endpoint requires no authentication."""
    response = await client.get("/api/v1/ai/health")
    assert response.status_code == 200


async def test_generate_business_returns_503_when_no_provider_available(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    """When all providers fail, the endpoint returns 503 with a clear message."""
    async def fail_all(self, prompt: str) -> str:
        raise AIProviderError("provider unavailable")

    async def ollama_available(self) -> bool:
        return True  # pretend Ollama is up so local_generate is attempted

    monkeypatch.setattr(AIService, "groq_generate", fail_all)
    monkeypatch.setattr(AIService, "hf_generate", fail_all)
    monkeypatch.setattr(AIService, "local_generate", fail_all)
    monkeypatch.setattr(AIService, "featherless_generate", fail_all)
    monkeypatch.setattr(AIService, "_ollama_available", ollama_available)
    # Make all three providers appear configured
    from app.core import config as config_module
    monkeypatch.setattr(config_module.settings, "featherless_enabled", True)
    monkeypatch.setattr(config_module.settings, "featherless_api_key", "test-key")
    monkeypatch.setattr(config_module.settings, "groq_api_key", "test-key")
    monkeypatch.setattr(config_module.settings, "hf_api_key", "test-key")

    response = await client.post(
        "/api/v1/businesses/generate",
        json={"interests": "fitness coaching"},
        headers=auth_headers,
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "No AI provider" in detail or "provider unavailable" in detail


async def test_generate_business_uses_groq_first(
    client: AsyncClient,
    auth_headers: dict,
    monkeypatch: pytest.MonkeyPatch,
):
    """Groq is tried before HuggingFace and Ollama when its key is set."""
    call_order: list[str] = []

    async def mock_groq(self, prompt: str) -> str:
        call_order.append("groq")
        return (
            '{"name":"Test","niche":"test","description":"A test business for testing purposes.",'
            '"target_audience":"testers","monetization_model":"subscriptions",'
            '"brand_tone":"professional","headline":"Test headline",'
            '"subheading":"Test subheading","product_pitch":"Test pitch",'
            '"cta_text":"Start","seo_title":"Test","seo_description":"Test description"}'
        )

    async def mock_hf(self, prompt: str) -> str:
        call_order.append("hf")
        raise AIProviderError("should not be called")

    # Patch the methods AND make settings report a groq key
    monkeypatch.setattr(AIService, "groq_generate", mock_groq)
    monkeypatch.setattr(AIService, "hf_generate", mock_hf)
    # Patch settings object attribute directly (lru_cache returns same instance)
    from app.core import config as config_module
    monkeypatch.setattr(config_module.settings, "featherless_enabled", False)
    monkeypatch.setattr(config_module.settings, "featherless_api_key", None)
    monkeypatch.setattr(config_module.settings, "groq_api_key", "test-groq-key")

    response = await client.post(
        "/api/v1/businesses/generate",
        json={"interests": "testing"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert "groq" in call_order
    assert "hf" not in call_order


async def test_marketing_task_prefers_featherless(
    monkeypatch: pytest.MonkeyPatch,
):
    """High-value tasks should route to Featherless before fallback providers."""
    call_order: list[str] = []

    async def mock_featherless(self, prompt: str, *, task_type: str | None = None, json_mode: bool = False) -> str:
        call_order.append(f"featherless:{task_type}")
        return '{"ok": true}'

    monkeypatch.setattr(AIService, "featherless_generate", mock_featherless)
    monkeypatch.setattr(AIService, "_ollama_available", lambda self: asyncio.sleep(0, result=False))
    from app.core import config as config_module
    monkeypatch.setattr(config_module.settings, "featherless_enabled", True)
    monkeypatch.setattr(config_module.settings, "featherless_api_key", "test-featherless-key")
    monkeypatch.setattr(config_module.settings, "groq_api_key", None)
    monkeypatch.setattr(config_module.settings, "hf_api_key", None)

    output = await AIService().generate_text("Create a campaign strategy", task_type="marketing", prefer_json=True)
    assert output == '{"ok": true}'
    assert call_order == ["featherless:marketing"]


async def test_ai_parse_json_strips_markdown_fences(monkeypatch):
    """JSON parser handles markdown code fences from some models."""
    svc = AIService()
    raw = '```json\n{"key": "value"}\n```'
    result = svc._parse_json(raw)
    assert result == {"key": "value"}


async def test_ai_parse_json_extracts_from_prose():
    """JSON parser extracts object from surrounding prose."""
    svc = AIService()
    raw = 'Here is the result: {"name": "Test", "value": 42} Hope that helps!'
    result = svc._parse_json(raw)
    assert result["name"] == "Test"
    assert result["value"] == 42
