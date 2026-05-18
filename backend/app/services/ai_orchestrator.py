"""Smart AI Provider Orchestration with intelligent routing.

Enhances the base AIService with:
- Task complexity-based provider selection
- Exponential backoff retry strategy
- Retry-After header respect
- Timeout handling
- Provider fallback chain
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from enum import Enum
from typing import Literal

from app.services.ai_service import AIService, AIProviderError
from app.services.ai_telemetry_service import AITelemetryService

logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    """Task complexity levels for provider selection."""
    SIMPLE = "simple"       # < 200 chars, simple text processing
    MEDIUM = "medium"       # 200-500 chars, moderate processing
    COMPLEX = "complex"     # > 500 chars, requires deep reasoning


class ProviderChoice(str, Enum):
    """Provider selection strategies."""
    AUTO = "auto"          # Let orchestrator decide
    FEATHERLESS = "featherless"
    GROQ = "groq"          # Force Groq (fast but rate-limited)
    OLLAMA = "ollama"       # Force Ollama (stable, local)
    HUGGINGFACE = "huggingface"  # Force HuggingFace (reliable)


class SmartAIOrchestrator:
    """Intelligent AI provider selection and orchestration."""

    def __init__(self):
        self.base_ai = AIService()
        self.telemetry = AITelemetryService()
        # Retry configuration
        self.max_retries = 3
        self.initial_delay = 1.0  # Start with 1 second
        self.max_delay = 60.0     # Cap at 60 seconds
        self.backoff_multiplier = 2.0
        self.jitter_ratio = 0.2
        self.provider_timeouts = {
            "featherless": 90.0,
            "groq": 35.0,
            "ollama": 150.0,
            "huggingface": 75.0,
        }

    def _estimate_complexity(self, prompt: str) -> TaskComplexity:
        """Estimate task complexity based on prompt characteristics."""
        length = len(prompt)
        has_json_request = "json" in prompt.lower()
        has_reasoning = any(
            word in prompt.lower()
            for word in ["analyze", "explain", "reason", "compare", "design"]
        )

        if length < 200 and not has_json_request:
            return TaskComplexity.SIMPLE
        elif length < 500 and not has_reasoning:
            return TaskComplexity.MEDIUM
        else:
            return TaskComplexity.COMPLEX

    def _select_provider_for_complexity(
        self, complexity: TaskComplexity
    ) -> list[Literal["featherless", "groq", "ollama", "huggingface"]]:
        """Select provider order based on task complexity.

        Strategy:
        - SIMPLE: Groq first (lowest latency)
        - MEDIUM: Groq first (fast), Ollama fallback
        - COMPLEX: Ollama first (large-context/local stability), then Groq
        - HuggingFace is always the final fallback.
        """
        if complexity == TaskComplexity.SIMPLE:
            return ["groq", "featherless", "ollama", "huggingface"]
        elif complexity == TaskComplexity.MEDIUM:
            return ["featherless", "groq", "ollama", "huggingface"]
        else:  # COMPLEX
            return ["featherless", "ollama", "groq", "huggingface"]

    def _provider_order_for_task(
        self,
        prompt: str,
        task_type: str | None,
    ) -> list[Literal["featherless", "groq", "ollama", "huggingface"]]:
        task = (task_type or "").lower()
        if task in {"browser_planning", "browser_synthesis", "browser_extraction", "coding", "marketing", "ai_studio", "vision"}:
            return ["featherless", "groq", "ollama", "huggingface"]
        if task in {"quick_task", "short_classification", "json_formatting"}:
            return ["groq", "featherless", "ollama", "huggingface"]
        complexity = self._estimate_complexity(prompt)
        logger.info(
            "Task complexity estimated  complexity=%s  providers=%s",
            complexity.value,
            self._select_provider_for_complexity(complexity),
        )
        return self._select_provider_for_complexity(complexity)

    async def _execute_with_provider(
        self,
        prompt: str,
        provider: Literal["featherless", "groq", "ollama", "huggingface"],
        *,
        prefer_json: bool,
        task_type: str | None,
    ) -> str:
        """Execute request with specific provider."""
        timeout = self.provider_timeouts.get(provider, 60.0)
        if provider == "featherless":
            return await asyncio.wait_for(
                self.base_ai.featherless_generate(prompt, task_type=task_type, json_mode=prefer_json),
                timeout=timeout,
            )
        if provider == "groq":
            target = self.base_ai.groq_generate(prompt) if prefer_json else self.base_ai.groq_generate_text(prompt)
            return await asyncio.wait_for(target, timeout=timeout)
        if provider == "ollama":
            return await asyncio.wait_for(self.base_ai.local_generate(prompt, json_mode=prefer_json), timeout=timeout)
        if provider == "huggingface":
            return await asyncio.wait_for(self.base_ai.hf_generate(prompt), timeout=timeout)
        raise ValueError(f"Unknown provider: {provider}")

    def _compute_backoff_delay(self, attempt: int) -> float:
        """Compute jittered exponential backoff delay."""
        base_delay = min(self.initial_delay * (self.backoff_multiplier ** attempt), self.max_delay)
        jitter = base_delay * self.jitter_ratio * random.random()
        return base_delay + jitter

    async def generate_text_with_retry(
        self,
        prompt: str,
        prefer_provider: ProviderChoice = ProviderChoice.AUTO,
        *,
        task_type: str | None = None,
        prefer_json: bool = False,
    ) -> str:
        """Generate text with smart provider selection and exponential backoff.

        Args:
            prompt: The prompt to generate from
            prefer_provider: Override provider selection (AUTO for smart selection)

        Returns:
            Generated text from whichever provider succeeds

        Raises:
            AIProviderError: If all providers fail after retries
        """
        # Determine provider order
        if prefer_provider != ProviderChoice.AUTO:
            provider_order = [prefer_provider.value]
        else:
            provider_order = self._provider_order_for_task(prompt, task_type)

        errors: list[tuple[str, str]] = []

        # Try each provider with retries
        for provider in provider_order:
            for attempt in range(self.max_retries):
                try:
                    started = time.perf_counter()
                    logger.debug(
                        "AI request attempt  provider=%s  attempt=%d/%d",
                        provider,
                        attempt + 1,
                        self.max_retries,
                    )
                    result = await self._execute_with_provider(
                        prompt,
                        provider,
                        prefer_json=prefer_json,
                        task_type=task_type,
                    )
                    logger.info(
                        "AI generation succeeded  provider=%s  attempts=%d",
                        provider,
                        attempt + 1,
                    )
                    await self.telemetry.record_success(
                        provider=provider,
                        latency_ms=int((time.perf_counter() - started) * 1000),
                    )
                    return result

                except AIProviderError as exc:
                    error_msg = str(exc)
                    await self.telemetry.record_failure(provider=provider, reason=error_msg)

                    # Check for rate limit with Retry-After header
                    retry_after = self._extract_retry_after(error_msg)
                    if retry_after and attempt < self.max_retries - 1:
                        logger.warning(
                            "Rate limited by %s  retry_after=%d  attempt=%d",
                            provider,
                            retry_after,
                            attempt + 1,
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    # Calculate exponential backoff
                    if attempt < self.max_retries - 1:
                        delay = self._compute_backoff_delay(attempt)
                        logger.warning(
                            "Provider failed, retrying  provider=%s  "
                            "attempt=%d/%d  delay=%.1fs  error=%s",
                            provider,
                            attempt + 1,
                            self.max_retries,
                            delay,
                            error_msg[:100],
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "Provider exhausted after retries  provider=%s  error=%s",
                            provider,
                            error_msg[:100],
                        )
                        errors.append((provider, error_msg))
                        break

                except asyncio.TimeoutError:
                    error_msg = (
                        f"provider timeout after {self.provider_timeouts.get(provider, 60.0):.0f}s"
                    )
                    await self.telemetry.record_failure(provider=provider, reason=error_msg, timeout=True)
                    logger.warning("Provider timed out  provider=%s  attempt=%d/%d", provider, attempt + 1, self.max_retries)
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(self._compute_backoff_delay(attempt))
                    else:
                        errors.append((provider, error_msg))
                        break

                except Exception as exc:
                    error_msg = str(exc)
                    await self.telemetry.record_failure(provider=provider, reason=error_msg)
                    logger.error(
                        "Unexpected error from provider  provider=%s  error=%s",
                        provider,
                        error_msg[:100],
                    )
                    errors.append((provider, error_msg))
                    break

        # All providers exhausted
        error_summary = " | ".join(
            [f"{provider}: {msg[:80]}" for provider, msg in errors]
        )
        raise AIProviderError(
            f"All AI providers exhausted after {self.max_retries} retries. "
            f"Details: {error_summary}"
        )

    async def generate_json_with_retry(
        self,
        prompt: str,
        prefer_provider: ProviderChoice = ProviderChoice.AUTO,
        *,
        task_type: str | None = None,
    ) -> dict:
        """Generate JSON with smart provider selection and retries."""
        text = await self.generate_text_with_retry(prompt, prefer_provider, task_type=task_type, prefer_json=True)
        return self.base_ai._parse_json(text)

    def _extract_retry_after(self, error_message: str) -> int | None:
        """Extract Retry-After seconds from error message.

        Supports:
        - Retry-After: 30
        - Retry-After: 30s
        - retry after 30
        """
        import re

        match = re.search(r"(?:Retry-After:|retry after)\s*(\d+)", error_message, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    async def health_check(self) -> dict:
        """Check overall health and provider status."""
        health = await self.base_ai.health()
        return {
            "featherless": health.featherless,
            "groq": health.groq,
            "huggingface": health.huggingface,
            "ollama": health.ollama,
            "any_available": health.any_available,
            "recommended_provider": (
                "featherless" if health.featherless else
                "groq" if health.groq else
                "ollama" if health.ollama else
                "huggingface" if health.huggingface else
                None
            ),
        }


# Global singleton for easy access
_orchestrator: SmartAIOrchestrator | None = None


def get_orchestrator() -> SmartAIOrchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SmartAIOrchestrator()
    return _orchestrator


# Convenience functions matching the base AIService interface

async def generate_text_smart(
    prompt: str,
    prefer_provider: ProviderChoice = ProviderChoice.AUTO,
    *,
    task_type: str | None = None,
    prefer_json: bool = False,
) -> str:
    """Generate text using smart provider orchestration."""
    return await get_orchestrator().generate_text_with_retry(
        prompt,
        prefer_provider,
        task_type=task_type,
        prefer_json=prefer_json,
    )


async def generate_json_smart(
    prompt: str,
    prefer_provider: ProviderChoice = ProviderChoice.AUTO,
    *,
    task_type: str | None = None,
) -> dict:
    """Generate JSON using smart provider orchestration."""
    return await get_orchestrator().generate_json_with_retry(prompt, prefer_provider, task_type=task_type)


async def health_check() -> dict:
    """Check orchestrator health."""
    return await get_orchestrator().health_check()
