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
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.agent import AgentLog
from app.models.marketing import MarketingCampaign
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


def _classify_internal_goal(goal: str) -> str:
    """Classify goals for the Internal Agent without treating AI as live web search."""
    text = goal.lower()
    platform_markers = {
        "publish", "post to", "connect linkedin", "connect instagram", "send email",
        "google ads", "meta ads", "facebook page", "gmail", "wordpress",
    }
    code_markers = {
        "change code", "edit file", "modify component", "update page", "tsx",
        "css", "preview", "landing page", "hero section",
    }
    live_markers = {
        "current", "latest", "right now", "today", "live", "real website",
        "website", "web page", "extract", "scrape", "serp", "search results",
        "search volume", "keyword volume", "ranking", "rankings",
        "competitor pricing", "competitors pricing", "current pricing",
        "exact pricing", "top 3 competitors pricing", "compare real",
        "research current", "trending now", "currently trending",
    }

    if any(marker in text for marker in platform_markers):
        return "platform_action"
    if any(marker in text for marker in code_markers):
        return "code_project"
    if any(marker in text for marker in live_markers):
        return "live_web"
    if any(marker in text for marker in {"product", "analytics", "business", "pricing", "campaign", "marketing", "strategy", "seo", "keyword"}):
        return "internal_data"
    return "reasoning"


def _is_internal_orchestration_goal(goal: str) -> bool:
    return _classify_internal_goal(goal) in {"live_web", "platform_action", "code_project", "internal_data", "reasoning"}


def _research_progress(evidence: list[dict], sources: list[str], provider_used: str) -> dict:
    useful_sources = len([item for item in evidence if item])
    source_count = len([source for source in sources if source])
    target_sources = 3 if useful_sources or source_count else 0
    score = 0.0
    if useful_sources or source_count:
        score = min(0.75, 0.45 + (max(useful_sources, source_count) * 0.06))
    structured_density = 0.0
    if useful_sources:
        signal_count = 0
        for item in evidence:
            if isinstance(item, dict):
                signal_count += len([value for value in item.values() if value])
        structured_density = round(signal_count / max(useful_sources, 1), 1)
    return {
        "progress_score": round(score, 2),
        "useful_sources": useful_sources,
        "extracted_sources": useful_sources,
        "unique_sources": source_count,
        "target_sources": target_sources,
        "coverage_met": bool(score >= 0.6),
        "structured_density": structured_density,
        "provider_used": provider_used,
    }


def _goal_terms(goal: str) -> set[str]:
    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "find", "create",
        "research", "analyze", "analyse", "suggest", "generate", "top", "best",
        "business", "businesses", "tools", "platforms", "online", "current",
    }
    terms = {
        token
        for token in "".join(char.lower() if char.isalnum() else " " for char in goal).split()
        if len(token) >= 3 and token not in stopwords
    }
    aliases: dict[str, set[str]] = {
        "seo": {"keyword", "keywords", "search", "ranking", "content"},
        "fitness": {"coach", "coaching", "health", "wellness", "workout"},
        "pricing": {"price", "plan", "plans", "subscription", "tier", "tiers"},
        "productivity": {"digital", "products", "tools", "workflow"},
        "course": {"courses", "learning", "creator", "education"},
        "competitor": {"competitors", "competition", "alternatives"},
    }
    expanded = set(terms)
    for term in list(terms):
        expanded.update(aliases.get(term, set()))
    return expanded


def _cached_report_relevance(goal: str, report: dict) -> float:
    terms = _goal_terms(goal)
    if not terms:
        return 0.0
    text = " ".join(
        clean_text(str(value or ""))
        for value in [
            report.get("summary"),
            report.get("result"),
            json.dumps(report.get("evidence") or [], default=str),
            " ".join(str(source) for source in (report.get("sources") or [])),
        ]
    ).lower()
    matches = sum(1 for term in terms if term in text)
    return round(matches / max(len(terms), 1), 2)


def _evidence_from_products(products: list[dict]) -> list[dict]:
    return [
        {
            "type": "internal_product",
            "source_type": "internal_database",
            "title": product.get("name") or "Product",
            "summary": product.get("description") or "",
            "data": product,
            "useful": True,
        }
        for product in products
    ]


def _report_to_text(report: dict) -> str:
    parts = [str(report.get("title") or "Agent Report"), "", str(report.get("summary") or "")]
    for section in report.get("sections") or []:
        heading = section.get("heading") or "Section"
        content = section.get("content") or ""
        items = section.get("items") or []
        parts.extend(["", heading, content])
        parts.extend(f"- {item}" for item in items)
    recommendations = report.get("recommendations") or []
    if recommendations:
        parts.extend(["", "Recommendations"])
        parts.extend(f"- {item}" for item in recommendations)
    return clean_text("\n".join(part for part in parts if part is not None))


def _insufficient_report(goal: str, attempted: list[dict], provider_used: str, reason: str) -> dict:
    return {
        "title": "Insufficient Evidence",
        "summary": reason,
        "sections": [
            {
                "heading": "What Was Attempted",
                "content": "The agent checked available real evidence sources and did not find enough verified data to complete the task.",
                "items": [
                    clean_text(str(item.get("result") or item.get("error") or item.get("tool") or item.get("strategy") or "Attempted source"))
                    for item in attempted[-6:]
                ],
            },
            {
                "heading": "Next Step",
                "content": "Run this task in Browser mode for live website extraction, add verified internal data, or connect an official data/search integration.",
                "items": [],
            },
        ],
        "evidence": [],
        "sources": [],
        "recommendations": [
            "Use Browser mode when the answer requires current external websites.",
            "Add products, competitor records, or verified reports to internal data for API-first mode.",
        ],
        "confidence": 0.0,
        "status": "insufficient_evidence",
        "provider_used": provider_used,
        "data_mode": "none",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "goal": goal,
    }


def _needs_browser_report(goal: str, attempted: list[dict], provider_used: str = "ai_service_router") -> dict:
    return {
        "title": "Live Website Evidence Required",
        "summary": (
            "This objective needs fresh external evidence. The Internal Agent will not use AI provider memory "
            "as verified live data, so it should be routed to Browser Agent for website extraction."
        ),
        "sections": [
            {
                "heading": "Why Internal Mode Stopped",
                "content": "AI providers can plan and reason, but they cannot verify current web facts without extracted sources.",
                "items": [
                    "No relevant internal or saved evidence was available for this live research request.",
                    "No fake sources or invented pricing, trends, or keyword evidence were generated.",
                ],
            },
            {
                "heading": "Recommended Route",
                "content": "Run Browser Agent to collect live pages, extract useful evidence, and then synthesize a verified report.",
                "items": [
                    "Open fresh sources related to the goal.",
                    "Extract facts, keyword ideas, pricing, or competitor details from the pages.",
                    "Return a structured report with source cards and confidence based on evidence quality.",
                ],
            },
        ],
        "evidence": [],
        "sources": [],
        "recommendations": [
            "Run Browser Agent for live website extraction.",
            "Add verified internal reports if you want Internal Agent to reuse them later.",
        ],
        "next_action": {
            "label": "Run Browser Agent",
            "action": "run_browser_agent",
        },
        "confidence": 0.0,
        "status": "needs_browser_agent",
        "task_type": "live_web",
        "provider_used": provider_used,
        "evidence_type": "browser_required",
        "data_mode": "browser_required",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "goal": goal,
        "attempted": attempted[-6:],
    }


async def _ai_reasoning_report(goal: str, context: dict, task_type: str) -> tuple[dict, str]:
    from app.services.ai_service import AIService
    from app.core.config import settings

    prompt = (
        "You are the Internal Agent for AI Business Builder.\n"
        "Use AI providers for reasoning, planning, strategy, marketing generation, and recommendations.\n"
        "Do not claim live web research, verified external sources, or current competitor facts.\n"
        "For SEO keyword idea tasks, generate useful keyword suggestions, long-tail keywords, local SEO ideas, buyer-intent terms, blog topics, hashtags, and landing-page recommendations.\n"
        "Clearly state that exact search volume, live SERP rankings, and current competitor data require Browser Agent or an SEO data integration.\n"
        "Return ONLY valid JSON with this exact shape:\n"
        "{\n"
        '  "status": "completed|insufficient_data|failed",\n'
        f'  "task_type": "{task_type}",\n'
        '  "title": "short title",\n'
        '  "summary": "plain summary without markdown",\n'
        '  "sections": [{"heading": "string", "content": "string", "items": ["string"]}],\n'
        '  "recommendations": ["string"],\n'
        '  "next_action": {"label": "string", "action": "string"},\n'
        '  "confidence": 0.0,\n'
        '  "evidence_type": "internal|user_provided|saved_report|ai_reasoning",\n'
        '  "disclaimer": "string"\n'
        "}\n\n"
        f"GOAL:\n{goal}\n\n"
        f"AVAILABLE_CONTEXT:\n{json.dumps(context, default=str, ensure_ascii=True)[:8000]}"
    )
    raw = await asyncio.wait_for(AIService().generate_text(prompt, task_type="ai_studio", prefer_json=True), timeout=min(max(settings.ai_timeout_seconds, 30), 90))
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("AI provider returned non-object JSON")
    parsed.setdefault("status", "completed")
    parsed.setdefault("task_type", task_type)
    parsed.setdefault("title", "Internal Agent Result")
    parsed.setdefault("summary", "")
    parsed.setdefault("sections", [])
    parsed.setdefault("recommendations", [])
    parsed.setdefault("next_action", {"label": "Create Marketing Draft", "action": "create_marketing_draft"})
    parsed.setdefault("confidence", 0.65)
    parsed.setdefault("evidence_type", "ai_reasoning")
    parsed["evidence"] = []
    parsed.setdefault("sources", [])
    parsed.setdefault("provider_used", "ai_service_router")
    parsed.setdefault("disclaimer", "Generated from configured AI provider reasoning; not live search-volume, SERP, or current competitor data.")
    parsed.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    parsed.setdefault("goal", goal)
    parsed["data_mode"] = parsed.get("evidence_type") or "ai_reasoning"
    return parsed, "ai_service_router"


async def _ai_structured_analysis(goal: str, context: dict, evidence: list[dict]) -> tuple[dict, str]:
    from app.services.ai_service import AIService
    from app.core.config import settings

    prompt = (
        "You are the Internal Agent for an autonomous AI business operating system.\n"
        "Use configured AI providers for reasoning, but never invent evidence.\n"
        "If evidence is empty, status MUST be insufficient_evidence and confidence MUST be 0.\n"
        "If evidence exists, synthesize only from that evidence.\n"
        "Return ONLY valid JSON with this exact shape:\n"
        "{\n"
        '  "title": "short title",\n'
        '  "summary": "plain summary without markdown",\n'
        '  "sections": [{"heading": "string", "content": "string", "items": ["string"]}],\n'
        '  "evidence": [],\n'
        '  "recommendations": ["string"],\n'
        '  "confidence": 0.0,\n'
        '  "status": "completed|insufficient_evidence|failed",\n'
        '  "data_mode": "internal|cached|browser|mixed|none"\n'
        "}\n\n"
        f"GOAL:\n{goal}\n\n"
        f"CONTEXT:\n{json.dumps(context, default=str, ensure_ascii=True)[:5000]}\n\n"
        f"VERIFIED_EVIDENCE:\n{json.dumps(evidence, default=str, ensure_ascii=True)[:7000]}"
    )
    raw = await asyncio.wait_for(AIService().generate_text(prompt, task_type="ai_studio", prefer_json=True), timeout=min(max(settings.ai_timeout_seconds, 8), 25))
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("AI provider returned non-object JSON")
    parsed.setdefault("sections", [])
    parsed.setdefault("evidence", evidence)
    parsed.setdefault("recommendations", [])
    parsed.setdefault("sources", [])
    parsed.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    parsed.setdefault("goal", goal)
    parsed["provider_used"] = "ai_service_router"
    if not evidence:
        parsed["status"] = "insufficient_evidence"
        parsed["confidence"] = 0.0
        parsed["data_mode"] = "none"
    return parsed, "ai_service_router"


async def _stream_api_first_research_agent(
    *,
    goal: str,
    business_id: str | None,
    user_id: str,
    run_id: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Internal Agent flow using internal data + AI reasoning, with Browser routing for live evidence."""
    from app.services.ai_service import AIProviderError
    from app.services.product_service import ProductService

    steps: list[dict] = []
    evidence: list[dict] = []
    sources: list[str] = []
    ignored_cached_reports: list[dict] = []
    task_type = _classify_internal_goal(goal)
    state = "planning"

    yield _sse("thinking", {
        "step": 1,
        "state": state,
        "strategy": "internal_agent_router",
        "thought": f"Classified the objective as {task_type.replace('_', ' ')} and selected the correct execution route.",
        "progress": 8,
    })

    products: list[dict] = []
    if business_id:
        state = "researching"
        yield _sse("thinking", {
            "step": 2,
            "state": state,
            "strategy": "internal_database",
            "thought": "Checking internal product records once. Empty results will trigger escalation, not a retry loop.",
            "progress": 18,
        })
        try:
            product_rows = await ProductService(db).list(UUID(str(business_id)))
            products = [
                {
                    "name": product.name,
                    "price": str(product.price),
                    "category": product.category,
                    "description": product.description,
                }
                for product in product_rows
            ]
            steps.append({"tool": "list_products", "strategy": "internal_database", "success": True, "count": len(products)})
            yield _sse("step", {
                "step": 2,
                "state": state,
                "action": "list_products",
                "tool": "Internal Products API",
                "thought": "Internal product check completed.",
                "result": f"{len(products)} product records found.",
                "success": True,
            })
        except Exception as exc:
            steps.append({"tool": "list_products", "strategy": "internal_database", "success": False, "error": str(exc)})
            yield _sse("step", {
                "step": 2,
                "state": "retrying",
                "action": "list_products",
                "tool": "Internal Products API",
                "thought": "Internal product API failed. Switching strategy instead of retrying.",
                "result": "",
                "success": False,
                "error": str(exc),
            })

    state = "evaluating"
    yield _sse("thinking", {
        "step": 3,
        "state": state,
        "strategy": "cached_reports",
        "thought": "Checking saved agent reports once and filtering them for relevance to the current goal.",
        "progress": 35,
    })
    cached_reports: list[dict] = []
    if business_id:
        try:
            report_rows = await db.execute(
                select(AgentLog)
                .where(
                    AgentLog.business_id == UUID(str(business_id)),
                    AgentLog.log_type == "report",
                )
                .order_by(AgentLog.created_at.desc())
                .limit(5)
            )
            for report in report_rows.scalars().all():
                payload = report.payload or {}
                report_sources = payload.get("sources") or []
                report_evidence = payload.get("evidence") or []
                cached_reports.append(
                    {
                        "agent_type": report.agent_type,
                        "summary": report.summary,
                        "result": payload.get("result") or "",
                        "sources": report_sources,
                        "evidence": report_evidence,
                        "created_at": report.created_at.isoformat() if report.created_at else None,
                        "source_type": "cached_report",
                    }
                )
                cached_reports[-1]["relevance_score"] = _cached_report_relevance(goal, cached_reports[-1])
                if report_sources and report_evidence and cached_reports[-1]["relevance_score"] >= 0.35:
                    evidence.append(
                        {
                            "type": "cached_report",
                            "source_type": "cached_report",
                            "title": report.summary,
                            "summary": clean_text(str(payload.get("result") or report.summary))[:1000],
                            "sources": report_sources,
                            "created_at": report.created_at.isoformat() if report.created_at else None,
                            "relevance_score": cached_reports[-1]["relevance_score"],
                            "useful": True,
                        }
                    )
                    sources.extend(str(source) for source in report_sources)
                elif cached_reports[-1]["relevance_score"] < 0.35:
                    ignored_cached_reports.append(cached_reports[-1])
            steps.append({"tool": "cached_reports", "strategy": "cached_reports", "success": True, "count": len(cached_reports)})
            yield _sse("step", {
                "step": 3,
                "state": state,
                "action": "cached_reports",
                "tool": "Agent Report Cache",
                "thought": "Cached report check completed.",
                "result": f"{len(cached_reports)} cached reports checked; {len(ignored_cached_reports)} ignored as unrelated.",
                "success": True,
                "data": {"ignored_cached_reports": len(ignored_cached_reports), "relevance_threshold": 0.35},
            })
        except Exception as exc:
            steps.append({"tool": "cached_reports", "strategy": "cached_reports", "success": False, "error": str(exc)})

    if task_type == "live_web" and not evidence:
        steps.append({"tool": "browser_route", "strategy": "browser_required", "success": True, "status": "needs_browser_agent"})
        report = _needs_browser_report(goal, steps)
        final_text = _report_to_text(report)
        progress_payload = _research_progress([], [], report["provider_used"])
        progress_payload["progress_score"] = 0.0
        progress_payload["useful_sources"] = 0
        yield _sse("step", {
            "step": 4,
            "state": "needs_browser_agent",
            "action": "route_to_browser_agent",
            "tool": "Browser Agent Route",
            "thought": "This needs live website evidence. Internal mode will not invent current web facts from AI memory.",
            "result": "Ready to run Browser Agent for verified website extraction.",
            "success": True,
            "progress": progress_payload,
            "report": report,
        })
        yield _sse("result", {"text": final_text, "report": report, "evidence": [], "sources": [], "confidence": 0.0, "progress": progress_payload, "status": "needs_browser_agent"})
        if business_id:
            await _persist_agent_report(
                db,
                business_id=business_id,
                agent_type="internal_agent",
                goal=goal,
                run_id=run_id,
                status="needs_browser_agent",
                result_text=final_text,
                steps=steps,
                evidence=[],
                sources=[],
                task={
                    "label": "Internal Agent Route",
                    "strategy": "browser_required",
                    "states": ["planning", "evaluating", "needs_browser_agent"],
                },
                progress={**progress_payload, "report": report, "ignored_cached_reports": ignored_cached_reports},
            )
        yield _sse("done", {
            "run_id": run_id,
            "status": "needs_browser_agent",
            "state": "needs_browser_agent",
            "cost_summary": {"current_step": len(steps), "total_requests": 0, "total_tokens": 0, "total_cost_usd": 0},
        })
        return

    product_evidence = _evidence_from_products(products)

    if task_type in {"platform_action", "code_project"}:
        action = "connect_integration" if task_type == "platform_action" else "open_ai_studio"
        report = {
            "title": "Specialized Workflow Required",
            "summary": "This request should be handled by a dedicated platform workflow rather than Internal Agent free-form reasoning.",
            "sections": [{"heading": "Route", "content": "Use the specialized module so the app can execute real actions with permissions and persistence.", "items": []}],
            "recommendations": ["Use the matching workflow module instead of a simulated internal action."],
            "next_action": {"label": "Open Workflow", "action": action},
            "confidence": 0.0,
            "status": "needs_integration" if task_type == "platform_action" else "needs_code_project",
            "task_type": task_type,
            "provider_used": "internal_agent_router",
            "evidence_type": "specialized_workflow_required",
            "data_mode": "specialized_workflow_required",
            "evidence": [],
            "sources": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "goal": goal,
        }
        final_text = _report_to_text(report)
        yield _sse("result", {"text": final_text, "report": report, "evidence": [], "sources": [], "confidence": 0.0, "progress": _research_progress([], [], "internal_agent_router"), "status": report["status"]})
        yield _sse("done", {"run_id": run_id, "status": report["status"], "state": report["status"], "cost_summary": {"current_step": len(steps), "total_requests": 0, "total_tokens": 0, "total_cost_usd": 0}})
        return

    state = "synthesizing"
    yield _sse("thinking", {
        "step": 4,
        "state": state,
        "strategy": "ai_provider_synthesis",
        "thought": "Using configured AI providers for reasoning and structured output. AI output will be labeled as reasoning, not live evidence.",
        "progress": 74,
    })

    context = {
        "goal": goal,
        "internal_products": products,
        "relevant_cached_reports": [report for report in cached_reports if report.get("relevance_score", 0) >= 0.35],
        "ignored_cached_reports": ignored_cached_reports,
        "execution_priority": [
            "internal_database",
            "internal_backend_apis",
            "official_integrations",
            "cached_reports",
            "ai_provider_reasoning",
            "browser_agent_fallback",
        ],
    }
    provider_used = "ai_service_router"
    try:
        if task_type in {"reasoning", "internal_data"}:
            report, provider_used = await _ai_reasoning_report(goal, context, task_type)
            if product_evidence and any(marker in goal.lower() for marker in {"analyze my", "existing products", "my products", "based on my products"}):
                report["evidence"] = product_evidence
                report["evidence_type"] = "internal"
                report["data_mode"] = "internal"
        elif evidence:
            report, provider_used = await _ai_structured_analysis(goal, context, evidence)
        else:
            report, provider_used = await _ai_reasoning_report(goal, context, task_type)
    except (AIProviderError, asyncio.TimeoutError, Exception) as exc:
        report = _insufficient_report(
            goal,
            steps,
            provider_used,
            f"AI provider analysis failed or timed out: {clean_text(str(exc))[:300]}",
        )

    failed_reasoning = (
        report.get("status") in {"failed", "insufficient_evidence"}
        or "insufficient evidence" in str(report.get("title", "")).lower()
        or "ai provider analysis failed" in str(report.get("summary", "")).lower()
    )
    if task_type in {"reasoning", "internal_data"} and not failed_reasoning:
        report["status"] = "completed"
        report["evidence_type"] = report.get("evidence_type") or "ai_reasoning"
        report["data_mode"] = report.get("data_mode") or report["evidence_type"]

    report_sources = report.get("sources") or []
    if isinstance(report_sources, list):
        sources.extend(str(source) for source in report_sources if source)

    if report.get("evidence_type") == "ai_reasoning":
        sources = []
        evidence = []

    unique_sources = []
    for source in sources:
        if source and source not in unique_sources:
            unique_sources.append(source)
    sources = unique_sources[:12]

    evidence = report.get("evidence") if isinstance(report.get("evidence"), list) else evidence
    progress_payload = _research_progress(evidence, sources, provider_used)
    if not evidence and report.get("status") == "completed":
        progress_payload["progress_score"] = float(report.get("confidence") or 0.65)
    confidence = float(report.get("confidence") or progress_payload["progress_score"] or 0.0)
    if report.get("status") in {"insufficient_evidence", "needs_browser_agent"} or (not evidence and task_type == "live_web"):
        confidence = 0.0
    report["confidence"] = confidence
    report["sources"] = sources
    report["evidence"] = evidence
    report["provider_used"] = provider_used
    final_text = _report_to_text(report)
    final_status = str(report.get("status") or ("completed" if evidence else "insufficient_evidence"))

    state = "validating"
    yield _sse("thinking", {
        "step": 6,
        "state": state,
        "strategy": "completion_check",
        "thought": "Validating that the final answer includes findings, evidence, recommendations, and confidence.",
        "progress": 90,
        "confidence": confidence,
    })

    steps.append(
        {
            "tool": "ai_provider_synthesis",
            "strategy": "ai_provider_synthesis",
            "success": final_status == "completed",
            "provider_used": provider_used,
            "evidence_count": len(evidence),
            "source_count": len(sources),
            "status": final_status,
        }
    )

    yield _sse("step", {
        "step": 6,
        "state": final_status,
        "action": "synthesize_report",
        "tool": "Internal Agent Orchestrator",
        "thought": "AI provider reasoning completed and produced a structured answer.",
        "result": final_text[:500],
        "success": final_status == "completed",
        "provider_used": provider_used,
        "evidence_count": len(evidence),
        "sources": sources,
        "progress": progress_payload,
        "report": report,
    })
    yield _sse("result", {"text": final_text, "report": report, "evidence": evidence, "sources": sources, "confidence": confidence, "progress": progress_payload, "status": final_status})

    if business_id:
        await _persist_agent_report(
            db,
            business_id=business_id,
            agent_type="internal_agent",
            goal=goal,
            run_id=run_id,
            status=final_status,
            result_text=final_text,
            steps=steps,
            evidence=evidence,
            sources=sources,
            task={
                "label": "API-first internal research",
                "strategy": "internal_db_to_ai_synthesis",
                "states": ["planning", "researching", "escalating", "synthesizing", "validating", "completed"],
            },
            progress={**progress_payload, "report": report},
        )

    yield _sse("done", {
        "run_id": run_id,
        "status": final_status,
        "state": final_status,
        "cost_summary": {"current_step": len(steps), "total_requests": 1, "total_tokens": len(final_text) // 4, "total_cost_usd": 0},
    })


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

    if _is_internal_orchestration_goal(goal):
        async for event in _stream_api_first_research_agent(
            goal=goal,
            business_id=business_id,
            user_id=user_id,
            run_id=run_id,
            db=db,
        ):
            yield event
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
                    final_text = clean_text(synth.strip())
                    yield _sse("result", {"text": final_text})
                    if business_id:
                        await _persist_agent_report(
                            db,
                            business_id=business_id,
                            agent_type="internal_agent",
                            goal=goal,
                            run_id=run_id,
                            status="done",
                            result_text=final_text,
                            steps=history,
                            evidence=[],
                            sources=[],
                        )
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
            final_text = clean_text(final)
            yield _sse("result", {"text": final_text})
            if business_id:
                await _persist_agent_report(
                    db,
                    business_id=business_id,
                    agent_type="internal_agent",
                    goal=goal,
                    run_id=run_id,
                    status="done",
                    result_text=final_text,
                    steps=history,
                    evidence=[],
                    sources=[],
                )
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
        final_text = clean_text(synth.strip())
        yield _sse("result", {"text": final_text})
        if business_id:
            await _persist_agent_report(
                db,
                business_id=business_id,
                agent_type="internal_agent",
                goal=goal,
                run_id=run_id,
                status="done",
                result_text=final_text,
                steps=history,
                evidence=[],
                sources=[],
            )
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

    run_id = ""
    final_text = ""
    steps: list[dict] = []
    evidence: list[dict] = []
    sources: list[str] = []
    task_plan: dict = {}
    progress_snapshot: dict = {}
    async for event in agent.iter_events(goal):
        event_copy = dict(event)
        event_type = event.pop("type", "step")
        if event_copy.get("run_id"):
            run_id = str(event_copy["run_id"])
        if isinstance(event_copy.get("task"), dict):
            task_plan = event_copy["task"]
        if isinstance(event_copy.get("progress"), dict):
            progress_snapshot = event_copy["progress"]
        if event_type == "step":
            steps.append(event_copy)
        if event_copy.get("evidence"):
            raw_evidence = event_copy["evidence"]
            if isinstance(raw_evidence, list):
                evidence = raw_evidence
            elif isinstance(raw_evidence, dict):
                evidence = list(raw_evidence.values()) if raw_evidence else []
        if event_copy.get("sources") and isinstance(event_copy["sources"], list):
            sources = [str(item) for item in event_copy["sources"]]
        if event_type == "result":
            final_text = clean_text(str(event_copy.get("text") or event_copy.get("result") or ""))
        if event_type == "done" and business_id:
            await _persist_agent_report(
                db,
                business_id=business_id,
                agent_type="browser_agent",
                goal=goal,
                run_id=run_id,
                status=str(event_copy.get("status") or "done"),
                result_text=final_text or str(event_copy.get("result_preview") or ""),
                steps=steps,
                evidence=evidence,
                sources=sources,
                task=task_plan,
                progress=progress_snapshot,
            )
        yield _sse(event_type, event)


async def _persist_agent_report(
    db: AsyncSession,
    *,
    business_id: str,
    agent_type: str,
    goal: str,
    run_id: str,
    status: str,
    result_text: str,
    steps: list[dict],
    evidence: list[dict],
    sources: list[str],
    task: dict | None = None,
    progress: dict | None = None,
) -> None:
    try:
        report = AgentLog(
            business_id=UUID(str(business_id)),
            agent_type=agent_type,
            log_type="report" if status in {"done", "completed"} else "error",
            summary=(result_text or goal)[:500],
            payload={
                "run_id": run_id,
                "goal": goal,
                "status": status,
                "result": result_text,
                "report": progress.get("report") if isinstance(progress, dict) else None,
                "steps": steps[-80:],
                "evidence": evidence[-40:],
                "sources": sources[-40:],
                "task": task or {},
                "progress": progress or {},
            },
            applied=False,
        )
        db.add(report)
        await db.commit()
    except Exception:
        logger.exception("Failed to persist agent report")
        await db.rollback()

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


class AgentReportMarketingBriefRequest(BaseModel):
    business_id: str | None = None


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


@router.get("/reports")
async def list_agent_reports(
    business_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return durable browser/internal agent reports for the selected business."""
    try:
        biz = await BusinessService(db).get(UUID(str(business_id)), user_id=current_user.id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid business_id") from exc
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    result = await db.execute(
        select(AgentLog)
        .where(
            AgentLog.business_id == UUID(str(business_id)),
            AgentLog.log_type.in_(["report", "error"]),
        )
        .order_by(AgentLog.created_at.desc())
        .limit(limit)
    )
    reports = result.scalars().all()
    return [
        {
            "id": str(report.id),
            "business_id": str(report.business_id),
            "agent_type": report.agent_type,
            "log_type": report.log_type,
            "summary": report.summary,
            "payload": report.payload or {},
            "applied": report.applied,
            "created_at": report.created_at.isoformat() if report.created_at else None,
            "updated_at": report.updated_at.isoformat() if report.updated_at else None,
        }
        for report in reports
    ]


@router.post("/reports/{report_id}/marketing-brief")
async def create_marketing_brief_from_report(
    report_id: str,
    payload: AgentReportMarketingBriefRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Convert a persisted research report into a real editable Marketing draft."""
    try:
        report_uuid = UUID(str(report_id))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid report_id") from exc

    report = await db.get(AgentLog, report_uuid)
    if not report or report.log_type not in {"report", "error"}:
        raise HTTPException(status_code=404, detail="Agent report not found")

    if payload.business_id and str(report.business_id) != str(payload.business_id):
        raise HTTPException(status_code=400, detail="Report does not belong to the selected business")

    biz = await BusinessService(db).get(UUID(str(report.business_id)), user_id=current_user.id)
    if not biz:
        raise HTTPException(status_code=404, detail="Business not found")

    report_payload = report.payload or {}
    content = _marketing_brief_content_from_report(report_payload, report.summary)
    campaign = MarketingCampaign(
        business_id=report.business_id,
        campaign_type="research_brief",
        name=content["title"][:200],
        status="draft",
        content=content,
        targeting={
            "source": "browser_agent_report",
            "agent_report_id": str(report.id),
            "goal": report_payload.get("goal") or report.summary,
            "task_label": (report_payload.get("task") or {}).get("label"),
        },
        metrics={
            "research_confidence": (report_payload.get("progress") or {}).get("progress_score"),
            "useful_sources": (report_payload.get("progress") or {}).get("useful_sources"),
            "structured_density": (report_payload.get("progress") or {}).get("structured_density"),
        },
    )
    db.add(campaign)
    await db.flush()
    report.applied = True
    next_payload = dict(report_payload)
    linked_campaigns = list(next_payload.get("linked_campaign_ids") or [])
    linked_campaigns.append(str(campaign.id))
    next_payload["linked_campaign_ids"] = linked_campaigns
    report.payload = next_payload
    await db.commit()
    await db.refresh(campaign)
    return _campaign_to_dict(campaign)


def _marketing_brief_content_from_report(payload: dict, fallback_summary: str) -> dict:
    goal = clean_text(str(payload.get("goal") or fallback_summary or "Research brief"))
    result = clean_text(str(payload.get("result") or fallback_summary or ""))
    task = payload.get("task") or {}
    progress = payload.get("progress") or {}
    evidence = payload.get("evidence") or []
    sources = [str(source) for source in (payload.get("sources") or []) if source]

    prices: list[str] = []
    keywords: list[str] = []
    entities: list[str] = []
    features: list[str] = []
    evidence_cards: list[dict] = []
    for item in evidence[:12]:
        if not isinstance(item, dict):
            continue
        extracted = item.get("extracted_data") or {}
        prices.extend(str(value) for value in extracted.get("prices", [])[:5] if value)
        keywords.extend(str(value) for value in (extracted.get("keyword_candidates") or extracted.get("signals") or [])[:8] if value)
        entities.extend(str(value) for value in extracted.get("entities", [])[:6] if value)
        features.extend(str(value) for value in extracted.get("features", [])[:5] if value)
        evidence_cards.append(
            {
                "title": clean_text(str(item.get("title") or item.get("url") or ""))[:180],
                "url": str(item.get("url") or ""),
                "summary": clean_text(str(item.get("summary") or ""))[:600],
                "key_points": [clean_text(str(point))[:220] for point in item.get("key_points", [])[:5]],
                "prices": [str(value) for value in extracted.get("prices", [])[:5]],
                "keywords": [str(value) for value in (extracted.get("keyword_candidates") or extracted.get("signals") or [])[:8]],
            }
        )

    def unique(items: list[str], limit: int) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for item in items:
            cleaned = clean_text(item).strip()
            key = cleaned.lower()
            if cleaned and key not in seen:
                seen.add(key)
                output.append(cleaned[:160])
            if len(output) >= limit:
                break
        return output

    title_label = clean_text(str(task.get("label") or "Agent Research Brief"))
    return {
        "title": f"{title_label}: {goal}"[:180],
        "brief_type": "browser_agent_research",
        "platform": "strategy",
        "goal": goal,
        "executive_summary": result[:2500],
        "recommended_angle": _first_non_empty_line(result) or goal,
        "keywords": unique(keywords, 20),
        "pricing_signals": unique(prices, 12),
        "competitor_or_entity_signals": unique(entities, 16),
        "feature_signals": unique(features, 16),
        "evidence": evidence_cards,
        "sources": sources[:30],
        "confidence": progress.get("progress_score"),
        "structured_density": progress.get("structured_density"),
        "next_actions": [
            "Review this brief and convert it into channel-specific assets.",
            "Use the evidence cards to refine positioning, SEO targets, and offer messaging.",
            "Generate LinkedIn, email, ad, or SEO content from this research brief.",
        ],
    }


def _first_non_empty_line(text: str) -> str:
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        cleaned = clean_text(line).strip(" -#")
        if len(cleaned) > 8:
            return cleaned[:220]
    return ""


def _campaign_to_dict(campaign: MarketingCampaign) -> dict:
    return {
        "id": str(campaign.id),
        "business_id": str(campaign.business_id),
        "product_id": str(campaign.product_id) if campaign.product_id else None,
        "project_id": str(campaign.project_id) if campaign.project_id else None,
        "campaign_type": campaign.campaign_type,
        "name": campaign.name,
        "status": campaign.status,
        "content": campaign.content,
        "targeting": campaign.targeting,
        "metrics": campaign.metrics,
        "lifecycle_status": campaign.lifecycle_status,
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
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
    business_id = payload.get("business_id")
    instruction = payload.get("instruction", "")

    if not business_id or not instruction:
        return {"error": "business_id and instruction are required"}

    try:
        from app.services.ai_studio_service import AIStudioService

        result = await AIStudioService(db).run_prompt(
            business_id,
            instruction,
            current_user,
            payload.get("brand_context") or {},
        )
    except Exception as exc:
        return {"error": str(exc)}
    return result.get("action") or result


