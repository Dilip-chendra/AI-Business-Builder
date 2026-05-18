"""ToolExecutor — the single gateway for all agent tool calls.

Every tool invocation MUST go through this class.
The execution pipeline is:

    Permission Check → Action Validation → Cost Check → Execute → Log → Return

No agent may call a tool directly.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from app.agents.safety.cost_tracker import CostTracker, CostLimitExceededError
from app.agents.safety.permissions import ForbiddenError, PermissionService, Role
from app.agents.safety.validator import ActionValidator, ValidationError, REQUIRES_CONFIRMATION
from app.agents.tools.registry import ToolRegistry, ToolResult

logger = logging.getLogger(__name__)


class ToolExecutionError(RuntimeError):
    """Raised when tool execution fails after all safety checks."""


class ToolExecutor:
    """Safe, logged, rate-limited tool executor.

    Args:
        role:         The caller's role (determines permissions).
        cost_tracker: Shared CostTracker for this agent run.
        db:           SQLAlchemy async session (for internal tools).
        session:      BrowserSession (for browser tools).
    """

    def __init__(
        self,
        role: Role | str = Role.AGENT,
        cost_tracker: CostTracker | None = None,
        db=None,
        session=None,
    ) -> None:
        self.role = role if isinstance(role, Role) else Role(role)
        self.cost_tracker = cost_tracker or CostTracker()
        self.db = db
        self.session = session
        self._execution_log: list[dict] = []
        # Duplicate action detection: track last N action signatures
        self._recent_actions: list[str] = []
        self._max_recent = 5

    async def execute(self, tool_name: str, params: dict[str, Any]) -> ToolResult:
        """Execute a tool safely.

        Pipeline:
          1. Permission check
          2. Action validation
          3. Duplicate action detection
          4. Cost limit check
          5. Execute
          6. Log result

        Returns ToolResult (success or failure — never raises unless limits exceeded).
        """
        action = {"tool": tool_name, "params": params}
        start_time = time.monotonic()

        # ── 1. Permission check ───────────────────────────────────────────────
        try:
            PermissionService.check(self.role, tool_name)
        except ForbiddenError as exc:
            result = ToolResult(success=False, error=str(exc), tool_name=tool_name)
            self._log_execution(tool_name, params, result, start_time)
            return result

        # ── 2. Action validation ──────────────────────────────────────────────
        try:
            ActionValidator.validate(action)
        except ValidationError as exc:
            result = ToolResult(success=False, error=str(exc), tool_name=tool_name)
            self._log_execution(tool_name, params, result, start_time)
            return result

        # ── 3. Duplicate action detection ─────────────────────────────────────
        action_sig = f"{tool_name}:{sorted(params.items())}"
        if self._recent_actions.count(action_sig) >= 2:
            result = ToolResult(
                success=False,
                error=f"DUPLICATE_ACTION: '{tool_name}' with same params called 3+ times. Stopping.",
                tool_name=tool_name,
            )
            self._log_execution(tool_name, params, result, start_time)
            return result
        self._recent_actions.append(action_sig)
        if len(self._recent_actions) > self._max_recent:
            self._recent_actions.pop(0)

        # ── 4. Cost limit check ───────────────────────────────────────────────
        try:
            self.cost_tracker.check_limits()
        except CostLimitExceededError as exc:
            raise  # Re-raise — this stops the entire agent run
        self.cost_tracker.ensure_capacity_for_request()

        # ── 5. Requires confirmation? ─────────────────────────────────────────
        if ActionValidator.requires_confirmation(tool_name):
            result = ToolResult(
                success=False,
                error=f"CONFIRMATION_REQUIRED: '{tool_name}' requires human approval before execution.",
                tool_name=tool_name,
                metadata={"requires_confirmation": True, "params": params},
            )
            self._log_execution(tool_name, params, result, start_time)
            return result

        # ── 6. Look up and execute tool ───────────────────────────────────────
        registry = ToolRegistry.get()

        tool_def = registry.get_tool(tool_name)
        if tool_def is None:
            result = ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found in registry or permission matrix.",
                tool_name=tool_name,
            )
            self._log_execution(tool_name, params, result, start_time)
            return result

        try:
            result = await tool_def.handler(params, db=self.db, session=self.session)
        except Exception as exc:
            result = ToolResult(success=False, error=f"Tool execution error: {exc}", tool_name=tool_name)

        # ── 7. Log result ─────────────────────────────────────────────────────
        self._log_execution(tool_name, params, result, start_time)

        if result.success:
            logger.info("Tool executed  tool=%s  duration=%.2fs", tool_name, time.monotonic() - start_time)
        else:
            logger.warning("Tool failed  tool=%s  error=%s", tool_name, result.error)

        return result

    def _log_execution(
        self,
        tool_name: str,
        params: dict,
        result: ToolResult,
        start_time: float,
    ) -> None:
        self._execution_log.append({
            "tool": tool_name,
            "params": params,
            "success": result.success,
            "error": result.error,
            "duration_ms": round((time.monotonic() - start_time) * 1000),
        })

    def get_execution_log(self) -> list[dict]:
        return list(self._execution_log)
