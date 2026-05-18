from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, RateLimitError

from app.core.config import settings

logger = logging.getLogger(__name__)


class FeatherlessProviderError(RuntimeError):
    """Raised when Featherless cannot satisfy a generation request."""


class FeatherlessProvider:
    def __init__(self) -> None:
        if not settings.featherless_api_key:
            raise FeatherlessProviderError("FEATHERLESS_API_KEY is not configured.")
        self._client = AsyncOpenAI(
            api_key=settings.featherless_api_key,
            base_url=settings.featherless_base_url.rstrip("/"),
            timeout=settings.ai_timeout_seconds,
        )
        self._base_url = settings.featherless_base_url.rstrip("/")

    def _fallback_models(self, primary_model: str) -> list[str]:
        candidates = [
            primary_model,
            settings.featherless_reasoning_model,
            settings.featherless_general_model,
            settings.featherless_marketing_model,
            settings.featherless_coding_model,
            settings.featherless_browser_model,
        ]
        seen: set[str] = set()
        ordered: list[str] = []
        for model in candidates:
            if model and model not in seen:
                seen.add(model)
                ordered.append(model)
        return ordered

    def model_for_task(self, task_type: str | None) -> str:
        task = (task_type or "").lower()
        if task == "coding":
            return settings.featherless_coding_model
        if task in {"browser_planning", "browser_synthesis", "browser_extraction", "vision"}:
            return settings.featherless_browser_model or settings.featherless_reasoning_model
        if task == "marketing":
            return settings.featherless_marketing_model or settings.featherless_general_model
        if task == "ai_studio":
            return settings.featherless_reasoning_model or settings.featherless_general_model
        if task == "quick_task":
            return settings.featherless_general_model
        return settings.featherless_reasoning_model or settings.featherless_general_model

    async def generate(
        self,
        *,
        prompt: str,
        task_type: str | None = None,
        prefer_json: bool = False,
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        if not settings.featherless_enabled:
            raise FeatherlessProviderError("Featherless provider is disabled.")

        errors: list[str] = []
        primary_model = self.model_for_task(task_type)
        messages = []
        if prefer_json:
            messages.append(
                {
                    "role": "system",
                    "content": "Return only valid JSON. No prose, no markdown, no code fences.",
                }
            )
        messages.append({"role": "user", "content": prompt})

        timeout = timeout_seconds or settings.ai_timeout_seconds
        for model in self._fallback_models(primary_model):
            try:
                request_kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": 0.2 if prefer_json else 0.35,
                    "max_tokens": 2200,
                    "timeout": timeout,
                }
                if prefer_json:
                    request_kwargs["response_format"] = {"type": "json_object"}

                response = await self._client.chat.completions.create(
                    **request_kwargs,
                )
                content = response.choices[0].message.content or ""
                if not content.strip():
                    raise FeatherlessProviderError(f"Featherless returned an empty response for model {model}.")
                usage = response.usage
                return {
                    "provider": "featherless",
                    "model": model,
                    "content": content,
                    "usage": {
                        "prompt_tokens": getattr(usage, "prompt_tokens", None),
                        "completion_tokens": getattr(usage, "completion_tokens", None),
                        "total_tokens": getattr(usage, "total_tokens", None),
                    },
                }
            except RateLimitError as exc:
                errors.append(f"{model}: rate_limit")
                logger.warning("Featherless rate limited model=%s task_type=%s", model, task_type or "unknown")
            except APITimeoutError as exc:
                errors.append(f"{model}: timeout")
                logger.warning("Featherless timed out model=%s task_type=%s", model, task_type or "unknown")
            except (APIConnectionError, APIError, FeatherlessProviderError) as exc:
                errors.append(f"{model}: {type(exc).__name__}")
                logger.warning("Featherless request failed model=%s task_type=%s error=%s", model, task_type or "unknown", type(exc).__name__)
            except Exception as exc:
                errors.append(f"{model}: {type(exc).__name__}")
                logger.warning("Unexpected Featherless error model=%s task_type=%s error=%s", model, task_type or "unknown", type(exc).__name__)

        raise FeatherlessProviderError(
            "Featherless provider failed for all configured fallback models. Details: " + " | ".join(errors)
        )

    async def generate_json(self, *, prompt: str, task_type: str | None = None, timeout_seconds: float | None = None) -> dict[str, Any]:
        payload = await self.generate(
            prompt=prompt,
            task_type=task_type,
            prefer_json=True,
            timeout_seconds=timeout_seconds,
        )
        return json.loads(payload["content"])

    async def stream(
        self,
        *,
        prompt: str,
        task_type: str | None = None,
        prefer_json: bool = False,
        timeout_seconds: float | None = None,
    ) -> AsyncGenerator[str, None]:
        payload = await self.generate(
            prompt=prompt,
            task_type=task_type,
            prefer_json=prefer_json,
            timeout_seconds=timeout_seconds,
        )
        text = str(payload["content"])
        for idx in range(0, len(text), 120):
            yield text[idx:idx + 120]
            await asyncio.sleep(0)

    async def health_check(self) -> dict[str, Any]:
        if not settings.featherless_enabled or not settings.featherless_api_key:
            return {"ok": False, "configured": False, "reason": "missing_api_key"}
        try:
            result = await self.generate(
                prompt="Reply with exactly the word READY.",
                task_type="quick_task",
                prefer_json=False,
                timeout_seconds=12.0,
            )
            return {
                "ok": "READY" in result["content"].upper(),
                "configured": True,
                "model": result["model"],
                "usage": result.get("usage", {}),
            }
        except Exception as exc:
            logger.warning("Featherless health check failed: %s", type(exc).__name__)
            return {
                "ok": False,
                "configured": True,
                "reason": type(exc).__name__,
            }
