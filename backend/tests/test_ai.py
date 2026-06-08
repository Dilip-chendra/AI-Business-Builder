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
    monkeypatch.setattr(AIService, "_ollama_available", ollama_available)
    # Make active providers appear configured.
    from app.core import config as config_module
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
    monkeypatch.setattr(config_module.settings, "groq_api_key", "test-groq-key")

    response = await client.post(
        "/api/v1/businesses/generate",
        json={"interests": "testing"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert "groq" in call_order
    assert "hf" not in call_order


async def test_marketing_task_prefers_groq_after_featherless_deprecation(
    monkeypatch: pytest.MonkeyPatch,
):
    """High-value tasks should no longer route to Featherless."""
    call_order: list[str] = []

    async def mock_groq(self, prompt: str) -> str:
        call_order.append("groq")
        return '{"ok": true}'

    monkeypatch.setattr(AIService, "groq_generate", mock_groq)
    monkeypatch.setattr(AIService, "_ollama_available", lambda self: asyncio.sleep(0, result=False))
    from app.core import config as config_module
    monkeypatch.setattr(config_module.settings, "groq_api_key", "test-groq-key")
    monkeypatch.setattr(config_module.settings, "hf_api_key", None)

    output = await AIService().generate_text("Create a campaign strategy", task_type="marketing", prefer_json=True)
    assert output == '{"ok": true}'
    assert call_order == ["groq"]


async def test_ai_service_records_actual_provider_used(
    monkeypatch: pytest.MonkeyPatch,
):
    """Successful generations expose the concrete provider for Studio timelines."""

    async def mock_groq(self, prompt: str) -> str:
        return '{"ok": true}'

    monkeypatch.setattr(AIService, "groq_generate", mock_groq)
    monkeypatch.setattr(AIService, "_ollama_available", lambda self: asyncio.sleep(0, result=False))
    from app.core import config as config_module
    monkeypatch.setattr(config_module.settings, "groq_api_key", "test-groq-key")
    monkeypatch.setattr(config_module.settings, "hf_api_key", None)

    service = AIService()
    output = await service.generate_text("Return JSON", task_type="ai_studio_app_builder", prefer_json=True)

    assert output == '{"ok": true}'
    assert service.last_provider == "groq"
    assert service.last_latency_seconds is not None
    assert service.last_trace_id


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


async def test_ai_parse_json_uses_first_balanced_object_with_trailing_text():
    """Provider chatter after a valid JSON object should not break Studio parsing."""
    svc = AIService()
    raw = (
        '{"summary":"Updated page","business_updates":{"headline":"Expert Home Services"},'
        '"page_content_patch":{"color_scheme":"black_gold"}}\n\n'
        "I made sure the page is more attractive."
    )

    result = svc._parse_json(raw)

    assert result["summary"] == "Updated page"
    assert result["business_updates"]["headline"] == "Expert Home Services"
    assert result["page_content_patch"]["color_scheme"] == "black_gold"


async def test_ai_parse_json_repairs_truncated_object_without_trailing_prose():
    """Truncated JSON repair stops cleanly when the root object closes."""
    svc = AIService()
    raw = '{"summary":"Updated","business_updates":{"headline":"Expert Home Services"}} trailing explanation'

    result = svc._parse_json(raw)

    assert result["business_updates"]["headline"] == "Expert Home Services"
