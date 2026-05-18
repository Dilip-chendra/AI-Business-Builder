"""AgentController — the autonomous agent loop.

Architecture:
    User Goal → Plan → Loop(Observe → Think → Decide → Validate → Execute → Store) → Result

The controller:
1. Accepts a natural-language goal
2. Uses the AI to plan steps
3. Executes each step through the ToolExecutor (safety-enforced)
4. Stores every action in the database
5. Stops when done, on error, or when limits are reached
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.safety.cost_tracker import CostLimitExceededError, CostTracker
from app.agents.safety.permissions import Role
from app.agents.tools.executor import ToolExecutor
from app.agents.tools.registry import ToolRegistry
from app.services.ai_service import AIProviderError, AIService
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Agent run status ──────────────────────────────────────────────────────────
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_LIMIT_EXCEEDED = "limit_exceeded"
STATUS_WAITING_CONFIRMATION = "waiting_confirmation"


class AgentRun:
    """Represents a single agent execution run."""

    def __init__(
        self,
        run_id: str,
        goal: str,
        business_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        self.run_id = run_id
        self.goal = goal
        self.business_id = business_id
        self.user_id = user_id
        self.status = STATUS_RUNNING
        self.steps: list[dict] = []
        self.result: str | None = None
        self.error: str | None = None
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.finished_at: str | None = None
        self.cost_summary: dict = {}

    def add_step(self, step: dict) -> None:
        self.steps.append({**step, "step_number": len(self.steps) + 1})

    def finish(self, status: str, result: str | None = None, error: str | None = None) -> None:
        self.status = status
        self.result = result
        self.error = error
        self.finished_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "goal": self.goal,
            "business_id": self.business_id,
            "user_id": self.user_id,
            "status": self.status,
            "steps": self.steps,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "cost_summary": self.cost_summary,
        }


class AgentController:
    """Autonomous agent that executes a goal through a safe tool loop.

    Args:
        db:          SQLAlchemy async session.
        role:        Caller's role (controls permissions).
        business_id: Optional business context.
        user_id:     Optional user context.
        max_steps:   Hard limit on loop iterations.
        use_browser: Whether to enable browser tools.
    """

    def __init__(
        self,
        db: AsyncSession,
        role: Role | str = Role.USER,
        business_id: str | None = None,
        user_id: str | None = None,
        max_steps: int = 10,
        use_browser: bool = False,
    ) -> None:
        self.db = db
        self.role = role
        self.business_id = business_id
        self.user_id = user_id
        self.max_steps = max_steps
        self.use_browser = use_browser
        self._ai = AIService()
        self._browser_session = None

    async def run(self, goal: str) -> AgentRun:
        """Execute the agent loop for a given goal.

        Returns an AgentRun with full step history and final result.
        """
        run_id = str(uuid4())
        run = AgentRun(
            run_id=run_id,
            goal=goal,
            business_id=self.business_id,
            user_id=self.user_id,
        )
        cost_tracker = CostTracker(
            max_steps=self.max_steps,
            max_requests=settings.agent_max_requests_per_run,
            max_tokens=settings.agent_max_tokens_per_run,
            max_cost_usd=settings.agent_max_cost_usd,
        )

        logger.info("AgentController starting  run_id=%s  goal=%r", run_id, goal[:100])

        # ── Start browser if needed ───────────────────────────────────────────
        if self.use_browser:
            await self._start_browser()

        executor = ToolExecutor(
            role=self.role,
            cost_tracker=cost_tracker,
            db=self.db,
            session=self._browser_session,
        )

        # ── Register tools ────────────────────────────────────────────────────
        from app.agents.tools.internal_tools import register_internal_tools
        register_internal_tools()
        if self.use_browser:
            from app.agents.tools.browser_tools import register_browser_tools
            register_browser_tools()

        # ── Build context for AI ──────────────────────────────────────────────
        # Only expose tools relevant to the current mode to avoid confusion
        tool_category = None if self.use_browser else "internal"
        available_tools = ToolRegistry.get().describe_for_prompt(category=tool_category)
        context = self._build_context()

        # ── Detect if goal is research-oriented (no internal tools can help) ──
        research_keywords = {
            "find", "search", "research", "competitor", "pricing", "trend",
            "keyword", "seo", "market", "analyze", "compare", "discover",
            "what is", "how much", "top ", "best ", "list of",
        }
        goal_lower = goal.lower()
        is_research_goal = any(kw in goal_lower for kw in research_keywords)
        has_business_context = bool(self.business_id)

        # If it's a pure research goal with no browser, answer from AI knowledge immediately
        if is_research_goal and not self.use_browser and not has_business_context:
            logger.info(
                "AgentController: research goal detected with no browser — "
                "answering from AI knowledge  run_id=%s", run_id
            )
            try:
                answer_prompt = (
                    f"You are an expert business analyst and researcher.\n"
                    f"Answer this question with clear, well-structured, human-readable prose.\n"
                    f"Use bullet points, sections with ## headers, and specific numbers/examples.\n"
                    f"Make it immediately actionable and easy to read.\n"
                    f"Do NOT return JSON. Write in plain English.\n\n"
                    f"Question: {goal}"
                )
                answer = await self._ai.generate_text(answer_prompt)
                run.finish(STATUS_DONE, result=answer.strip())
                run.cost_summary = cost_tracker.summary()
                await self._persist_run(run)
                return run
            except AIProviderError as exc:
                run.finish(STATUS_FAILED, error=f"AI unavailable: {exc}")
                run.cost_summary = cost_tracker.summary()
                await self._persist_run(run)
                return run

        # ── Agent loop ────────────────────────────────────────────────────────
        observation = f"Goal: {goal}\n\nContext:\n{context}"

        # Track repeated actions to detect loops
        action_counts: dict[str, int] = {}

        try:
            for step_num in range(1, self.max_steps + 1):
                cost_tracker.increment_step()

                # ── THINK ─────────────────────────────────────────────────────
                thought_prompt = self._build_thought_prompt(
                    goal=goal,
                    observation=observation,
                    available_tools=available_tools,
                    step_num=step_num,
                    history=run.steps,
                )

                try:
                    raw_decision = await self._ai.generate_text(thought_prompt)
                    cost_tracker.record_request(provider="ollama", input_tokens=len(thought_prompt) // 4)
                except AIProviderError as exc:
                    run.finish(STATUS_FAILED, error=f"AI unavailable: {exc}")
                    break

                # ── DECIDE ────────────────────────────────────────────────────
                decision = self._parse_decision(raw_decision)
                if decision is None:
                    run.add_step({
                        "thought": raw_decision[:500],
                        "action": None,
                        "result": None,
                        "error": "Could not parse AI decision as JSON",
                    })
                    # Give the AI one more chance with a correction prompt
                    observation = "Your last response was not valid JSON. Return ONLY a JSON object."
                    continue

                tool_name = decision.get("action", "")
                params = {k: v for k, v in decision.items()
                          if k not in ("action", "reason", "done", "thought")}
                reason = decision.get("reason", "")
                is_done = bool(decision.get("done", False))

                logger.info(
                    "Step %d  tool=%s  reason=%r  done=%s",
                    step_num, tool_name, reason[:80], is_done,
                )

                # ── Loop detection: if same tool called 3+ times, force done ──
                if tool_name and tool_name != "none":
                    action_counts[tool_name] = action_counts.get(tool_name, 0) + 1
                    if action_counts[tool_name] >= 3:
                        logger.warning(
                            "AgentController: tool '%s' called %d times — forcing synthesis  run_id=%s",
                            tool_name, action_counts[tool_name], run_id,
                        )
                        # Force the agent to synthesize from what it has
                        try:
                            synth_prompt = (
                                f"Based on the data collected so far, provide a complete answer to: {goal}\n\n"
                                f"Data collected:\n{observation}\n\n"
                                f"Give a thorough, specific answer even if data is incomplete."
                            )
                            synthesis = await self._ai.generate_text(synth_prompt)
                            run.finish(STATUS_DONE, result=synthesis.strip())
                        except Exception:
                            run.finish(STATUS_DONE, result=f"Based on available data: {observation[:500]}")
                        break

                # ── EXECUTE ───────────────────────────────────────────────────
                if tool_name and tool_name != "none":
                    tool_result = await executor.execute(tool_name, params)
                    step_record = {
                        "thought": reason,
                        "action": tool_name,
                        "params": params,
                        "result": tool_result.data,
                        "error": tool_result.error,
                        "success": tool_result.success,
                    }

                    # Check if confirmation is required
                    if tool_result.metadata.get("requires_confirmation"):
                        run.add_step(step_record)
                        run.finish(
                            STATUS_WAITING_CONFIRMATION,
                            result="Action requires human approval before proceeding.",
                        )
                        break

                    # Update observation for next step
                    if tool_result.success:
                        observation = (
                            f"Step {step_num} result for '{tool_name}':\n"
                            f"{json.dumps(tool_result.data, default=str)[:2000]}"
                        )
                    else:
                        observation = (
                            f"Step {step_num} FAILED for '{tool_name}': {tool_result.error}\n"
                            "Try a different approach or tool."
                        )
                else:
                    step_record = {"thought": reason, "action": "none", "result": None, "error": None, "success": True}
                    observation = f"Step {step_num}: No action taken. Reason: {reason}"

                run.add_step(step_record)

                # ── EXIT if done ──────────────────────────────────────────────
                if is_done:
                    final_result = decision.get("result") or reason or "Goal completed."
                    run.finish(STATUS_DONE, result=final_result)
                    break

            else:
                # Loop exhausted without done=true
                run.finish(
                    STATUS_LIMIT_EXCEEDED,
                    error=f"Agent reached maximum steps ({self.max_steps}) without completing the goal.",
                )

        except CostLimitExceededError as exc:
            run.finish(STATUS_LIMIT_EXCEEDED, error=str(exc))
        except Exception as exc:
            logger.exception("AgentController unexpected error  run_id=%s", run_id)
            run.finish(STATUS_FAILED, error=f"Unexpected error: {exc}")
        finally:
            run.cost_summary = cost_tracker.summary()
            await self._stop_browser()
            # Persist run to database
            await self._persist_run(run)

        logger.info(
            "AgentController finished  run_id=%s  status=%s  steps=%d",
            run_id, run.status, len(run.steps),
        )
        return run

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_context(self) -> str:
        parts = []
        if self.business_id:
            parts.append(f"Business ID: {self.business_id}")
        if self.user_id:
            parts.append(f"User ID: {self.user_id}")
        parts.append(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        return "\n".join(parts)

    def _build_thought_prompt(
        self,
        goal: str,
        observation: str,
        available_tools: str,
        step_num: int,
        history: list[dict],
    ) -> str:
        history_str = ""
        if history:
            recent = history[-4:]
            history_str = "\n".join(
                f"Step {s.get('step_number', i+1)}: {s.get('action','none')} → "
                f"{'OK' if s.get('success', True) else 'FAILED: ' + str(s.get('error',''))}"
                for i, s in enumerate(recent)
            )

        steps_remaining = self.max_steps - step_num

        return f"""You are an autonomous AI agent completing a specific goal.

GOAL: {goal}

AVAILABLE TOOLS:
{available_tools}

CURRENT OBSERVATION (step {step_num}/{self.max_steps}):
{observation}

RECENT HISTORY:
{history_str or 'No previous steps.'}

CRITICAL RULES:
1. Return ONLY valid JSON — no prose, no markdown, no code fences.
2. If the goal requires web research and no browser tools are available, use action="none" with done=true and write your answer in "result" using your own knowledge.
3. If you have already gathered enough data to answer the goal, set done=true immediately.
4. If the same tool has been called 2+ times with no progress, STOP and synthesize an answer.
5. Never call a tool that cannot help achieve the goal.
6. Steps remaining: {steps_remaining}. If steps_remaining <= 2, you MUST set done=true now and write your best answer in "result".

Return JSON with exactly these keys:
{{
  "action": "<tool_name, or 'none' to skip>",
  "business_id": "<UUID only if the tool requires it>",
  "reason": "<one sentence: why this action moves toward the goal>",
  "done": false,
  "result": "<REQUIRED when done=true: complete, detailed answer to the goal>"
}}"""

    def _parse_decision(self, raw: str) -> dict | None:
        """Parse AI response as JSON decision. Returns None if unparseable."""
        # Strip markdown fences
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            # Try to extract JSON object
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None

    async def _start_browser(self) -> None:
        try:
            from app.agents.tools.browser_tools import BrowserSession
            self._browser_session = BrowserSession()
            await self._browser_session.start(headless=True)
        except ImportError as exc:
            logger.warning("Browser tools unavailable: %s", exc)
            self._browser_session = None
            self.use_browser = False

    async def _stop_browser(self) -> None:
        if self._browser_session:
            await self._browser_session.close()
            self._browser_session = None

    async def _persist_run(self, run: AgentRun) -> None:
        """Store the agent run in the database as AgentLog entries."""
        if not self.business_id:
            return
        try:
            from app.models.agent import AgentLog
            log = AgentLog(
                business_id=UUID(self.business_id),
                agent_type="controller",
                log_type="analysis",
                summary=f"Agent run {run.run_id}: {run.status} — {run.goal[:100]}",
                payload=run.to_dict(),
                applied=run.status == STATUS_DONE,
            )
            self.db.add(log)
            await self.db.commit()
        except Exception as exc:
            logger.warning("Failed to persist agent run: %s", exc)
