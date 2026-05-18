"""Cost and usage tracker for agent runs.

Tracks AI token usage, request counts, and estimated cost per run.
Enforces configurable limits to prevent runaway spending.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Approximate cost per 1K tokens (USD) — conservative estimates
_COST_PER_1K_TOKENS = {
    "groq": 0.0,        # Free tier
    "huggingface": 0.0, # Free tier
    "ollama": 0.0,      # Local — no cost
    "openai": 0.002,    # GPT-3.5 fallback estimate
    "default": 0.001,
}


class CostLimitExceededError(RuntimeError):
    """Raised when a cost or usage limit is exceeded."""


@dataclass
class CostTracker:
    """Tracks usage for a single agent run.

    Limits (all configurable):
        max_requests:  Maximum number of AI API calls per run.
        max_tokens:    Maximum total tokens (input + output) per run.
        max_cost_usd:  Maximum estimated cost in USD per run.
        max_steps:     Maximum agent loop steps per run.
    """

    max_requests: int = 20
    max_tokens: int = 50_000
    max_cost_usd: float = 0.50
    max_steps: int = 10

    # ── Counters (read-only externally) ──────────────────────────────────────
    total_requests: int = field(default=0, init=False)
    total_tokens: int = field(default=0, init=False)
    total_cost_usd: float = field(default=0.0, init=False)
    current_step: int = field(default=0, init=False)
    _request_log: list[dict] = field(default_factory=list, init=False)

    def record_request(
        self,
        provider: str = "default",
        input_tokens: int = 0,
        output_tokens: int = 0,
        metadata: dict | None = None,
    ) -> None:
        """Record one AI API call. Raises CostLimitExceededError if limits exceeded."""
        tokens = input_tokens + output_tokens
        cost_per_k = _COST_PER_1K_TOKENS.get(provider, _COST_PER_1K_TOKENS["default"])
        cost = (tokens / 1000) * cost_per_k

        self.total_requests += 1
        self.total_tokens += tokens
        self.total_cost_usd += cost

        self._request_log.append({
            "provider": provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            **(metadata or {}),
        })

        logger.debug(
            "CostTracker: request=%d  tokens=%d  cost=$%.4f  total_cost=$%.4f",
            self.total_requests,
            tokens,
            cost,
            self.total_cost_usd,
        )

        self.check_limits()

    def increment_step(self) -> None:
        """Increment the step counter. Raises if max_steps exceeded."""
        self.current_step += 1
        if self.current_step > self.max_steps:
            raise CostLimitExceededError(
                f"STEP_LIMIT_EXCEEDED: Agent reached maximum steps ({self.max_steps}). "
                "Stopping to prevent infinite loops."
            )

    def ensure_capacity_for_request(self) -> None:
        """Fail fast when another request/tool execution would exceed limits."""
        if self.total_requests >= self.max_requests:
            raise CostLimitExceededError(
                f"REQUEST_LIMIT_EXCEEDED: {self.total_requests}/{self.max_requests} requests already used."
            )
        if self.total_tokens >= self.max_tokens:
            raise CostLimitExceededError(
                f"TOKEN_LIMIT_EXCEEDED: {self.total_tokens}/{self.max_tokens} tokens already used."
            )
        if self.total_cost_usd >= self.max_cost_usd:
            raise CostLimitExceededError(
                f"COST_LIMIT_EXCEEDED: ${self.total_cost_usd:.4f}/${self.max_cost_usd:.2f} already spent."
            )

    def check_limits(self) -> None:
        """Check all limits. Raises CostLimitExceededError if any are exceeded."""
        if self.total_requests > self.max_requests:
            raise CostLimitExceededError(
                f"REQUEST_LIMIT_EXCEEDED: {self.total_requests}/{self.max_requests} requests used."
            )
        if self.total_tokens > self.max_tokens:
            raise CostLimitExceededError(
                f"TOKEN_LIMIT_EXCEEDED: {self.total_tokens}/{self.max_tokens} tokens used."
            )
        if self.total_cost_usd > self.max_cost_usd:
            raise CostLimitExceededError(
                f"COST_LIMIT_EXCEEDED: ${self.total_cost_usd:.4f}/${self.max_cost_usd:.2f} spent."
            )

    def summary(self) -> dict[str, Any]:
        """Return a summary of usage for logging/display."""
        return {
            "total_requests": self.total_requests,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "current_step": self.current_step,
            "limits": {
                "max_requests": self.max_requests,
                "max_tokens": self.max_tokens,
                "max_cost_usd": self.max_cost_usd,
                "max_steps": self.max_steps,
            },
        }
