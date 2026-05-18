"""AI service — routes generation requests through available providers.

Provider priority (first available wins):
  1. Groq        — free API, fast,   requires GROQ_API_KEY
  2. HuggingFace — free API, slower, requires HF_API_KEY
  3. Ollama      — local model,      requires Ollama running at OLLAMA_BASE_URL

If no provider is available the service raises AIProviderError with a clear
503-friendly message. No dummy data is ever returned.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.schemas.business import BusinessGenerateRequest
from app.services.providers.featherless_provider import FeatherlessProvider, FeatherlessProviderError

logger = logging.getLogger(__name__)

# ── Groq endpoint (direct HTTP — no SDK dependency) ──────────────────────────
_GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL    = "llama-3.1-8b-instant"   # official replacement for llama3-8b-8192
_GROQ_TIMEOUT  = 30.0  # seconds — Groq is fast; 30s is generous

# ── HuggingFace endpoint ──────────────────────────────────────────────────────
_HF_API_BASE = "https://api-inference.huggingface.co/models"
_HF_MODEL    = "HuggingFaceH4/zephyr-7b-beta"


class AIProviderError(RuntimeError):
    """Raised when every configured AI provider fails or none is available."""


# ── Groq-specific exceptions ──────────────────────────────────────────────────

class GroqRateLimitError(AIProviderError):
    """Raised when Groq returns HTTP 429 (rate limit exceeded)."""


class GroqAuthError(AIProviderError):
    """Raised when Groq returns HTTP 401 (invalid or expired API key)."""


class GroqTimeoutError(AIProviderError):
    """Raised when the Groq request exceeds the timeout."""


# ── HuggingFace-specific exceptions ──────────────────────────────────────────

class HFRateLimitError(AIProviderError):
    """Raised when HuggingFace returns HTTP 429."""


class HFModelLoadingError(AIProviderError):
    """Raised when HuggingFace model is still loading and retries are exhausted."""


# ── Pydantic output models ────────────────────────────────────────────────────

class GeneratedBusiness(BaseModel):
    # ── Core identity ─────────────────────────────────────────────────────────
    name: str = Field(min_length=2)
    niche: str = Field(min_length=2)
    description: str = Field(min_length=10)
    target_audience: str = Field(min_length=2)
    monetization_model: str = Field(min_length=2)
    brand_tone: str = Field(min_length=2)
    # ── Landing page copy ─────────────────────────────────────────────────────
    headline: str = Field(min_length=2)
    subheading: str = Field(min_length=2)
    product_pitch: str = Field(min_length=2)
    cta_text: str = Field(min_length=2)
    # ── SEO ───────────────────────────────────────────────────────────────────
    seo_title: str = Field(min_length=2)
    seo_description: str = Field(min_length=2)
    # ── Rich page content (psychology-driven) ─────────────────────────────────
    pain_points: list[str] = Field(default_factory=list)       # 3 pains the audience feels
    benefits: list[str] = Field(default_factory=list)          # 3 outcome-focused benefits
    features: list[dict] = Field(default_factory=list)         # [{title, description, icon_hint}]
    social_proof: list[dict] = Field(default_factory=list)     # [{name, role, quote, rating}]
    faq: list[dict] = Field(default_factory=list)              # [{question, answer}]
    pricing_tiers: list[dict] = Field(default_factory=list)    # [{name, price, period, features[], cta, highlighted}]
    urgency_text: str = ""                                      # e.g. "Limited beta — 47 spots left"
    trust_badges: list[str] = Field(default_factory=list)      # e.g. ["No credit card required"]
    color_scheme: str = "indigo"                               # indigo|emerald|rose|amber|sky|violet


class AIHealth(BaseModel):
    """Provider availability status returned by GET /api/v1/ai/health."""
    featherless: bool
    groq: bool
    huggingface: bool
    ollama: bool
    any_available: bool


# ── Main service ──────────────────────────────────────────────────────────────

class AIService:

    # ── Public interface ──────────────────────────────────────────────────────

    async def generate_business(self, payload: BusinessGenerateRequest) -> GeneratedBusiness:
        prompt = self._business_prompt(payload)
        parsed = await self.generate_json(prompt, task_type="ai_studio")
        try:
            return GeneratedBusiness.model_validate(parsed)
        except ValidationError as exc:
            raise AIProviderError(
                f"AI returned JSON that does not match the business schema: {exc}"
            ) from exc

    async def generate_json(self, prompt: str, *, task_type: str | None = None) -> dict[str, Any]:
        """Generate text and parse it as JSON. Raises AIProviderError on failure."""
        output = await self.generate_text(prompt, prefer_json=True, task_type=task_type)
        return self._parse_json(output)

    async def generate_text(
        self,
        prompt: str,
        trace_id: str | None = None,
        *,
        prefer_json: bool = False,
        task_type: str | None = None,
    ) -> str:
        """Try each provider in priority order using adaptive scoring.

        Raises AIProviderError if all fail.
        Records telemetry for every attempt.
        """
        from app.services.ai_telemetry import telemetry

        if trace_id is None:
            trace_id = str(uuid.uuid4())[:8]

        errors: list[str] = []
        prompt_preview = prompt[:100].replace("\n", " ")

        # Build candidate list in deterministic priority order.
        # We still record telemetry, but we don't let stale circuit state silently
        # reshuffle provider order for critical product flows and CI.
        ollama_ok = await self._ollama_available()
        configured = self._configured_providers(ollama_ok=ollama_ok)
        preferred_order = self._provider_order_for_task(task_type, prefer_json=prefer_json)
        candidates = [provider for provider in preferred_order if provider in configured]

        prev_provider = None
        for provider in candidates:
            if prev_provider:
                await telemetry.record_fallback(prev_provider, provider)

            t_start = time.monotonic()
            try:
                if provider == "featherless":
                    result = await self.featherless_generate(prompt, task_type=task_type, json_mode=prefer_json)
                elif provider == "groq":
                    result = await (self.groq_generate(prompt) if prefer_json else self.groq_generate_text(prompt))
                elif provider == "huggingface":
                    result = await self.hf_generate(prompt)
                else:
                    result = await self.local_generate(prompt, json_mode=prefer_json)

                if result.strip():
                    latency = time.monotonic() - t_start
                    await telemetry.record_success(provider, latency, trace_id=trace_id)
                    logger.info(
                        "AI generation succeeded  provider=%s  latency=%.2fs  trace=%s",
                        provider, latency, trace_id,
                    )
                    return result
                errors.append(f"{provider}: empty response")
                await telemetry.record_failure(
                    provider, "empty_response", "Empty response",
                    time.monotonic() - t_start, trace_id=trace_id,
                    prompt_preview=prompt_preview,
                )

            except FeatherlessProviderError as exc:
                latency = time.monotonic() - t_start
                is_timeout = "timeout" in str(exc).lower() or "timed out" in str(exc).lower()
                await telemetry.record_failure(
                    provider, type(exc).__name__, str(exc), latency,
                    trace_id=trace_id, prompt_preview=prompt_preview, is_timeout=is_timeout,
                )
                logger.warning("featherless failed  trace=%s: %s", trace_id, exc)
                errors.append(f"featherless: {exc}")

            except GroqRateLimitError as exc:
                latency = time.monotonic() - t_start
                await telemetry.record_failure(
                    provider, "rate_limit", str(exc), latency,
                    trace_id=trace_id, prompt_preview=prompt_preview, is_rate_limit=True,
                )
                logger.warning("groq rate-limited  trace=%s: %s", trace_id, exc)
                errors.append(f"groq: rate_limit — {exc}")

            except GroqAuthError as exc:
                latency = time.monotonic() - t_start
                await telemetry.record_failure(
                    provider, "auth_error", "Auth failed", latency,
                    trace_id=trace_id, prompt_preview=prompt_preview,
                )
                logger.error("groq auth failed — check GROQ_API_KEY in .env  trace=%s", trace_id)
                errors.append(f"groq: auth_error — {exc}")

            except GroqTimeoutError as exc:
                latency = time.monotonic() - t_start
                await telemetry.record_failure(
                    provider, "timeout", str(exc), latency,
                    trace_id=trace_id, prompt_preview=prompt_preview, is_timeout=True,
                )
                logger.warning("groq timed out  trace=%s: %s", trace_id, exc)
                errors.append(f"groq: timeout — {exc}")

            except HFRateLimitError as exc:
                latency = time.monotonic() - t_start
                await telemetry.record_failure(
                    provider, "rate_limit", str(exc), latency,
                    trace_id=trace_id, prompt_preview=prompt_preview, is_rate_limit=True,
                )
                logger.warning("huggingface rate-limited  trace=%s: %s", trace_id, exc)
                errors.append(f"huggingface: rate_limit — {exc}")

            except HFModelLoadingError as exc:
                latency = time.monotonic() - t_start
                await telemetry.record_failure(
                    provider, "model_loading", str(exc), latency,
                    trace_id=trace_id, prompt_preview=prompt_preview,
                )
                logger.warning("huggingface model loading  trace=%s: %s", trace_id, exc)
                errors.append(f"huggingface: model_loading — {exc}")

            except Exception as exc:
                latency = time.monotonic() - t_start
                is_timeout = "timeout" in str(exc).lower() or "timed out" in str(exc).lower()
                await telemetry.record_failure(
                    provider, type(exc).__name__, str(exc), latency,
                    trace_id=trace_id, prompt_preview=prompt_preview, is_timeout=is_timeout,
                )
                logger.warning("%s failed  trace=%s: %s", provider, trace_id, exc)
                errors.append(f"{provider}: {exc}")

            prev_provider = provider

        raise AIProviderError(
            "No AI provider is available. Configure FEATHERLESS_API_KEY, GROQ_API_KEY or HF_API_KEY, "
            "or start Ollama locally. Details: " + " | ".join(errors)
        )

    async def health(self) -> AIHealth:
        """Check which providers are currently available."""
        featherless_ok = await self._featherless_available()
        groq_ok = bool(settings.groq_api_key)
        hf_ok   = bool(settings.hf_api_key)
        ollama_ok = await self._ollama_available()
        return AIHealth(
            featherless=featherless_ok,
            groq=groq_ok,
            huggingface=hf_ok,
            ollama=ollama_ok,
            any_available=featherless_ok or groq_ok or hf_ok or ollama_ok,
        )

    async def featherless_generate(
        self,
        prompt: str,
        *,
        task_type: str | None = None,
        json_mode: bool = False,
    ) -> str:
        provider = FeatherlessProvider()
        payload = await provider.generate(
            prompt=prompt,
            task_type=task_type,
            prefer_json=json_mode,
            timeout_seconds=max(
                settings.ai_timeout_seconds,
                settings.browser_synthesis_timeout_seconds if task_type == "browser_synthesis" else settings.ai_timeout_seconds,
            ),
        )
        return str(payload["content"])

    @staticmethod
    def _provider_order_for_task(task_type: str | None, *, prefer_json: bool) -> list[str]:
        task = (task_type or "").lower()
        if task in {"quick_task", "short_classification", "json_formatting"}:
            return ["groq", "featherless", "ollama", "huggingface"]
        if task in {"coding", "browser_planning", "browser_synthesis", "browser_extraction", "marketing", "ai_studio", "vision"}:
            return ["featherless", "groq", "ollama", "huggingface"]
        if prefer_json:
            return ["featherless", "groq", "ollama", "huggingface"]
        return ["featherless", "groq", "ollama", "huggingface"]

    @staticmethod
    def _configured_providers(*, ollama_ok: bool) -> list[str]:
        configured: list[str] = []
        if settings.featherless_enabled and settings.featherless_api_key:
            configured.append("featherless")
        if settings.groq_api_key:
            configured.append("groq")
        if settings.hf_api_key:
            configured.append("huggingface")
        if ollama_ok:
            configured.append("ollama")
        return configured

    # ── Provider implementations ──────────────────────────────────────────────

    async def groq_generate(self, prompt: str) -> str:
        """Call Groq with JSON response format (for structured data)."""
        return await self._groq_call(prompt, json_mode=True)

    async def groq_generate_text(self, prompt: str) -> str:
        """Call Groq without JSON response format (for plain prose)."""
        return await self._groq_call(prompt, json_mode=False)

    async def _groq_call(self, prompt: str, json_mode: bool = True) -> str:
        """Internal Groq HTTP call. json_mode=True forces JSON output."""
        if not settings.groq_api_key:
            raise AIProviderError("GROQ_API_KEY is not set")

        model    = getattr(settings, "groq_model", _GROQ_MODEL)
        endpoint = getattr(settings, "groq_base_url", "https://api.groq.com/openai/v1").rstrip("/")
        url      = f"{endpoint}/chat/completions"

        logger.info("Groq request starting  model=%s  json_mode=%s", model, json_mode)

        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if json_mode:
            messages.append({
                "role": "system",
                "content": "Return only valid JSON. No prose, no markdown, no code fences.",
            })
        messages.append({"role": "user", "content": prompt})

        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": 0.35,
            "max_tokens": 2048,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        timeout_cfg = httpx.Timeout(
            connect=10.0,
            read=_GROQ_TIMEOUT,
            write=10.0,
            pool=5.0,
        )

        try:
            async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                response = await client.post(url, headers=headers, json=body)

        except httpx.TimeoutException:
            logger.error(
                "Groq request timed out  model=%s  timeout=%.0fs",
                model, _GROQ_TIMEOUT,
            )
            raise GroqTimeoutError(
                f"Groq request timed out after {_GROQ_TIMEOUT:.0f}s. "
                "Falling back to next provider."
            )

        except httpx.RequestError as exc:
            logger.error("Groq network error  model=%s  error=%s", model, exc)
            raise AIProviderError(
                f"Groq network error: {exc}. Check your internet connection."
            )

        # ── HTTP error handling ───────────────────────────────────────────────

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            logger.warning(
                "Groq rate limit hit  model=%s  retry_after=%s",
                model, retry_after,
            )
            raise GroqRateLimitError(
                f"Groq rate limit exceeded (HTTP 429). "
                f"Retry-After: {retry_after}s. "
                "Falling back to HuggingFace or Ollama."
            )

        if response.status_code == 401:
            # Log hint only — never log the key value
            logger.error(
                "Groq authentication failed  model=%s  "
                "hint=check_GROQ_API_KEY_in_.env",
                model,
            )
            raise GroqAuthError(
                "Groq authentication failed (HTTP 401). "
                "Verify GROQ_API_KEY is correct and not expired."
            )

        if response.status_code == 400:
            logger.error(
                "Groq bad request  model=%s  body=%.200s",
                model, response.text,
            )
            raise AIProviderError(
                f"Groq rejected the request (HTTP 400): {response.text[:200]}"
            )

        if response.status_code == 503:
            logger.warning("Groq service unavailable  model=%s", model)
            raise AIProviderError(
                "Groq service is temporarily unavailable (HTTP 503). "
                "Falling back to next provider."
            )

        if response.status_code != 200:
            logger.error(
                "Groq unexpected HTTP status  model=%s  status=%d  body=%.200s",
                model, response.status_code, response.text,
            )
            raise AIProviderError(
                f"Groq returned unexpected HTTP {response.status_code}. "
                f"Body: {response.text[:200]}"
            )

        # ── Parse successful response ─────────────────────────────────────────

        try:
            data = response.json()
        except Exception as exc:
            logger.error("Groq response is not valid JSON  model=%s  error=%s", model, exc)
            raise AIProviderError(
                f"Groq returned non-JSON response: {response.text[:200]}"
            )

        # OpenAI-compatible response shape:
        # {"choices": [{"message": {"content": "..."}}], "usage": {...}}
        try:
            content: str = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            logger.error(
                "Groq response missing expected fields  model=%s  keys=%s",
                model, list(data.keys()) if isinstance(data, dict) else type(data),
            )
            raise AIProviderError(
                f"Groq response missing 'choices[0].message.content': {exc}. "
                f"Full response keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}"
            )

        if not content.strip():
            raise AIProviderError("Groq returned an empty content string.")

        # Log completion stats from usage block (no sensitive data)
        usage = data.get("usage", {})
        logger.info(
            "Groq request completed  model=%s  "
            "prompt_tokens=%s  completion_tokens=%s  total_tokens=%s",
            model,
            usage.get("prompt_tokens", "?"),
            usage.get("completion_tokens", "?"),
            usage.get("total_tokens", "?"),
        )

        return content

    async def hf_generate(self, prompt: str) -> str:
        """Call HuggingFace Inference API — mistralai/Mistral-7B-Instruct-v0.2.

        Handles:
        - Model cold-start ("model is loading") with configurable retries
        - Rate limiting (HTTP 429) — raises HFRateLimitError
        - Request timeout (settings.hf_timeout_seconds, default 60s)
        - Malformed / unexpected response shapes

        The API key is read exclusively from settings.hf_api_key (env var HF_API_KEY).
        It is NEVER logged or included in error messages.
        """
        if not settings.hf_api_key:
            raise AIProviderError("HF_API_KEY is not set")

        # Build the endpoint URL from config so the model can be swapped via env
        model = getattr(settings, "hf_model", _HF_MODEL)
        base  = getattr(settings, "hf_base_url", _HF_API_BASE).rstrip("/")
        url   = f"{base}/{model}"

        # Log the target model — never the key
        logger.info("HuggingFace request starting  model=%s", model)

        headers = {
            # Key injected at runtime from env — never appears in source code
            "Authorization": f"Bearer {settings.hf_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 800,
                "temperature": 0.35,
                "return_full_text": False,
                "do_sample": True,
            },
            # Ask HF to wait for the model to load instead of returning 503
            "options": {
                "wait_for_model": False,  # We handle loading ourselves for better UX
                "use_cache": False,       # Always get a fresh generation
            },
        }

        timeout_cfg = httpx.Timeout(
            connect=10.0,
            read=settings.hf_timeout_seconds,
            write=10.0,
            pool=5.0,
        )

        max_retries = settings.hf_loading_retries
        retry_delay = settings.hf_loading_retry_delay

        for attempt in range(1, max_retries + 2):  # +2: initial attempt + retries
            try:
                async with httpx.AsyncClient(timeout=timeout_cfg) as client:
                    response = await client.post(url, headers=headers, json=payload)

                # ── Rate limit ────────────────────────────────────────────────
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "unknown")
                    logger.warning(
                        "HuggingFace rate limit hit  model=%s  retry_after=%s",
                        model, retry_after,
                    )
                    raise HFRateLimitError(
                        f"HuggingFace rate limit exceeded. "
                        f"Retry after {retry_after}s. "
                        "Consider using Groq or Ollama as primary provider."
                    )

                # ── Auth failure — key is wrong/expired ───────────────────────
                if response.status_code == 401:
                    logger.error(
                        "HuggingFace authentication failed  model=%s  "
                        "hint=check_HF_API_KEY_in_.env",
                        model,
                    )
                    raise AIProviderError(
                        "HuggingFace authentication failed. "
                        "Verify HF_API_KEY is correct and not expired."
                    )

                # ── Model not found ───────────────────────────────────────────
                if response.status_code == 404:
                    logger.error("HuggingFace model not found  model=%s", model)
                    raise AIProviderError(
                        f"HuggingFace model '{model}' not found. "
                        "Check HF_MODEL in .env."
                    )

                # ── Other HTTP errors ─────────────────────────────────────────
                if response.status_code not in (200, 503):
                    logger.error(
                        "HuggingFace unexpected HTTP status  model=%s  status=%d",
                        model, response.status_code,
                    )
                    raise AIProviderError(
                        f"HuggingFace returned HTTP {response.status_code}. "
                        f"Body: {response.text[:200]}"
                    )

                data = response.json()

                # ── Model is loading (503 or loading flag in body) ────────────
                is_loading = (
                    response.status_code == 503
                    or (isinstance(data, dict) and data.get("error", "").lower().startswith("loading"))
                )
                if is_loading:
                    estimated_time = (
                        data.get("estimated_time", retry_delay)
                        if isinstance(data, dict)
                        else retry_delay
                    )
                    if attempt > max_retries:
                        logger.error(
                            "HuggingFace model still loading after %d retries  model=%s",
                            max_retries, model,
                        )
                        raise HFModelLoadingError(
                            f"HuggingFace model '{model}' is still loading after "
                            f"{max_retries} retries. Try again in ~{estimated_time:.0f}s."
                        )
                    wait = min(float(estimated_time), retry_delay)
                    logger.info(
                        "HuggingFace model loading  model=%s  attempt=%d/%d  "
                        "waiting=%.0fs",
                        model, attempt, max_retries, wait,
                    )
                    await asyncio.sleep(wait)
                    continue  # retry

                # ── Successful response — extract generated text ───────────────
                return self._extract_hf_text(data, model)

            except (HFRateLimitError, HFModelLoadingError, AIProviderError):
                raise  # propagate our own typed errors unchanged

            except httpx.TimeoutException:
                logger.error(
                    "HuggingFace request timed out  model=%s  timeout=%.0fs",
                    model, settings.hf_timeout_seconds,
                )
                raise AIProviderError(
                    f"HuggingFace request timed out after {settings.hf_timeout_seconds:.0f}s. "
                    "The model may be under heavy load. Try again or switch to Groq."
                )

            except httpx.RequestError as exc:
                logger.error("HuggingFace network error  model=%s  error=%s", model, exc)
                raise AIProviderError(
                    f"HuggingFace network error: {exc}. "
                    "Check your internet connection."
                )

        # Should never reach here — loop always returns or raises
        raise AIProviderError(f"HuggingFace: exhausted all {max_retries} retries.")

    def _extract_hf_text(self, data: Any, model: str) -> str:
        """Extract the generated text string from a HuggingFace response payload.

        HF can return several shapes depending on the pipeline type:
          - list of dicts:  [{"generated_text": "..."}]
          - single dict:    {"generated_text": "..."}  or  {"error": "..."}
        """
        # Error in a 200 response body (rare but happens)
        if isinstance(data, dict) and "error" in data:
            raise AIProviderError(
                f"HuggingFace returned an error in the response body: {data['error']}"
            )

        # Standard text-generation pipeline response
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                text = first.get("generated_text", "")
                if text:
                    logger.info(
                        "HuggingFace request completed  model=%s  "
                        "output_chars=%d",
                        model, len(text),
                    )
                    return str(text)

        # Some models return a plain dict
        if isinstance(data, dict):
            for key in ("generated_text", "response", "text", "output"):
                text = data.get(key, "")
                if text:
                    logger.info(
                        "HuggingFace request completed  model=%s  "
                        "output_chars=%d",
                        model, len(str(text)),
                    )
                    return str(text)

        logger.error(
            "HuggingFace unexpected response shape  model=%s  type=%s  "
            "preview=%.100r",
            model, type(data).__name__, data,
        )
        raise AIProviderError(
            f"HuggingFace returned an unexpected response format "
            f"(type={type(data).__name__}). "
            f"Preview: {str(data)[:200]}"
        )

    async def local_generate(self, prompt: str, json_mode: bool = False) -> str:
        """Call a locally running Ollama instance."""
        url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
        # Local models can be slow on first run – use a generous timeout
        timeout = max(settings.ai_timeout_seconds, 120.0)
        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise AIProviderError(f"Ollama error: {data['error']}")
            return str(data.get("response", ""))

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _ollama_available(self) -> bool:
        """Return True if Ollama is reachable. Never raises."""
        if not settings.should_enable_ollama:
            return False
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(f"{settings.ollama_base_url.rstrip('/')}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    async def _featherless_available(self) -> bool:
        """Return True if Featherless is configured and responds to a lightweight health check."""
        if not settings.featherless_enabled or not settings.featherless_api_key:
            return False
        try:
            payload = await FeatherlessProvider().health_check()
            return bool(payload.get("ok"))
        except Exception:
            return False

    def _parse_json(self, output: str) -> dict[str, Any]:
        """Parse JSON from model output, extracting from surrounding text if needed."""
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?\s*", "", output).strip()
        # Also strip any leading/trailing prose before the first {
        brace_start = cleaned.find("{")
        if brace_start > 0:
            cleaned = cleaned[brace_start:]
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract the first JSON object from the text
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if not match:
                raise AIProviderError(
                    f"AI response is not valid JSON. Raw output: {output[:300]}"
                )
            try:
                parsed = json.loads(match.group())
            except json.JSONDecodeError as exc:
                raise AIProviderError(
                    f"Could not parse JSON from AI response: {exc}. "
                    f"Raw: {output[:300]}"
                ) from exc
        if not isinstance(parsed, dict):
            raise AIProviderError(
                f"AI response JSON must be an object, got {type(parsed).__name__}"
            )
        return parsed

    def _business_prompt(self, payload: BusinessGenerateRequest) -> str:
        return (
            "You are an expert conversion copywriter and business strategist.\n"
            "Generate a complete, psychologically compelling landing page for a real online business.\n"
            "Return ONLY a single flat JSON object. No nested sections. No markdown. No code fences.\n\n"
            "The JSON must have EXACTLY these top-level keys (all flat, no nesting):\n\n"
            "  name            string  — catchy brand name, 2-4 words\n"
            "  niche           string  — specific market niche\n"
            "  description     string  — 2-sentence business description\n"
            "  target_audience string  — precise audience (e.g. 'Freelance designers aged 25-40')\n"
            "  monetization_model string — how it earns money\n"
            "  brand_tone      string  — tone of voice\n"
            "  headline        string  — powerful benefit-driven headline, max 10 words\n"
            "  subheading      string  — 1-2 sentences expanding the headline\n"
            "  cta_text        string  — CTA button text (e.g. 'Start Free — No Card Needed')\n"
            "  urgency_text    string  — scarcity line (e.g. 'Join 2,400+ founders — 50 spots left')\n"
            "  product_pitch   string  — 2-3 sentence elevator pitch\n"
            "  seo_title       string  — SEO title under 60 chars\n"
            "  seo_description string  — meta description 150-160 chars\n"
            "  color_scheme    string  — one of: indigo|emerald|rose|amber|sky|violet\n"
            "                           (tech=indigo, health=emerald, creative=violet, finance=sky)\n"
            "  pain_points     array   — exactly 3 strings, each a specific daily pain the audience feels\n"
            "  benefits        array   — exactly 3 strings, outcome-focused (e.g. 'Go from X to Y in Z')\n"
            "  trust_badges    array   — exactly 4 strings (e.g. 'No credit card required')\n"
            "  features        array   — exactly 4 objects, each: {title, description, icon_hint}\n"
            "                           icon_hint must be one of: zap|shield|chart|users|star|clock|globe|lock\n"
            "  social_proof    array   — exactly 3 objects, each: {name, role, quote, rating}\n"
            "                           rating is integer 4 or 5. quote must cite a specific number/outcome.\n"
            "  faq             array   — exactly 4 objects, each: {question, answer}\n"
            "                           cover: pricing, setup time, cancellation, results timeline\n"
            "  pricing_tiers   array   — exactly 3 objects, each: {name, price, period, features, cta, highlighted}\n"
            "                           features is array of 4 strings. highlighted is boolean (true for middle).\n"
            "                           Use realistic pricing for the niche.\n\n"
            "RULES:\n"
            "- Output must be a single flat JSON object — do NOT nest fields under section names\n"
            "- Every value must be specific to this business, never generic placeholders\n"
            "- Social proof quotes must mention real numbers (hours saved, revenue, percentage)\n\n"
            f"User input:\n{payload.model_dump_json()}"
        )


# ── Standalone callables ──────────────────────────────────────────────────────

async def call_groq(prompt: str) -> str:
    """Standalone function to call the Groq Inference API directly via httpx.

    Reads GROQ_API_KEY exclusively from the environment (via settings).
    The key is NEVER logged, printed, or included in any error message.

    Endpoint : https://api.groq.com/openai/v1/chat/completions
    Model    : llama3-8b-8192  (overridable via GROQ_MODEL in .env)
    Timeout  : 30 seconds

    Args:
        prompt: The user message to send to the model.

    Returns:
        The clean text response from the model (no markdown fences).

    Raises:
        GroqRateLimitError : HTTP 429 — rate limit exceeded.
        GroqAuthError      : HTTP 401 — invalid or expired API key.
        GroqTimeoutError   : Request timed out after 30s.
        AIProviderError    : Any other failure.

    Example::

        from app.services.ai_service import call_groq

        result = await call_groq(
            "Suggest a profitable SaaS niche for solo founders in 2025."
        )
        print(result)
    """
    return await AIService().groq_generate(prompt)


async def call_huggingface(prompt: str) -> str:
    """Standalone function to call HuggingFace Inference API.

    Reads HF_API_KEY exclusively from the environment (via settings).
    The key is NEVER logged, printed, or included in any error message.

    Args:
        prompt: The text prompt to send to the model.

    Returns:
        The generated text string from the model.

    Raises:
        AIProviderError:      General API failure (network, auth, bad response).
        HFRateLimitError:     HTTP 429 — too many requests.
        HFModelLoadingError:  Model still loading after all retries.

    Example::

        from app.services.ai_service import call_huggingface

        result = await call_huggingface(
            "Suggest a profitable SaaS niche for solo founders in 2025."
        )
        print(result)
    """
    return await AIService().hf_generate(prompt)
