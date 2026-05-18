from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from time import monotonic
from typing import Literal


RunStatus = Literal[
    "running",
    "paused",
    "needs_more_steps",
    "awaiting_final_confirmation",
    "stopped",
    "completed",
    "failed",
]


@dataclass
class BrowserRunState:
    run_id: str
    goal: str
    created_at: float = field(default_factory=monotonic)
    status: RunStatus = "running"
    stop_requested: bool = False
    pause_requested: bool = False
    force_finalize_requested: bool = False
    confirm_publish_requested: bool = False
    extend_steps_requested: int = 0
    manual_stop_reason: str | None = None
    last_phase: str = "planning"
    progress_snapshot: dict[str, Any] = field(default_factory=dict)
    evidence_snapshot: dict[str, Any] = field(default_factory=dict)
    current_page: dict[str, Any] = field(default_factory=dict)
    result_preview: str | None = None
    _signal: asyncio.Event = field(default_factory=asyncio.Event)

    def request_stop(self, reason: str | None = None) -> None:
        self.stop_requested = True
        self.status = "stopped"
        self.manual_stop_reason = reason or "Stopped by user."
        self._signal.set()

    def request_pause(self) -> None:
        self.pause_requested = True
        self.status = "paused"
        self._signal.set()

    def request_resume(self) -> None:
        self.pause_requested = False
        if self.status == "paused":
            self.status = "running"
        self._signal.set()

    def request_continue(self, steps: int) -> None:
        self.extend_steps_requested += max(1, steps)
        self.status = "running"
        self._signal.set()

    def request_force_finalize(self) -> None:
        self.force_finalize_requested = True
        self.status = "running"
        self._signal.set()

    def request_confirm_publish(self) -> None:
        self.confirm_publish_requested = True
        self.status = "running"
        self._signal.set()

    async def wait_for_signal(self, timeout: float) -> bool:
        self._signal.clear()
        try:
            await asyncio.wait_for(self._signal.wait(), timeout)
            return True
        except TimeoutError:
            return False


class BrowserRunManager:
    def __init__(self) -> None:
        self._runs: dict[str, BrowserRunState] = {}

    def register(self, run_id: str, goal: str) -> BrowserRunState:
        state = BrowserRunState(run_id=run_id, goal=goal)
        self._runs[run_id] = state
        return state

    def get(self, run_id: str) -> BrowserRunState | None:
        return self._runs.get(run_id)

    def complete(self, run_id: str, status: RunStatus) -> None:
        state = self._runs.get(run_id)
        if state:
            state.status = status

    def update_snapshot(
        self,
        run_id: str,
        *,
        phase: str | None = None,
        progress: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
        current_page: dict[str, Any] | None = None,
        result_preview: str | None = None,
    ) -> None:
        state = self._runs.get(run_id)
        if not state:
            return
        if phase is not None:
            state.last_phase = phase
        if progress is not None:
            state.progress_snapshot = progress
        if evidence is not None:
            state.evidence_snapshot = evidence
        if current_page is not None:
            state.current_page = current_page
        if result_preview is not None:
            state.result_preview = result_preview

    def cleanup(self, run_id: str) -> None:
        self._runs.pop(run_id, None)


browser_run_manager = BrowserRunManager()
