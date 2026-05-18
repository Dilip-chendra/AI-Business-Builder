"""Agent streaming endpoint â€” Server-Sent Events (SSE).

GET /api/v1/agent/stream?goal=...&business_id=...&apply_actions=...&mode=internal|browser

Streams agent execution events in real-time as the agent thinks and acts.
Each event is a JSON object on a single line, prefixed with "data: ".

Event types:
  start       â€” run started, includes run_id and goal
  thinking    â€” AI is generating the next decision
  step        â€” a step completed (tool + result)
  blocked     â€” safety layer blocked an action
  result      â€” final result text
  done        â€” run finished (status + cost summary)
  error       â€” run failed
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.business_service import BusinessService
from app.services.browser_agent.run_manager import browser_run_manager
from app.services.usage_service import UsageService
from app.utils.text import clean_text, looks_like_structured_blob

router = APIRouter()
logger = logging.getLogger(__name__)


def _sse(event_type: str, data: dict) -> str:
    """Format a single SSE message."""
    payload = json.dumps({"type": event_type, **data}, default=str)
    return f"data: {payload}\n\n"


async def _stream_internal_agent(
    goal: str,
    business_id: str | None,
    apply_actions: bool,
    max_steps: int,
    user_id: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Stream internal agent execution events."""
    from app.agents.safety.cost_tracker import CostLimitExceededError, CostTracker
    from app.agents.safety.permissions import Role
    from app.agents.tools.executor import ToolExecutor
    from app.agents.tools.registry import ToolRegistry
    from app.agents.tools.internal_tools import register_internal_tools
    from app.services.ai_service import AIProviderError, AIService
    from app.core.config import settings
    from uuid import uuid4
    import re

    run_id = str(uuid4())
    role = Role.USER if apply_actions else Role.AGENT

    yield _sse("start", {
        "run_id": run_id,
        "goal": goal,
        "mode": "internal",
        "business_id": business_id,
    })

    # Research goal fast-path
    research_keywords = {
        "find", "search", "research", "competitor", "pricing", "trend",
        "keyword", "seo", "market", "analyze", "compare", "discover",
        "what is", "how much", "top ", "best ", "list of",
    }
    is_research = any(kw in goal.lower() for kw in research_keywords)

    if is_research and not business_id:
        yield _sse("thinking", {"thought": "Analyzing your research question...", "step": 1})
        await asyncio.sleep(0.3)

        try:
            ai = AIService()
            answer_prompt = (
                f"You are an expert business analyst and researcher.\n"
                f"Answer this question with polished markdown prose.\n"
                f"Use ## headings and '-' bullet points only.\n"
                f"Be specific with real numbers and examples.\n"
                f"Do NOT return JSON, tables, emojis, or unusual symbols.\n\n"
                f"Question: {goal}"
            )
            answer = clean_text(await ai.generate_text(answer_prompt))
            if looks_like_structured_blob(answer):
                answer = clean_text(await ai.generate_text(
                    "Rewrite the following draft into polished markdown.\n"
                    "Use ## headings and '-' bullet points only.\n"
                    "Do not output JSON or unusual symbols.\n\n"
                    f"Draft:\n{answer}"
                ))
            yield _sse("step", {
                "step": 1,
                "action": "ai_research",
                "tool": "AI Knowledge Base",
                "thought": "Synthesizing research findings from AI knowledge",
                "result": answer[:500],
                "success": True,
            })
            yield _sse("result", {"text": clean_text(answer)})
            yield _sse("done", {
                "run_id": run_id,
                "status": "done",
                "cost_summary": {"current_step": 1, "total_requests": 1, "total_tokens": len(answer) // 4, "total_cost_usd": 0},
            })
        except AIProviderError as exc:
            yield _sse("error", {"message": str(exc)})
        return

    # Full agent loop with streaming
    cost_tracker = CostTracker(
        max_steps=max_steps,
        max_requests=settings.agent_max_requests_per_run,
        max_tokens=settings.agent_max_tokens_per_run,
        max_cost_usd=settings.agent_max_cost_usd,
    )

    register_internal_tools()
    executor = ToolExecutor(role=role, cost_tracker=cost_tracker, db=db)
    available_tools = ToolRegistry.get().describe_for_prompt(category="internal")
    ai = AIService()

    context_parts = []
    if business_id:
        context_parts.append(f"Business ID: {business_id}")
    context_parts.append(f"User ID: {user_id}")
    context = "\n".join(context_parts)

    observation = f"Goal: {goal}\n\nContext:\n{context}"
    history: list[dict] = []
    action_counts: dict[str, int] = {}

    for step_num in range(1, max_steps + 1):
        # Emit thinking event
        yield _sse("thinking", {
            "thought": f"Planning step {step_num}...",
            "step": step_num,
        })
        await asyncio.sleep(0.1)

        # Build prompt
        history_str = "\n".join(
            f"Step {s.get('step_number', i+1)}: {s.get('action','none')} -> "
            f"{'OK' if s.get('success', True) else 'FAILED'}"
            for i, s in enumerate(history[-4:])
        ) or "No previous steps."

        steps_remaining = max_steps - step_num
        thought_prompt = (
            f"You are an autonomous AI agent. Execute the goal step by step.\n\n"
            f"GOAL: {goal}\n\nAVAILABLE TOOLS:\n{available_tools}\n\n"
            f"CURRENT OBSERVATION (step {step_num}/{max_steps}):\n{observation}\n\n"
            f"RECENT HISTORY:\n{history_str}\n\n"
            f"RULES:\n"
            f"- Return ONLY valid JSON\n"
            f"- Set done=true when goal is achieved\n"
            f"- If steps_remaining <= 2, set done=true and write your best answer\n"
            f"- Steps remaining: {steps_remaining}\n\n"
            f'Return JSON: {{"action":"<tool or none>","business_id":"<UUID if needed>",'
            f'"reason":"<why>","done":false,"result":"<if done=true>"}}'
        )

        try:
            raw = await ai.generate_text(thought_prompt)
            cost_tracker.record_request(provider="groq", input_tokens=len(thought_prompt) // 4)
        except AIProviderError as exc:
            yield _sse("error", {"message": f"AI unavailable: {exc}"})
            break

        # Parse decision
        cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
        decision = None
        try:
            import json as _json
            decision = _json.loads(cleaned)
        except Exception:
            import re as _re
            m = _re.search(r"\{.*\}", cleaned, _re.DOTALL)
            if m:
                try:
                    decision = _json.loads(m.group())
                except Exception:
                    pass

        if not decision:
            observation = "Invalid JSON. Return ONLY a JSON object."
            continue

        tool_name = decision.get("action", "")
        params = {k: v for k, v in decision.items() if k not in ("action", "reason", "done", "thought")}
        reason = decision.get("reason", "")
        is_done = bool(decision.get("done", False))

        # Emit thinking with actual thought
        yield _sse("thinking", {
            "thought": clean_text(reason or f"Executing {tool_name}..."),
            "step": step_num,
            "tool": tool_name,
        })
        await asyncio.sleep(0.2)

        # Loop detection
        if tool_name and tool_name != "none":
            action_counts[tool_name] = action_counts.get(tool_name, 0) + 1
            if action_counts[tool_name] >= 3:
                try:
                    synth = await ai.generate_text(
                        f"Based on the data collected, answer this goal: {goal}\n\n"
                        f"Data collected:\n{observation[:1500]}\n\n"
                        f"Write a clear, structured answer using ## headers and bullet points.\n"
                        f"Do NOT return JSON. Write in plain English."
                    )
                    yield _sse("result", {"text": clean_text(synth.strip())})
                    yield _sse("done", {
                        "run_id": run_id, "status": "done",
                        "cost_summary": cost_tracker.summary(),
                    })
                except Exception:
                    pass
                return

        # Execute tool
        step_record: dict = {
            "step_number": step_num,
            "thought": reason,
            "action": tool_name,
            "params": params,
            "result": None,
            "error": None,
            "success": True,
        }

        if tool_name and tool_name != "none":
            tool_result = await executor.execute(tool_name, params)
            step_record["result"] = tool_result.data
            step_record["error"] = tool_result.error
            step_record["success"] = tool_result.success

            # Check if blocked
            if not tool_result.success and tool_result.error:
                if "BLOCKED" in str(tool_result.error) or "Forbidden" in str(tool_result.error) or "not allowed" in str(tool_result.error):
                    yield _sse("blocked", {
                        "step": step_num,
                        "tool": tool_name,
                        "reason": tool_result.error,
                    })
                    observation = f"Action blocked: {tool_result.error}. Try a different approach."
                else:
                    observation = f"Step {step_num} FAILED: {tool_result.error}. Try differently."
            else:
                import json as _json
                observation = f"Step {step_num} '{tool_name}' succeeded:\n{_json.dumps(tool_result.data, default=str)[:1500]}"

            # Check confirmation required
            if tool_result.metadata.get("requires_confirmation"):
                yield _sse("step", {
                    "step": step_num,
                    "action": tool_name,
                    "tool": tool_name,
                    "thought": reason,
                    "result": "Requires human approval",
                    "success": False,
                    "requires_confirmation": True,
                })
                yield _sse("done", {
                    "run_id": run_id,
                    "status": "waiting_confirmation",
                    "cost_summary": cost_tracker.summary(),
                })
                return

        history.append(step_record)

        # Emit step event
        result_preview = ""
        if step_record.get("result"):
            r = step_record["result"]
            result_preview = clean_text(str(r)[:300] if not isinstance(r, str) else r[:300])

        yield _sse("step", {
            "step": step_num,
            "action": tool_name or "none",
            "tool": tool_name or "none",
            "thought": reason,
            "result": result_preview,
            "success": step_record["success"],
            "error": step_record.get("error"),
        })
        await asyncio.sleep(0.1)

        if is_done:
            final = clean_text(decision.get("result") or reason or "Goal completed.")
            # If the final result looks like JSON, format it as human-readable prose
            final_stripped = final.strip()
            if final_stripped.startswith("{") or final_stripped.startswith("["):
                try:
                    format_prompt = (
                        f"Convert this JSON data into clear, human-readable prose.\n"
                        f"Use ## headers and bullet points. Be specific and actionable.\n"
                        f"Do NOT return JSON. Write in plain English.\n\n"
                        f"Goal: {goal}\n\nData:\n{final_stripped[:2000]}"
                    )
                    formatted = await ai.generate_text(format_prompt)
                    final = clean_text(formatted.strip())
                except Exception:
                    pass  # keep raw if formatting fails
            yield _sse("result", {"text": clean_text(final)})
            yield _sse("done", {
                "run_id": run_id,
                "status": "done",
                "cost_summary": cost_tracker.summary(),
            })
            return

    # Exhausted steps â€” synthesize from what was collected
    try:
        synth = await ai.generate_text(
            f"Based on the data collected, answer this goal: {goal}\n\n"
            f"Data collected:\n{observation[:2000]}\n\n"
            f"Write a clear, structured answer using ## headers and bullet points.\n"
            f"Do NOT return JSON. Write in plain English."
        )
        yield _sse("result", {"text": clean_text(synth.strip())})
        yield _sse("done", {
            "run_id": run_id,
            "status": "done",
            "cost_summary": cost_tracker.summary(),
        })
    except Exception:
        yield _sse("done", {
            "run_id": run_id,
            "status": "limit_exceeded",
            "cost_summary": cost_tracker.summary(),
        })


async def _stream_browser_agent(
    goal: str,
    business_id: str | None,
    db: AsyncSession,
    max_steps: int,
) -> AsyncGenerator[str, None]:
    """Stream browser operator events from the real Playwright + Ollama agent."""
    from app.core.config import settings
    from app.services.browser_agent.browser_agent import BrowserAgent

    agent = BrowserAgent(
        db=db,
        business_id=business_id,
        headless=False,
        max_steps=max(max_steps, 10),
    )

    async for event in agent.iter_events(goal):
        event_type = event.pop("type", "step")
        yield _sse(event_type, event)

@router.get("/stream")
async def stream_agent(
    goal: str = Query(..., min_length=5, max_length=1000),
    mode: str = Query(default="internal", pattern="^(internal|browser)$"),
    business_id: str | None = Query(default=None),
    apply_actions: bool = Query(default=False),
    max_steps: int = Query(default=40, ge=1, le=120),
    token: str = Query(..., description="JWT access token"),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream agent execution as Server-Sent Events.

    Connect with EventSource:
        const es = new EventSource('/api/v1/agent/stream?goal=...&token=...')
        es.onmessage = (e) => { const event = JSON.parse(e.data); ... }
    """
    # Validate token manually (SSE can't use Authorization header easily)
    from app.core.security import decode_access_token
    from jose import JWTError
    from uuid import UUID as _UUID

    try:
        payload = decode_access_token(token)
        user_id = payload["sub"]
    except (JWTError, KeyError):
        async def _auth_error():
            yield _sse("error", {"message": "Invalid or expired token"})
        return StreamingResponse(_auth_error(), media_type="text/event-stream")

    # Verify business ownership
    if business_id:
        try:
            biz = await BusinessService(db).get(_UUID(business_id), user_id=_UUID(user_id))
            if not biz:
                async def _biz_error():
                    yield _sse("error", {"message": "Business not found or access denied"})
                return StreamingResponse(_biz_error(), media_type="text/event-stream")
        except Exception:
            pass

    if mode == "browser":
        await UsageService(db).check_limit(UUID(user_id), "browser_agent_run")
        await UsageService(db).increment_usage(
            UUID(user_id),
            "browser_agent_run",
            business_id=_UUID(business_id) if business_id else None,
            source="browser_agent_stream",
            metadata_json={"goal": goal},
        )
        generator = _stream_browser_agent(goal, business_id, db, max_steps)
    else:
        generator = _stream_internal_agent(
            goal, business_id, apply_actions, max_steps, user_id, db
        )

    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


class BrowserRunControlRequest(BaseModel):
    action: str
    steps: int | None = None


@router.post("/browser/runs/{run_id}/control")
async def control_browser_run(
    run_id: str,
    payload: BrowserRunControlRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    state = browser_run_manager.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Browser run not found")

    action = payload.action.lower().strip()
    if action == "stop":
        state.request_stop("Stopped by user.")
    elif action == "pause":
        state.request_pause()
    elif action == "resume":
        state.request_resume()
    elif action in {"continue", "extend"}:
        state.request_continue(payload.steps or 4)
    elif action == "force_final":
        state.request_force_finalize()
    elif action == "confirm_publish":
        state.request_confirm_publish()
    else:
        raise HTTPException(status_code=400, detail="Unsupported browser run control action")

    return {
        "run_id": run_id,
        "status": state.status,
        "action": action,
        "steps_requested": payload.steps,
    }


@router.post("/browser-agent/{run_id}/continue")
async def continue_browser_run_alias(
    run_id: str,
    payload: BrowserRunControlRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    state = browser_run_manager.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Browser run not found")
    state.request_continue(payload.steps or 6)
    return {"run_id": run_id, "status": state.status, "action": "continue", "steps_requested": payload.steps or 6}


@router.post("/browser-agent/{run_id}/stop")
async def stop_browser_run_alias(
    run_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    state = browser_run_manager.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Browser run not found")
    state.request_stop("Stopped by user.")
    return {"run_id": run_id, "status": state.status, "action": "stop"}


@router.post("/browser-agent/{run_id}/force-answer")
async def force_answer_browser_run_alias(
    run_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    state = browser_run_manager.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Browser run not found")
    state.request_force_finalize()
    return {"run_id": run_id, "status": state.status, "action": "force_final"}


@router.get("/browser-agent/{run_id}/evidence")
async def get_browser_run_evidence(
    run_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    state = browser_run_manager.get(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="Browser run not found")
    return {
        "run_id": run_id,
        "status": state.status,
        "phase": state.last_phase,
        "progress": state.progress_snapshot,
        "evidence": state.evidence_snapshot,
        "current_page": state.current_page,
        "result_preview": state.result_preview,
    }


@router.post("/playground/modify")
async def playground_modify(
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """AI Playground â€” modify a business based on a chat instruction.

    Accepts: { business_id, instruction, field? }
    Returns: { field, old_value, new_value, summary }
    """
    from app.services.ai_service import AIService
    from app.services.business_service import BusinessService
    from app.services.code_version_service import CodeVersionService
    from app.core.cache import cache
    from app.services.project_sync_service import ProjectSyncService
    from uuid import UUID

    business_id = payload.get("business_id")
    instruction = payload.get("instruction", "")

    if not business_id or not instruction:
        return {"error": "business_id and instruction are required"}

    biz = await BusinessService(db).get(UUID(business_id), user_id=current_user.id)
    if not biz:
        return {"error": "Business not found"}

    ai = AIService()

    # Ask AI what field to change and what the new value should be
    # Be very explicit about the allowed field names to prevent hallucination
    analysis_prompt = (
        f"You are an AI assistant modifying a business landing page.\n"
        f"You MUST return a JSON object with EXACTLY these 5 keys: field, new_value, summary, code_preview, page_patch\n\n"
        f"ALLOWED VALUES FOR 'field' (copy exactly, lowercase, no spaces):\n"
        f"  headline       â€” the main hero title\n"
        f"  subheading     â€” the subtitle below the headline\n"
        f"  cta_text       â€” the call-to-action button text\n"
        f"  description    â€” the business description paragraph\n"
        f"  product_pitch  â€” the product/service pitch paragraph\n"
        f"  page_content   â€” use this for pricing, testimonials, FAQ, benefits, features, trust badges, urgency, or colour scheme changes\n\n"
        f"CURRENT PAGE CONTENT:\n"
        f"  headline: {biz.headline}\n"
        f"  subheading: {biz.subheading}\n"
        f"  cta_text: {biz.cta_text}\n"
        f"  description: {biz.description}\n"
        f"  product_pitch: {biz.product_pitch}\n"
        f"  page_content: {json.dumps(biz.page_content or {}, ensure_ascii=True)}\n\n"
        f"USER INSTRUCTION: {instruction}\n\n"
        f"RULES:\n"
        f"- 'field' must be EXACTLY one of: headline, subheading, cta_text, description, product_pitch, page_content\n"
        f"- 'new_value' must be the improved text for top-level field edits. For page_content edits, keep it short and descriptive.\n"
        f"- 'summary' must be one sentence explaining what changed\n"
        f"- 'code_preview' must be a short HTML snippet showing the new value\n"
        f"- 'page_patch' must be an object. Use it only when field='page_content'.\n"
        f"- ALLOWED page_patch keys: pain_points, benefits, features, social_proof, faq, pricing_tiers, urgency_text, trust_badges, color_scheme\n"
        f"- Do NOT use any other field names\n\n"
        f"Return ONLY valid JSON, no prose, no markdown."
    )

    try:
        result = await ai.generate_json(analysis_prompt)
    except Exception as exc:
        return {"error": str(exc)}

    field = result.get("field", "")
    new_value = result.get("new_value", "")
    summary = result.get("summary", "")
    code_preview = result.get("code_preview", "")
    page_patch = result.get("page_patch") or {}

    # Normalize field name â€” handle common AI mistakes
    field_map = {
        "headline": "headline",
        "subheading": "subheading",
        "cta_text": "cta_text",
        "cta": "cta_text",
        "call_to_action": "cta_text",
        "button_text": "cta_text",
        "description": "description",
        "product_pitch": "product_pitch",
        "pitch": "product_pitch",
        "product pitch": "product_pitch",
        "pricing": "page_content",
        "pricing_section": "page_content",
        "testimonials": "page_content",
        "testimonial": "page_content",
        "faq": "page_content",
        "features": "page_content",
        "benefits": "page_content",
        "social_proof": "page_content",
        "page_content": "page_content",
        "value": "headline",  # common AI mistake â€” "Value" usually means headline
        "title": "headline",
        "main_headline": "headline",
        "hero_headline": "headline",
        "sub_headline": "subheading",
        "subtitle": "subheading",
    }
    field_normalized = field_map.get(field.lower().strip().replace(" ", "_"), None)

    allowed_fields = {"headline", "subheading", "cta_text", "description", "product_pitch", "page_content"}

    # If field is still not valid, infer from instruction
    if field_normalized not in allowed_fields:
        instruction_lower = instruction.lower()
        if any(w in instruction_lower for w in ["headline", "title", "heading"]):
            field_normalized = "headline"
        elif any(w in instruction_lower for w in ["subheading", "subtitle", "sub"]):
            field_normalized = "subheading"
        elif any(w in instruction_lower for w in ["cta", "button", "call to action", "click"]):
            field_normalized = "cta_text"
        elif any(w in instruction_lower for w in ["description", "about", "overview"]):
            field_normalized = "description"
        elif any(w in instruction_lower for w in ["pitch", "product", "offer"]):
            field_normalized = "product_pitch"
        elif any(w in instruction_lower for w in ["pricing", "testimonial", "testimonials", "faq", "feature", "benefit", "social proof", "trust badge", "urgency", "colour scheme", "color scheme"]):
            field_normalized = "page_content"
        else:
            field_normalized = "headline"  # safe default

    field = field_normalized

    if not new_value or len(str(new_value).strip()) < 2:
        return {"error": "AI returned an empty new value. Please try a more specific instruction."}

    old_value = getattr(biz, field, "") if field != "page_content" else dict(biz.page_content or {})

    if field == "page_content":
        allowed_page_keys = {
            "pain_points",
            "benefits",
            "features",
            "social_proof",
            "faq",
            "pricing_tiers",
            "urgency_text",
            "trust_badges",
            "color_scheme",
        }
        sanitized_patch = {key: value for key, value in page_patch.items() if key in allowed_page_keys}
        if not sanitized_patch:
            return {"error": "AI did not return a valid structured page update. Please try a more specific section request."}
        next_page_content = dict(biz.page_content or {})
        next_page_content.update(sanitized_patch)
        biz.page_content = next_page_content
        new_value = json.dumps(sanitized_patch, ensure_ascii=True)
    else:
        setattr(biz, field, new_value)
    await db.commit()
    await db.refresh(biz)
    sync_service = ProjectSyncService(biz)
    sync_service.ensure_scaffold()
    sync_service.sync_business_profile()
    await cache.delete(f"business:{biz.id}:{current_user.id}")
    await cache.delete(f"landing:{biz.id}")
    await CodeVersionService(db).create_version(
        user_id=str(current_user.id),
        business_id=str(biz.id),
        file_path="studio/business-profile.json",
        content=sync_service._studio_snapshot(),
        source="ai_studio",
        instruction=instruction,
    )

    return {
        "field": field,
        "old_value": old_value,
        "new_value": new_value,
        "summary": summary,
        "code_preview": code_preview,
        "business_id": business_id,
        "business_name": biz.name,
    }


