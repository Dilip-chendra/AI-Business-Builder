from __future__ import annotations

import asyncio
import json
import logging
import queue
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, AsyncGenerator
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.agent import AgentLog
from app.services.browser_agent.browser_memory import BrowserMemory
from app.services.browser_agent.executor import BrowserExecutor
from app.services.browser_agent.planner import BrowserPlanner
from app.services.browser_agent.run_manager import browser_run_manager
from app.services.browser_agent.screenshot_analyzer import ScreenshotAnalyzer
from app.services.browser_agent.session_manager import SessionManager

logger = logging.getLogger(__name__)


def _describe_exception(exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return message
    return exc.__class__.__name__


@dataclass
class BrowserAgentResult:
    run_id: str
    goal: str
    status: str = "running"
    steps: list[dict[str, Any]] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    result: str | None = None
    error: str | None = None
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str | None = None

    def finish(self, *, status: str, result: str | None = None, error: str | None = None) -> None:
        self.status = status
        self.result = result
        self.error = error
        self.finished_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "status": self.status,
            "steps": self.steps,
            "sources": self.sources,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class BrowserAgent:
    """Real Playwright + Ollama browser operator with streaming support."""

    def __init__(
        self,
        *,
        db: AsyncSession | None = None,
        business_id: str | None = None,
        headless: bool | None = None,
        session_id: str | None = None,
        max_steps: int | None = None,
    ) -> None:
        self.db = db
        self.business_id = business_id
        base_session = session_id or business_id or "default-browser-session"
        self.session_id = str(base_session).replace("/", "_").replace("\\", "_").replace(":", "_")
        self.max_steps = max_steps or settings.browser_agent_max_steps
        self.session_manager = SessionManager(headless=headless, session_id=self.session_id)
        self.memory = BrowserMemory()
        self.planner = BrowserPlanner()
        self.executor = BrowserExecutor(self.session_manager)
        self.screenshot_analyzer = ScreenshotAnalyzer()
        self._last_result: BrowserAgentResult | None = None

    async def iter_events(self, goal: str) -> AsyncGenerator[dict[str, Any], None]:
        if sys.platform == "win32":
            async for event in self._iter_events_threaded(goal):
                yield event
            return

        async for event in self._iter_events_inline(goal):
            yield event

    async def _iter_events_threaded(self, goal: str) -> AsyncGenerator[dict[str, Any], None]:
        event_queue: queue.Queue[dict[str, Any] | object] = queue.Queue()
        sentinel = object()

        def _runner() -> None:
            loop = asyncio.ProactorEventLoop()
            asyncio.set_event_loop(loop)

            async def _consume() -> None:
                try:
                    async for event in self._iter_events_inline(goal):
                        event_queue.put(event)
                except Exception as exc:
                    logger.exception("Threaded browser stream failed: %s", exc)
                    event_queue.put({"type": "error", "message": f"Browser agent failed: {exc or 'Unknown browser error'}"})
                finally:
                    event_queue.put(sentinel)

            loop.run_until_complete(_consume())
            loop.close()

        thread = threading.Thread(target=_runner, name=f"browser-agent-{self.session_id}", daemon=True)
        thread.start()

        while True:
            item = await asyncio.to_thread(event_queue.get)
            if item is sentinel:
                break
            yield item  # type: ignore[misc]

        thread.join(timeout=1)

    async def _iter_events_inline(self, goal: str) -> AsyncGenerator[dict[str, Any], None]:
        result = BrowserAgentResult(run_id=str(uuid4()), goal=goal)
        self._last_result = result
        run_state = browser_run_manager.register(result.run_id, goal)
        goal_profile = self.planner._goal_profile(goal)
        target_sources = self._target_sources_for_goal(goal_profile)
        soft_budget = self._initial_budget(goal_profile=goal_profile, target_sources=target_sources)
        hard_budget = max(soft_budget + (settings.browser_agent_extension_steps * 4), settings.browser_agent_max_steps_hard)
        step_number = 1

        try:
            yield {"type": "start", "run_id": result.run_id, "goal": goal, "mode": "browser"}
            yield {
                "type": "thinking",
                "step": 0,
                "thought": "Launching Chromium session and restoring browser memory.",
                "browser_status": "launching",
                "phase": "planning",
            }

            page = await self.session_manager.start()
            if page.url in {"about:blank", "chrome://newtab/"}:
                await page.goto(self._initial_url_for_goal(goal, goal_profile), wait_until="domcontentloaded", timeout=45000)

            while True:
                if step_number > hard_budget:
                    progress = self.memory.research_progress(goal=goal, target_sources=target_sources)
                    if self._should_finalize(progress):
                        summary = await self._synthesize_final(goal=goal, progress=progress)
                        result.finish(status="done", result=summary)
                        browser_run_manager.update_snapshot(result.run_id, result_preview=summary)
                        final_state = await self._collect_state()
                        yield {
                            "type": "result",
                            "text": summary,
                            "url": final_state["url"],
                            "sources": result.sources,
                            "screenshot": final_state["screenshot"],
                        }
                        break

                    if self._can_auto_extend(progress, hard_budget):
                        soft_budget, hard_budget = self._extend_budgets(soft_budget=soft_budget, hard_budget=hard_budget)
                        yield {
                            "type": "status",
                            "run_id": result.run_id,
                            "status": "running",
                            "message": "The operator needs more evidence, so it is extending the research window automatically.",
                            "phase": "needs_more_steps",
                            "progress": progress,
                            "step_budget": {"soft": soft_budget, "hard": hard_budget},
                            "evidence": self.memory.structured_evidence(limit=5),
                        }
                        continue

                    result.finish(status="needs_more_steps")
                    yield {
                        "type": "status",
                        "run_id": result.run_id,
                        "status": "needs_more_steps",
                        "message": "The agent has useful evidence, but it still needs stronger source coverage before it can finish confidently.",
                        "phase": "needs_more_steps",
                        "progress": progress,
                        "evidence": self.memory.structured_evidence(limit=5),
                    }
                    browser_run_manager.update_snapshot(
                        result.run_id,
                        phase="needs_more_steps",
                        progress=progress,
                        evidence=self.memory.evidence_snapshot(limit=6),
                    )
                    waited = await run_state.wait_for_signal(settings.browser_agent_wait_for_control_seconds)
                    if waited:
                        if run_state.stop_requested:
                            result.finish(status="stopped", error=run_state.manual_stop_reason)
                            yield {
                                "type": "done",
                                "run_id": result.run_id,
                                "status": "stopped",
                                "message": run_state.manual_stop_reason or "Stopped by user.",
                            }
                            break
                        if run_state.force_finalize_requested:
                            summary = await self._synthesize_final(goal=goal, progress=progress)
                            result.finish(status="done", result=summary)
                            browser_run_manager.update_snapshot(result.run_id, result_preview=summary)
                            final_state = await self._collect_state()
                            yield {
                                "type": "result",
                                "text": summary,
                                "url": final_state["url"],
                                "sources": result.sources,
                                "screenshot": final_state["screenshot"],
                            }
                            break
                        if run_state.extend_steps_requested > 0:
                            requested = max(settings.browser_agent_extension_steps, run_state.extend_steps_requested)
                            run_state.extend_steps_requested = 0
                            soft_budget, hard_budget = self._extend_budgets(
                                soft_budget=soft_budget,
                                hard_budget=hard_budget,
                                requested_steps=requested,
                            )
                            result.status = "running"
                            yield {
                                "type": "status",
                                "run_id": result.run_id,
                                "status": "running",
                                "message": "Continuing the research run with a larger step budget.",
                                "phase": "planning",
                                "progress": progress,
                                "step_budget": {"soft": soft_budget, "hard": hard_budget},
                                "evidence": self.memory.structured_evidence(limit=5),
                            }
                            continue

                    summary = await self._synthesize_final(goal=goal, progress=progress)
                    result.finish(status="needs_more_steps", result=summary)
                    browser_run_manager.update_snapshot(result.run_id, result_preview=summary)
                    final_state = await self._collect_state()
                    yield {
                        "type": "result",
                        "text": summary,
                        "url": final_state["url"],
                        "sources": result.sources,
                        "screenshot": final_state["screenshot"],
                    }
                    break

                control_event = await self._handle_run_controls(run_state)
                if control_event is not None:
                    yield control_event
                    if control_event.get("type") == "done":
                        result.finish(status="stopped", result=result.result, error=run_state.manual_stop_reason)
                        break
                    if control_event.get("status") == "paused":
                        continue

                state = await self._collect_state()
                self.memory.observe_state(url=state["url"], tabs=state["tabs"])
                result.sources = self._merge_sources(result.sources, state["url"])
                memory_state = self.memory.summary() | {"tabs": state["tabs"]}
                progress = self.memory.research_progress(goal=goal, target_sources=target_sources)
                phase = self._determine_phase(state["url"], progress, bool(self.memory.evidence), bool(result.result))
                run_state.last_phase = phase
                browser_run_manager.update_snapshot(
                    result.run_id,
                    phase=phase,
                    progress=progress,
                    evidence=self.memory.evidence_snapshot(limit=6),
                    current_page={
                        "url": state["url"],
                        "title": state["title"],
                        "tabs": state["tabs"],
                    },
                    result_preview=result.result,
                )

                yield {
                    "type": "thinking",
                    "step": step_number,
                    "thought": "Inspecting the current page and gathering browser context.",
                    "url": state["url"],
                    "title": state["title"],
                    "screenshot": state["screenshot"],
                    "tabs": state["tabs"],
                    "memory": memory_state,
                    "browser_status": "inspecting",
                    "phase": phase,
                    "progress": progress,
                    "evidence": self.memory.structured_evidence(limit=5),
                }

                if run_state.force_finalize_requested or self._should_finalize(progress):
                    summary = await self._synthesize_final(goal=goal, progress=progress)
                    result.finish(status="done", result=summary)
                    browser_run_manager.update_snapshot(result.run_id, result_preview=summary)
                    yield {
                        "type": "result",
                        "text": summary,
                        "screenshot": state["screenshot"],
                        "url": state["url"],
                        "sources": result.sources,
                    }
                    break

                if self.memory.loop_detected():
                    if self._should_finalize(progress):
                        summary = await self._synthesize_final(goal=goal, progress=progress)
                        result.finish(status="done", result=summary)
                        yield {
                            "type": "result",
                            "text": summary,
                            "screenshot": state["screenshot"],
                            "url": state["url"],
                            "sources": result.sources,
                        }
                        break
                    soft_budget = min(hard_budget, soft_budget + settings.browser_agent_extension_steps)
                    yield {
                        "type": "status",
                        "run_id": result.run_id,
                        "status": "running",
                        "message": "The agent detected a shallow loop and is switching to a broader search strategy.",
                        "phase": "planning",
                        "progress": progress,
                    }

                vision = await self.screenshot_analyzer.analyze(
                    base64_image=state["screenshot"],
                    goal=goal,
                    dom_snapshot=state["dom_snapshot"],
                )
                blocked = state["dom_snapshot"].get("blockers", [])

                thought = self._reasoning_status(vision, blocked)
                yield {
                    "type": "thinking",
                    "step": step_number,
                    "thought": thought,
                    "url": state["url"],
                    "title": state["title"],
                    "screenshot": state["screenshot"],
                    "tabs": state["tabs"],
                    "memory": memory_state,
                    "vision": vision,
                    "browser_status": "blocked" if blocked else "active",
                    "phase": phase,
                    "progress": progress,
                    "evidence": self.memory.structured_evidence(limit=5),
                }

                deterministic_action = self.planner.deterministic_research_action(
                    goal=goal,
                    dom_snapshot=state["dom_snapshot"],
                    memory_state=memory_state,
                    extracted_context=self.memory.extracted_context(),
                    progress=progress,
                )
                if deterministic_action is not None:
                    action = deterministic_action
                else:
                    action = await self.planner.plan_next_action(
                        goal=goal,
                        dom_snapshot=state["dom_snapshot"],
                        vision_analysis=vision,
                        memory_context=self.memory.recent_history_text(),
                        memory_state=memory_state,
                        extracted_context=self.memory.extracted_context(),
                        step_number=step_number,
                        max_steps=soft_budget,
                    )

                duplicate_reason = self.memory.duplicate_action_reason(
                    action,
                    current_url=state["url"],
                    tabs=state["tabs"],
                )
                if duplicate_reason:
                    self.memory.record_rejected_action(
                        step=step_number,
                        action=action,
                        reason=duplicate_reason,
                        url=state["url"],
                    )
                    yield {
                        "type": "thinking",
                        "step": step_number,
                        "thought": f"Loop prevention triggered: {duplicate_reason} Replanning with a different strategy.",
                        "url": state["url"],
                        "title": state["title"],
                        "tabs": state["tabs"],
                        "memory": self.memory.summary() | {"tabs": state["tabs"]},
                        "browser_status": "replanning",
                    }
                    action = self.planner.corrective_action(
                        goal=goal,
                        dom_snapshot=state["dom_snapshot"],
                        vision_analysis=vision,
                        memory_state=self.memory.summary() | {"tabs": state["tabs"]},
                        extracted_context=self.memory.extracted_context(),
                        step_number=step_number,
                        max_steps=soft_budget,
                        reason=duplicate_reason,
                    )
                    second_duplicate_reason = self.memory.duplicate_action_reason(
                        action,
                        current_url=state["url"],
                        tabs=state["tabs"],
                    )
                    if second_duplicate_reason:
                        deterministic_action = self.planner.deterministic_research_action(
                            goal=goal,
                            dom_snapshot=state["dom_snapshot"],
                            memory_state=self.memory.summary() | {"tabs": state["tabs"]},
                            extracted_context=self.memory.extracted_context(),
                            progress=progress,
                        )
                        if deterministic_action is not None:
                            action = deterministic_action
                            second_duplicate_reason = self.memory.duplicate_action_reason(
                                action,
                                current_url=state["url"],
                                tabs=state["tabs"],
                            )
                    if second_duplicate_reason:
                        if not self._should_finalize(progress):
                            action = {
                                "action": "search",
                                "query": self.planner._focused_search_query(goal, goal_profile),
                                "search_engine": "duckduckgo",
                                "reason": "The current path is looping without enough evidence, so return to DuckDuckGo and open a different source.",
                            }
                        else:
                            fallback_result = await self._synthesize_final(goal=goal, progress=progress)
                            result.finish(status="done", result=fallback_result)
                            browser_run_manager.update_snapshot(result.run_id, result_preview=fallback_result)
                            yield {
                                "type": "result",
                                "text": fallback_result,
                                "screenshot": state["screenshot"],
                                "url": state["url"],
                            }
                            break
                action_reason = str(action.get("reason", "")).strip()
                if str(action.get("action", "")).lower() == "done" and not self._planner_done_is_valid(progress, goal_profile):
                    action = self.planner.corrective_action(
                        goal=goal,
                        dom_snapshot=state["dom_snapshot"],
                        vision_analysis=vision,
                        memory_state=self.memory.summary() | {"tabs": state["tabs"]},
                        extracted_context=self.memory.extracted_context(),
                        step_number=step_number,
                        max_steps=soft_budget,
                        reason="The task is not complete yet because source coverage and evidence quality are still below the research threshold.",
                    )
                    action_reason = str(action.get("reason", "")).strip() or "The agent needs more evidence before it can finish."

                execution = await self.executor.execute(action, state["dom_snapshot"])
                next_state = await self._collect_state()
                self.memory.observe_state(url=next_state["url"], tabs=next_state["tabs"])
                result.sources = self._merge_sources(result.sources, next_state["url"])

                step_record = {
                    "step": step_number,
                    "action": action.get("action", "unknown"),
                    "tool": action.get("action", "unknown"),
                    "thought": action_reason,
                    "params": action,
                    "result": execution.message,
                    "success": execution.success,
                    "blocked": execution.blocked,
                    "url": next_state["url"],
                    "title": next_state["title"],
                    "data": execution.data,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                result.steps.append(step_record)
                self.memory.add_step(
                    step=step_number,
                    action=action,
                    thought=action_reason,
                    result=self._memory_result_preview(execution.message, execution.data),
                    success=execution.success,
                    url=next_state["url"],
                    blocked=execution.blocked,
                    metadata=execution.data,
                )

                yield {
                    "type": "step",
                    "step": step_number,
                    "action": action.get("action", "unknown"),
                    "tool": action.get("action", "unknown"),
                    "thought": action_reason,
                    "result": execution.message,
                    "success": execution.success,
                    "blocked": execution.blocked,
                    "url": next_state["url"],
                    "title": next_state["title"],
                    "tabs": next_state["tabs"],
                    "memory": self.memory.summary() | {"tabs": next_state["tabs"]},
                    "sources": result.sources,
                    "screenshot": next_state["screenshot"],
                    "data": execution.data,
                    "phase": self._determine_phase(next_state["url"], self.memory.research_progress(goal=goal, target_sources=target_sources), bool(self.memory.evidence), False),
                    "progress": self.memory.research_progress(goal=goal, target_sources=target_sources),
                    "evidence": self.memory.structured_evidence(limit=5),
                }
                browser_run_manager.update_snapshot(
                    result.run_id,
                    phase=self._determine_phase(next_state["url"], self.memory.research_progress(goal=goal, target_sources=target_sources), bool(self.memory.evidence), False),
                    progress=self.memory.research_progress(goal=goal, target_sources=target_sources),
                    evidence=self.memory.evidence_snapshot(limit=6),
                    current_page={
                        "url": next_state["url"],
                        "title": next_state["title"],
                        "tabs": next_state["tabs"],
                    },
                )

                if execution.blocked:
                    yield {
                        "type": "blocked",
                        "step": step_number,
                        "tool": action.get("action", "unknown"),
                        "reason": execution.message,
                        "url": next_state["url"],
                        "screenshot": next_state["screenshot"],
                    }

                if action.get("action") == "done":
                    if goal_profile == "publishing":
                        publish_events = await self._await_publish_confirmation(
                            run_state=run_state,
                            result=result,
                            current_state=next_state,
                            progress=self.memory.research_progress(goal=goal, target_sources=target_sources),
                            step_number=step_number,
                        )
                        async for event in publish_events:
                            yield event
                        break
                    final_text = await self._synthesize_final(
                        goal=goal,
                        progress=self.memory.research_progress(goal=goal, target_sources=target_sources),
                        preferred_text=str(action.get("result") or execution.message).strip(),
                    )
                    result.finish(status="done", result=final_text)
                    browser_run_manager.update_snapshot(result.run_id, result_preview=final_text)
                    yield {
                        "type": "result",
                        "text": final_text,
                        "url": next_state["url"],
                        "sources": result.sources,
                        "screenshot": next_state["screenshot"],
                    }
                    break
                step_number += 1
                if step_number > soft_budget and step_number <= hard_budget:
                    progress = self.memory.research_progress(goal=goal, target_sources=target_sources)
                    if not progress["coverage_met"]:
                        soft_budget = min(hard_budget, soft_budget + settings.browser_agent_extension_steps)
                        yield {
                            "type": "status",
                            "run_id": result.run_id,
                            "status": "needs_more_steps",
                            "message": "More research is needed, so the agent is extending the run budget automatically.",
                            "phase": "needs_more_steps",
                            "progress": progress,
                            "step_budget": {"soft": soft_budget, "hard": hard_budget},
                            "evidence": self.memory.structured_evidence(limit=5),
                        }
                    elif self._should_finalize(progress):
                        summary = await self._synthesize_final(goal=goal, progress=progress)
                        result.finish(status="done", result=summary)
                        browser_run_manager.update_snapshot(result.run_id, result_preview=summary)
                        final_state = await self._collect_state()
                        yield {
                            "type": "result",
                            "text": summary,
                            "url": final_state["url"],
                            "sources": result.sources,
                            "screenshot": final_state["screenshot"],
                        }
                        break

            if result.finished_at is None:
                result.finish(status=result.status or "done", result=result.result)

            yield {
                "type": "done",
                "run_id": result.run_id,
                "status": result.status,
                "sources": result.sources,
                "screenshot": (await self._collect_state())["screenshot"],
            }
        except Exception as exc:
            logger.exception("BrowserAgent failed: %s", exc)
            error_message = _describe_exception(exc)
            result.finish(status="failed", error=error_message)
            yield {"type": "error", "message": f"Browser agent failed: {error_message}"}
            yield {"type": "done", "run_id": result.run_id, "status": "failed", "sources": result.sources}
        finally:
            browser_run_manager.complete(
                result.run_id,
                result.status if result.status in {"completed", "failed", "stopped", "needs_more_steps", "awaiting_final_confirmation", "paused", "running"} else "completed",
            )
            await self.session_manager.close()

    async def run(self, goal: str) -> BrowserAgentResult:
        async for _ in self.iter_events(goal):
            pass
        assert self._last_result is not None
        await self._persist(self._last_result)
        return self._last_result

    async def _collect_state(self) -> dict[str, Any]:
        await self.session_manager.enforce_tab_policy()
        screenshot = await self.session_manager.capture_screenshot_base64()
        dom_snapshot = await self.session_manager.get_dom_snapshot()
        tabs = await self.session_manager.list_tabs()
        return {
            "screenshot": screenshot,
            "dom_snapshot": dom_snapshot,
            "url": dom_snapshot.get("url", ""),
            "title": dom_snapshot.get("title", ""),
            "tabs": tabs,
        }

    async def _persist(self, result: BrowserAgentResult) -> None:
        if not self.db or not self.business_id:
            return
        try:
            log = AgentLog(
                business_id=UUID(self.business_id),
                agent_type="browser",
                log_type="analysis" if result.status == "done" else "error",
                summary=f"Browser operator run {result.run_id}: {result.status}",
                payload=result.to_dict(),
                applied=False,
            )
            self.db.add(log)
            await self.db.commit()
        except Exception as exc:
            logger.warning("Could not persist browser run %s: %s", result.run_id, exc)

    @staticmethod
    def _merge_sources(existing: list[str], current_url: str | None) -> list[str]:
        merged = list(existing)
        if not current_url or not current_url.startswith("http"):
            return merged
        normalized = BrowserMemory.normalize_url(current_url)
        if not normalized:
            return merged
        if any(engine in normalized for engine in ("duckduckgo.com", "google.", "bing.com")):
            return merged
        if normalized not in merged:
            merged.append(normalized)
        return merged

    @staticmethod
    def _memory_result_preview(message: str, data: dict[str, Any]) -> str:
        if not data:
            return message
        return f"{message} | data={json.dumps(data, default=str)[:1200]}"

    @staticmethod
    def _reasoning_status(vision: dict[str, Any], blockers: list[str]) -> str:
        if blockers:
            return f"Detected possible blockers: {', '.join(blockers)}. Replanning with fallback strategy."
        summary = str(vision.get("summary", "")).strip()
        if summary.lower().startswith("vision fallback active"):
            summary = "Using DOM-first fallback while local vision warms up."
        targets = ", ".join(vision.get("next_targets", [])[:3])
        if targets:
            return f"{summary} Next likely targets: {targets}"
        return summary or "Inspecting the current browser state."

    async def _handle_run_controls(self, run_state) -> dict[str, Any] | None:
        if run_state.stop_requested:
            return {
                "type": "done",
                "run_id": run_state.run_id,
                "status": "stopped",
                "message": run_state.manual_stop_reason or "Stopped by user.",
            }

        while run_state.pause_requested:
            yield_event = {
                "type": "status",
                "run_id": run_state.run_id,
                "status": "paused",
                "message": "Research paused. Resume when you want the browser to continue.",
                "phase": "paused",
            }
            await run_state.wait_for_signal(1.0)
            if run_state.stop_requested:
                return {
                    "type": "done",
                    "run_id": run_state.run_id,
                    "status": "stopped",
                    "message": run_state.manual_stop_reason or "Stopped by user.",
                }
            return yield_event
        return None

    def _should_finalize(self, progress: dict[str, Any]) -> bool:
        if progress.get("completion_ready"):
            return True
        return (
            progress.get("coverage_met")
            and float(progress.get("avg_quality", 0.0)) >= 0.28
            and float(progress.get("avg_relevance", 0.0)) >= 0.16
            and int(progress.get("unique_domains", 0)) >= max(3, min(int(progress.get("target_sources", 0)), 5))
            and int(progress.get("useful_sources", 0)) >= int(progress.get("target_sources", 0))
        )

    @staticmethod
    def _initial_url_for_goal(goal: str, goal_profile: str) -> str:
        if goal_profile != "publishing":
            return "https://duckduckgo.com/"

        goal_lower = goal.lower()
        if "linkedin" in goal_lower:
            return "https://www.linkedin.com/feed/"
        if "twitter" in goal_lower or "x " in goal_lower or "x.com" in goal_lower:
            return "https://x.com/home"
        if "instagram" in goal_lower:
            return "https://www.instagram.com/"
        if "facebook" in goal_lower:
            return "https://www.facebook.com/"
        if "wordpress" in goal_lower:
            return "https://wordpress.com/"
        return "https://duckduckgo.com/"

    @staticmethod
    def _can_auto_extend(progress: dict[str, Any], hard_budget: int) -> bool:
        useful_sources = int(progress.get("useful_sources", 0))
        target_sources = int(progress.get("target_sources", 0))
        has_research_signal = useful_sources > 0 or float(progress.get("progress_score", 0.0)) >= 0.18
        still_missing_coverage = useful_sources < target_sources or not bool(progress.get("coverage_met"))
        return has_research_signal and still_missing_coverage and hard_budget < settings.browser_agent_max_steps_hard

    @staticmethod
    def _extend_budgets(*, soft_budget: int, hard_budget: int, requested_steps: int | None = None) -> tuple[int, int]:
        extra = max(settings.browser_agent_extension_steps, requested_steps or 0)
        new_soft = min(settings.browser_agent_max_steps_hard, soft_budget + extra)
        new_hard = min(
            settings.browser_agent_max_steps_hard,
            max(hard_budget + extra, new_soft + settings.browser_agent_extension_steps * 2),
        )
        return new_soft, new_hard

    async def _await_publish_confirmation(
        self,
        *,
        run_state,
        result: BrowserAgentResult,
        current_state: dict[str, Any],
        progress: dict[str, Any],
        step_number: int,
    ) -> AsyncGenerator[dict[str, Any], None]:
        run_state.status = "awaiting_final_confirmation"
        yield {
            "type": "status",
            "run_id": run_state.run_id,
            "status": "awaiting_final_confirmation",
            "message": "The browser flow is ready for the final publish click. Review it, then confirm to publish.",
            "phase": "awaiting_final_confirmation",
            "progress": progress,
            "url": current_state["url"],
            "title": current_state["title"],
            "screenshot": current_state["screenshot"],
            "tabs": current_state["tabs"],
        }

        waited = await run_state.wait_for_signal(300.0)
        if run_state.stop_requested:
            result.finish(status="stopped", error=run_state.manual_stop_reason)
            yield {
                "type": "done",
                "run_id": run_state.run_id,
                "status": "stopped",
                "message": run_state.manual_stop_reason or "Stopped before the final publish click.",
            }
            return

        if waited and run_state.confirm_publish_requested:
            confirm_action = self._build_publish_confirmation_action(current_state["dom_snapshot"])
            if confirm_action is None:
                summary = await self._synthesize_final(
                    goal=result.goal,
                    progress=progress,
                    preferred_text="The post draft is ready, but the final publish button could not be located automatically.",
                )
                result.finish(status="done", result=summary)
                yield {
                    "type": "result",
                    "text": summary,
                    "url": current_state["url"],
                    "sources": result.sources,
                    "screenshot": current_state["screenshot"],
                }
                return

            execution = await self.executor.execute(confirm_action, current_state["dom_snapshot"])
            confirmed_state = await self._collect_state()
            self.memory.observe_state(url=confirmed_state["url"], tabs=confirmed_state["tabs"])
            self.memory.add_step(
                step=step_number + 1,
                action=confirm_action,
                thought="Final human confirmation received. Completing the publish step.",
                result=self._memory_result_preview(execution.message, execution.data),
                success=execution.success,
                url=confirmed_state["url"],
                blocked=execution.blocked,
                metadata=execution.data,
            )
            yield {
                "type": "step",
                "step": step_number + 1,
                "action": confirm_action.get("action", "click"),
                "tool": confirm_action.get("action", "click"),
                "thought": "Final human confirmation received. Completing the publish step.",
                "result": execution.message,
                "success": execution.success,
                "blocked": execution.blocked,
                "url": confirmed_state["url"],
                "title": confirmed_state["title"],
                "tabs": confirmed_state["tabs"],
                "screenshot": confirmed_state["screenshot"],
                "data": execution.data,
                "phase": "completed",
                "progress": progress,
            }
            final_text = await self._synthesize_final(
                goal=result.goal,
                progress=progress,
                preferred_text="The browser workflow completed and the final publish action was confirmed.",
            )
            result.finish(status="done", result=final_text)
            yield {
                "type": "result",
                "text": final_text,
                "url": confirmed_state["url"],
                "sources": result.sources,
                "screenshot": confirmed_state["screenshot"],
            }
            return

        summary = await self._synthesize_final(
            goal=result.goal,
            progress=progress,
            preferred_text="The browser workflow reached the final confirmation stage, but no final publish confirmation was received.",
        )
        result.finish(status="done", result=summary)
        yield {
            "type": "result",
            "text": summary,
            "url": current_state["url"],
            "sources": result.sources,
            "screenshot": current_state["screenshot"],
        }

    async def _synthesize_final(self, *, goal: str, progress: dict[str, Any], preferred_text: str | None = None) -> str:
        preferred = (preferred_text or "").strip()
        if (
            preferred
            and preferred.startswith("## ")
            and "## Executive Summary" in preferred
            and "## Key Findings" in preferred
        ):
            return preferred
        return await self.planner.summarize(
            goal=goal,
            extracted_context=self.memory.extracted_context(),
            evidence_digest=self.memory.report_context(limit=6),
            memory_context=self.memory.synthesis_history_text(),
            evidence=self.memory.structured_evidence(limit=6),
            progress=progress,
        )

    @staticmethod
    def _determine_phase(url: str, progress: dict[str, Any], has_evidence: bool, has_result: bool) -> str:
        url_lower = (url or "").lower()
        if has_result:
            return "completed"
        if "google." in url_lower or "bing.com" in url_lower or "duckduckgo.com" in url_lower:
            return "searching"
        if progress.get("completion_ready") and has_evidence:
            return "synthesizing"
        if has_evidence:
            return "analyzing"
        if progress.get("unique_sources", 0) > 0:
            return "opening_sources"
        return "planning"

    @staticmethod
    def _planner_done_is_valid(progress: dict[str, Any], goal_profile: str) -> bool:
        if goal_profile == "publishing":
            return True
        return bool(progress.get("completion_ready")) or (
            int(progress.get("useful_sources", 0)) >= int(progress.get("target_sources", 0))
            and int(progress.get("unique_domains", 0)) >= max(3, min(int(progress.get("target_sources", 0)), 5))
            and float(progress.get("avg_relevance", 0.0)) >= 0.14
            and float(progress.get("avg_quality", 0.0)) >= 0.24
        )

    @staticmethod
    def _target_sources_for_goal(goal_profile: str) -> int:
        if goal_profile in {"keyword_research", "competitor_research", "pricing_research", "general_research"}:
            return 6
        return 1

    def _initial_budget(self, *, goal_profile: str, target_sources: int) -> int:
        base = max(self.max_steps, 32)
        if goal_profile == "pricing_research":
            return max(base, target_sources * 7 + 8)
        if goal_profile == "keyword_research":
            return max(base, target_sources * 7 + 6)
        if goal_profile == "competitor_research":
            return max(base, target_sources * 7 + 8)
        if goal_profile == "general_research":
            return max(base, target_sources * 6 + 10)
        return max(base, 18)

    @staticmethod
    def _build_publish_confirmation_action(dom_snapshot: dict[str, Any]) -> dict[str, Any] | None:
        publish_tokens = ("publish", "post", "share", "submit", "launch")
        avoid_tokens = ("draft", "preview", "cancel", "close", "back")
        best_match: dict[str, Any] | None = None
        for element in dom_snapshot.get("elements", []):
            tag = str(element.get("tag", "")).lower()
            if tag not in {"button", "a", "input"}:
                continue
            haystack = " ".join(
                [
                    str(element.get("text", "")),
                    str(element.get("name", "")),
                    str(element.get("placeholder", "")),
                    str(element.get("href", "")),
                ]
            ).lower()
            if not any(token in haystack for token in publish_tokens):
                continue
            if any(token in haystack for token in avoid_tokens):
                continue
            best_match = element
            if "publish" in haystack or "post" in haystack:
                break
        if best_match is None or best_match.get("id") is None:
            return None
        return {
            "action": "click",
            "element_id": int(best_match["id"]),
            "reason": "Final human approval was received, so click the visible publish control now.",
        }
