from __future__ import annotations

import base64
import io
import json
import logging
import re
import time
from typing import Any

import httpx
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)


class ScreenshotAnalyzer:
    """Uses local Ollama vision models to reason over browser screenshots."""

    def __init__(self, vision_model: str | None = None) -> None:
        configured = vision_model or settings.browser_vision_models or settings.browser_vision_model
        self.vision_models = [item.strip() for item in configured.split(",") if item.strip()]
        if not self.vision_models:
            self.vision_models = [settings.browser_vision_model]
        self.ollama_base_url = settings.ollama_base_url.rstrip("/")
        self._availability_cache: dict[str, tuple[bool, float]] = {}
        self._cooldown_until: dict[str, float] = {}

    async def analyze(
        self,
        *,
        base64_image: str,
        goal: str,
        dom_snapshot: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not base64_image:
            return self._fallback("No screenshot available.", dom_snapshot)

        optimized_image = self._optimize_image(base64_image)

        prompt = (
            "You are the visual analysis module for an autonomous browser operator.\n"
            "Return ONLY compact JSON with these keys:\n"
            "- summary\n"
            "- page_type\n"
            "- visible_actions\n"
            "- blockers\n"
            "- next_targets\n"
            "- confidence\n\n"
            f"Goal: {goal}\n"
            f"URL: {(dom_snapshot or {}).get('url', '')}\n"
            f"Title: {(dom_snapshot or {}).get('title', '')}\n"
            "Be concrete. Avoid long explanations."
        )

        last_error = "No vision model responded."
        for index, model_name in enumerate(self.vision_models):
            cooldown_until = self._cooldown_until.get(model_name, 0.0)
            if cooldown_until > time.monotonic():
                last_error = f"Vision model '{model_name}' is cooling down after a recent timeout."
                if index == 0:
                    break
                continue
            if not await self._is_model_available(model_name):
                last_error = f"Vision model '{model_name}' is not available locally."
                continue

            timeout_seconds = (
                settings.browser_vision_timeout_seconds
                if index == 0
                else settings.browser_vision_fallback_timeout_seconds
            )
            result = await self._try_model(
                model_name=model_name,
                prompt=prompt,
                base64_image=optimized_image,
                dom_snapshot=dom_snapshot,
                timeout_seconds=timeout_seconds,
            )
            if result is not None:
                result.setdefault("model", model_name)
                return result
            last_error = f"Vision model '{model_name}' did not complete within {timeout_seconds:.0f}s."
            # For the live browser loop, fail fast after the first installed model misses
            # the latency budget. Only continue to the next model if the current one is
            # unavailable locally.
            break

        return self._fallback(last_error, dom_snapshot)

    async def _try_model(
        self,
        *,
        model_name: str,
        prompt: str,
        base64_image: str,
        dom_snapshot: dict[str, Any] | None,
        timeout_seconds: float,
    ) -> dict[str, Any] | None:
        payload = {
            "model": model_name,
            "prompt": prompt,
            "images": [base64_image],
            "stream": False,
            "format": "json",
            "keep_alive": settings.browser_vision_keep_alive,
            "options": {
                "temperature": 0.1,
                "num_predict": settings.browser_vision_num_predict,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(f"{self.ollama_base_url}/api/generate", json=payload)
                if response.status_code == 404:
                    self._availability_cache[model_name] = (False, time.monotonic())
                    return None
                response.raise_for_status()
                body = response.json()
            raw = str(body.get("response", ""))
            parsed = self._parse(raw, dom_snapshot)
            if parsed.get("confidence", 0) <= 0.2 and "fallback" in parsed.get("summary", "").lower():
                return None
            return parsed
        except Exception as exc:
            logger.warning("Vision analysis failed with %s: %s", model_name, exc)
            self._cooldown_until[model_name] = time.monotonic() + 120
            return None

    async def _is_model_available(self, model_name: str) -> bool:
        cached = self._availability_cache.get(model_name)
        now = time.monotonic()
        if cached and (now - cached[1]) < 300:
            return cached[0]

        available = False
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{self.ollama_base_url}/api/tags")
                response.raise_for_status()
                models = response.json().get("models", [])
            normalized = {str(model.get("name", "")).lower() for model in models}
            desired = model_name.lower()
            available = desired in normalized or f"{desired}:latest" in normalized
        except Exception:
            available = False

        self._availability_cache[model_name] = (available, now)
        return available

    def _parse(self, raw: str, dom_snapshot: dict[str, Any] | None) -> dict[str, Any]:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = raw[start : end + 1]
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                parsed.setdefault("visible_actions", [])
                parsed.setdefault("blockers", [])
                parsed.setdefault("next_targets", [])
                parsed.setdefault("summary", "Visual analysis complete.")
                parsed.setdefault("confidence", 0.5)
                return parsed
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group())
                if isinstance(parsed, dict):
                    parsed.setdefault("confidence", 0.5)
                    return parsed
            except json.JSONDecodeError:
                pass
        return self._fallback(raw[:400], dom_snapshot)

    def _fallback(self, message: str, dom_snapshot: dict[str, Any] | None) -> dict[str, Any]:
        headings = (dom_snapshot or {}).get("headings", [])
        elements = (dom_snapshot or {}).get("elements", [])
        visible_actions = [
            element.get("text") or element.get("placeholder") or element.get("tag")
            for element in elements[:8]
            if element.get("text") or element.get("placeholder") or element.get("tag")
        ]
        return {
            "summary": f"Vision fallback active. {message[:180]}",
            "page_type": "unknown",
            "visible_actions": visible_actions,
            "blockers": (dom_snapshot or {}).get("blockers", []),
            "next_targets": headings[:3],
            "confidence": 0.2,
            "model": "fallback",
        }

    def _optimize_image(self, base64_image: str) -> str:
        try:
            raw = base64.b64decode(base64_image)
            with Image.open(io.BytesIO(raw)) as image:
                image = image.convert("RGB")
                image.thumbnail(
                    (
                        settings.browser_vision_max_image_width,
                        settings.browser_vision_max_image_height,
                    ),
                    Image.Resampling.LANCZOS,
                )
                buffer = io.BytesIO()
                image.save(
                    buffer,
                    format="JPEG",
                    quality=settings.browser_vision_jpeg_quality,
                    optimize=True,
                )
                return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as exc:
            logger.warning("Could not optimize browser screenshot for vision: %s", exc)
            return base64_image
