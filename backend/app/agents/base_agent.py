"""Base agent — defines the contract every agent must implement.

Architecture:
    Input → Reasoning → Decision → Action → Log

Every agent:
1. Receives a structured ``AgentInput``
2. Produces a list of ``AgentDecision`` objects
3. Optionally executes those decisions (``apply=True``)
4. Persists an ``AgentLog`` record for every decision
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import AgentLog

logger = logging.getLogger(__name__)


@dataclass
class AgentInput:
    """Structured context passed to every agent."""

    business_id: UUID
    business_data: dict
    analytics_data: dict
    products: list[dict] = field(default_factory=list)
    extra: dict = field(default_factory=dict)


@dataclass
class AgentDecision:
    """A single decision produced by an agent."""

    action_type: str          # e.g. "update_headline", "suggest_price", "create_product"
    summary: str              # Human-readable description
    payload: dict             # Data needed to execute the action
    confidence: float = 0.8   # 0.0 – 1.0
    auto_apply: bool = False  # Whether the execution agent should apply this automatically


@dataclass
class AgentResult:
    """Aggregated output from one agent run."""

    agent_type: str
    decisions: list[AgentDecision]
    insights: list[str] = field(default_factory=list)
    applied_count: int = 0
    run_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseAgent(ABC):
    """Abstract base for all agents."""

    agent_type: str = "base"

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @abstractmethod
    async def analyze(self, input_data: AgentInput) -> AgentResult:
        """Analyse the input and return decisions + insights."""
        ...

    async def run(self, input_data: AgentInput, apply: bool = False) -> AgentResult:
        """Full agent lifecycle: analyze → optionally apply → log."""
        logger.info(
            "Agent %s starting  business_id=%s  apply=%s",
            self.agent_type,
            input_data.business_id,
            apply,
        )
        result = await self.analyze(input_data)

        for decision in result.decisions:
            if apply and decision.auto_apply:
                try:
                    await self._execute(decision, input_data)
                    result.applied_count += 1
                    await self._log(input_data.business_id, decision, applied=True)
                except Exception as exc:
                    logger.error(
                        "Agent %s failed to execute %s: %s",
                        self.agent_type,
                        decision.action_type,
                        exc,
                    )
                    await self._log(
                        input_data.business_id,
                        decision,
                        applied=False,
                        error=str(exc),
                    )
            else:
                await self._log(input_data.business_id, decision, applied=False)

        logger.info(
            "Agent %s done  decisions=%d  applied=%d",
            self.agent_type,
            len(result.decisions),
            result.applied_count,
        )
        return result

    async def _execute(self, decision: AgentDecision, input_data: AgentInput) -> None:
        """Override in subclasses that can auto-apply decisions."""
        pass

    async def _log(
        self,
        business_id: UUID,
        decision: AgentDecision,
        applied: bool,
        error: str | None = None,
    ) -> None:
        payload = dict(decision.payload)
        if error:
            payload["_error"] = error
        log = AgentLog(
            business_id=business_id,
            agent_type=self.agent_type,
            log_type="action" if applied else "decision",
            summary=decision.summary,
            payload=payload,
            applied=applied,
        )
        self.db.add(log)
        # Use flush (not commit) so all logs in a pipeline are committed together
        # by the coordinator. This avoids N round-trips to the database.
        try:
            await self.db.flush()
        except Exception as exc:
            logger.warning("Agent log flush failed: %s", exc)
            await self.db.rollback()
