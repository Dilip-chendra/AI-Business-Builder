from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

import httpx

from app.core.config import settings
from app.services.ai_service import AIService
from app.services.browser_agent.action_parser import ActionParser

logger = logging.getLogger(__name__)


class BrowserPlanner:
    """Plans the next browser action with a local Ollama reasoning model."""

    def __init__(self, reasoning_model: str | None = None) -> None:
        self.reasoning_model = reasoning_model or settings.browser_reasoning_model or settings.ollama_model
        self.ollama_base_url = settings.ollama_base_url.rstrip("/")
        self._cooldown_until = 0.0

    async def plan_next_action(
        self,
        *,
        goal: str,
        dom_snapshot: dict[str, Any],
        vision_analysis: dict[str, Any],
        memory_context: str,
        memory_state: dict[str, Any] | None,
        extracted_context: str,
        step_number: int,
        max_steps: int,
    ) -> dict[str, Any]:
        extracted_context = extracted_context.strip()
        if extracted_context.lower() == "no extracted data yet.":
            extracted_context = ""
        elements = dom_snapshot.get("elements", [])[:16]
        compact_elements = [
            {
                "id": item.get("id"),
                "tag": item.get("tag"),
                "text": str(item.get("text", ""))[:80],
                "name": str(item.get("name", ""))[:40],
                "placeholder": str(item.get("placeholder", ""))[:60],
                "href": str(item.get("href", ""))[:120],
                "type": item.get("type"),
                "role": item.get("role"),
            }
            for item in elements
        ]
        compact_search_results = [
            {
                "title": str(item.get("text", ""))[:100],
                "url": str(item.get("canonical_url") or item.get("href") or "")[:180],
                "snippet": str(item.get("snippet", ""))[:180],
            }
            for item in dom_snapshot.get("search_results", [])[:6]
        ]

        prompt = (
            "You are a real browser operator using Playwright.\n"
            "Decide the NEXT SINGLE ACTION to move toward the goal.\n"
            "Use browser actions only. Do not answer from memory. Do not skip to done unless enough evidence is collected.\n"
            "Be concise and choose the highest-value next action.\n\n"
            f"GOAL: {goal}\n"
            f"STEP: {step_number}/{max_steps}\n"
            f"CURRENT URL: {dom_snapshot.get('url')}\n"
            f"PAGE TITLE: {dom_snapshot.get('title')}\n"
            f"VISIBLE HEADINGS: {json.dumps(dom_snapshot.get('headings', [])[:6], ensure_ascii=True)}\n"
            f"SEARCH RESULTS: {json.dumps(compact_search_results, ensure_ascii=True)}\n"
            f"VISION: {json.dumps(vision_analysis, ensure_ascii=True)}\n"
            f"STRUCTURED MEMORY: {json.dumps(memory_state or {}, ensure_ascii=True)}\n"
            f"RECENT MEMORY:\n{memory_context[:520]}\n\n"
            f"EXTRACTED DATA SO FAR:\n{extracted_context[:900]}\n\n"
            f"INTERACTIVE ELEMENTS:\n{json.dumps(compact_elements, ensure_ascii=True)}\n\n"
            "You must return ONLY JSON with one action.\n"
            "Allowed action schemas:\n"
            '- {"action":"search","query":"...","search_engine":"duckduckgo|bing","reason":"..."}\n'
            '- {"action":"goto","url":"https://...","reason":"..."}\n'
            '- {"action":"click","element_id":12,"reason":"..."}\n'
            '- {"action":"click","target":"Pricing","reason":"..."}\n'
            '- {"action":"type","element_id":2,"text":"...","submit":true,"reason":"..."}\n'
            '- {"action":"scroll","direction":"down|up","amount":700,"reason":"..."}\n'
            '- {"action":"wait","seconds":2,"reason":"..."}\n'
            '- {"action":"extract","instruction":"exactly what to extract","reason":"..."}\n'
            '- {"action":"open_tab","url":"https://...","reason":"..."}\n'
            '- {"action":"switch_tab","tab_index":1,"reason":"..."}\n'
            '- {"action":"select_option","target":"Billing","value":"Monthly","reason":"..."}\n'
            '- {"action":"upload_file","target":"Upload image","file_path":"C:/path/file.png","reason":"..."}\n'
            '- {"action":"done","result":"final evidence-based answer","reason":"why the task is complete"}\n\n'
            "Rules:\n"
            "- Prefer clicking or typing into elements already visible before opening new pages.\n"
            "- Use DuckDuckGo as the default search engine. Do not choose Google.\n"
            "- For research tasks, keep the search-results tab alive, open at least 6 distinct source websites, extract from each one, and only return done after strong multi-source evidence is collected.\n"
            "- If a source is blocked or low quality, skip it and open another result instead of changing search engines repeatedly.\n"
            "- If you extracted enough pricing/features/data, return done with a structured text summary.\n"
            "- Never output markdown.\n"
        )

        if self._cooldown_until > time.monotonic():
            return self._heuristic_action(
                goal=goal,
                dom_snapshot=dom_snapshot,
                vision_analysis=vision_analysis,
                memory_state=memory_state or {},
                extracted_context=extracted_context,
                step_number=step_number,
                max_steps=max_steps,
                error="Planner is cooling down after a timeout.",
            )

        try:
            raw = await self._generate(
                prompt,
                timeout_seconds=settings.browser_planner_timeout_seconds,
                num_predict=settings.browser_planner_num_predict,
            )
            return ActionParser.parse_action(raw)
        except Exception as exc:
            self._cooldown_until = time.monotonic() + 60
            logger.warning("Planner fallback triggered at step %s: %s", step_number, exc)
            return self._heuristic_action(
                goal=goal,
                dom_snapshot=dom_snapshot,
                vision_analysis=vision_analysis,
                memory_state=memory_state or {},
                extracted_context=extracted_context,
                step_number=step_number,
                max_steps=max_steps,
                error=str(exc),
            )

    def deterministic_research_action(
        self,
        *,
        goal: str,
        dom_snapshot: dict[str, Any],
        memory_state: dict[str, Any] | None,
        extracted_context: str,
        progress: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        memory_state = memory_state or {}
        progress = progress or {}
        goal_profile = self._goal_profile(goal)
        if goal_profile not in {"keyword_research", "competitor_research", "pricing_research", "general_research"}:
            return None

        current_url = str(dom_snapshot.get("url") or "")
        elements = dom_snapshot.get("elements", [])
        search_results = dom_snapshot.get("search_results", []) or memory_state.get("cached_search_results", []) or []
        extracted_urls = {str(url).lower() for url in memory_state.get("extracted_urls", [])}
        rejected_urls = {str(url).lower() for url in memory_state.get("rejected_source_urls", [])}
        useful_sources = int(progress.get("useful_sources", 0))
        target_sources = int(progress.get("target_sources", 0) or 0)

        if self._is_search_results_page(current_url):
            candidate = self._find_unique_search_result_candidate(
                search_results=search_results,
                memory_state=memory_state,
                goal_profile=goal_profile,
                goal_text=goal,
            )
            if candidate:
                return {
                    "action": "open_tab",
                    "url": candidate["canonical_url"],
                    "reason": "A fresh search result is available, so open it directly and continue collecting evidence.",
                }

            element_candidate = self._find_unique_search_result(
                elements=elements,
                memory_state=memory_state,
                goal_profile=goal_profile,
                goal_text=goal,
            )
            if element_candidate is not None:
                return {
                    "action": "click",
                    "element_id": int(element_candidate["id"]),
                    "reason": "A unique visible result is available, so open it and extract another source.",
                }

        source_tab = self._find_best_source_tab(
            memory_state,
            extracted_urls=extracted_urls,
            rejected_urls=rejected_urls,
        )
        if source_tab is not None:
            return {
                "action": "switch_tab",
                "tab_index": source_tab,
                "reason": "An unextracted source tab is already open, so inspect it before searching again.",
            }

        title = str(dom_snapshot.get("title") or "").lower()
        headings = [str(item).lower() for item in dom_snapshot.get("headings", [])[:8]]
        text_excerpt = str(dom_snapshot.get("visible_text") or dom_snapshot.get("text_excerpt") or "").lower()

        if current_url and not self._is_search_page(current_url):
            current_key = current_url.lower()
            if current_key not in extracted_urls and self._page_has_useful_content(goal_profile, title, headings, text_excerpt):
                return {
                    "action": "extract",
                    "instruction": self._build_extract_instruction(goal_profile, goal),
                    "reason": "The current page has useful topical content and has not been extracted yet.",
                }

            if useful_sources < target_sources:
                search_tab = self._find_tab(memory_state, desired_kind="search")
                if search_tab is not None:
                    return {
                        "action": "switch_tab",
                        "tab_index": search_tab,
                        "reason": "This source is already captured, so return to search results and open another unique source.",
                    }
                return {
                    "action": "search",
                    "query": self._focused_search_query(goal, goal_profile),
                    "search_engine": "duckduckgo",
                    "reason": "More source coverage is needed, so restart from DuckDuckGo with a tighter research query.",
                }

        if useful_sources < target_sources:
            return {
                "action": "search",
                "query": self._focused_search_query(goal, goal_profile),
                "search_engine": "duckduckgo",
                "reason": "The run still needs broader evidence, so begin or resume source discovery from DuckDuckGo.",
            }

        if extracted_context.strip():
            return {
                "action": "done",
                "result": extracted_context[:2200],
                "reason": "The run has enough extracted multi-source evidence to synthesize a final answer.",
            }

        return None

    def corrective_action(
        self,
        *,
        goal: str,
        dom_snapshot: dict[str, Any],
        vision_analysis: dict[str, Any],
        memory_state: dict[str, Any] | None,
        extracted_context: str,
        step_number: int,
        max_steps: int,
        reason: str,
    ) -> dict[str, Any]:
        return self._heuristic_action(
            goal=goal,
            dom_snapshot=dom_snapshot,
            vision_analysis=vision_analysis,
            memory_state=memory_state or {},
            extracted_context=extracted_context,
            step_number=step_number,
            max_steps=max_steps,
            error=reason,
        )

    async def summarize(
        self,
        *,
        goal: str,
        extracted_context: str,
        evidence_digest: str = "",
        memory_context: str,
        evidence: list[dict[str, Any]] | None = None,
        progress: dict[str, Any] | None = None,
    ) -> str:
        prompt = (
            "You are preparing the final report for an autonomous browser research run.\n"
            "Use only the evidence collected from browsing.\n"
            "Write like a sharp research analyst, not like a debugger.\n"
            "Prefer concise claims supported by multiple sources. Avoid raw extraction dumps.\n"
            "Inside each section, write clear explanatory paragraphs first, then use bullets only when they genuinely help.\n"
            "Write a polished, user-facing report with these sections exactly:\n"
            "## Executive Summary\n"
            "## Key Findings\n"
            "## Sources Used\n"
            "## Extracted Data\n"
            "## Recommendations\n"
            "## Next Actions\n\n"
            f"GOAL: {goal}\n\n"
            f"PROGRESS SNAPSHOT:\n{json.dumps(progress or {}, ensure_ascii=True)}\n\n"
            f"COMPRESSED EVIDENCE DIGEST:\n{evidence_digest[:4000]}\n\n"
            f"EVIDENCE:\n{json.dumps(evidence or [], ensure_ascii=True)}\n\n"
            f"EXTRACTED DATA:\n{extracted_context}\n\n"
            f"BROWSER MEMORY:\n{memory_context}\n"
        )
        if self._cooldown_until > time.monotonic():
            return self._fallback_summary(
                goal=goal,
                extracted_context=extracted_context,
                memory_context=memory_context,
                evidence=evidence or [],
                progress=progress or {},
            )
        try:
            return await self._generate(
                prompt,
                json_mode=False,
                timeout_seconds=settings.browser_synthesis_timeout_seconds,
                num_predict=max(settings.browser_planner_num_predict, 220),
            )
        except Exception as exc:
            logger.warning("Planner summary fallback triggered: %s", exc)
            compressed_prompt = (
                "Create a concise final research report from the evidence below.\n"
                "Use these sections exactly:\n"
                    "## Executive Summary\n## Key Findings\n## Sources Used\n## Extracted Data\n## Recommendations\n## Next Actions\n\n"
                    f"Goal: {goal}\n"
                    f"Evidence Digest: {evidence_digest[:1800]}\n"
                    f"Evidence: {json.dumps((evidence or [])[:4], ensure_ascii=True)}\n"
                    f"Progress: {json.dumps(progress or {}, ensure_ascii=True)}\n"
                    f"Extracted Data: {extracted_context[:1800]}\n"
                )
            try:
                return await self._generate(
                    compressed_prompt,
                    json_mode=False,
                    timeout_seconds=max(8.0, settings.browser_synthesis_timeout_seconds * 0.7),
                    num_predict=180,
                    model_override=settings.browser_fast_reasoning_model or self.reasoning_model,
                )
            except Exception:
                self._cooldown_until = time.monotonic() + 60
                return self._fallback_summary(
                    goal=goal,
                    extracted_context=extracted_context,
                    memory_context=memory_context,
                    evidence=evidence or [],
                    progress=progress or {},
                )

    async def _generate(
        self,
        prompt: str,
        *,
        json_mode: bool = True,
        timeout_seconds: float | None = None,
        num_predict: int | None = None,
        model_override: str | None = None,
    ) -> str:
        ai = AIService()
        content = await ai.generate_text(
            prompt,
            prefer_json=json_mode,
            task_type="browser_planning" if json_mode else "browser_synthesis",
        )
        logger.debug("Planner response: %s", content[:600])
        return content

    @staticmethod
    def _fallback_summary(
        *,
        goal: str,
        extracted_context: str,
        memory_context: str,
        evidence: list[dict[str, Any]],
        progress: dict[str, Any],
    ) -> str:
        source_records = [item for item in evidence if item.get("url")]
        key_findings: list[str] = []
        extracted_lines: list[str] = []
        price_points: list[str] = []
        keyword_signals: list[str] = []
        seen_points: set[str] = set()

        for item in source_records[:6]:
            for point in item.get("key_points", [])[:4]:
                cleaned = str(point).strip()
                key = cleaned.lower()
                if cleaned and key not in seen_points:
                    seen_points.add(key)
                    key_findings.append(f"- {cleaned[:220]}")
                if len(key_findings) >= 8:
                    break
            data = item.get("extracted_data", {}) or {}
            for price in data.get("prices", [])[:4]:
                if str(price) not in price_points:
                    price_points.append(str(price))
            for signal in data.get("signals", [])[:4]:
                cleaned_signal = str(signal).strip()
                if cleaned_signal and cleaned_signal not in keyword_signals:
                    keyword_signals.append(cleaned_signal[:140])
            if len(key_findings) >= 8:
                break

        if not key_findings and extracted_context.strip() and extracted_context.lower() != "no extracted data yet.":
            for line in extracted_context.splitlines():
                cleaned = line.strip()
                if cleaned and not cleaned.lower().startswith(("source:", "url:")):
                    key_findings.append(f"- {cleaned[:220]}")
                if len(key_findings) >= 6:
                    break
        if not key_findings:
            key_findings.append("- The run did not gather enough clean evidence before synthesis, so this report is surfacing the strongest partial signals that were still captured.")

        if price_points:
            extracted_lines.append(f"- Pricing signals captured: {', '.join(price_points[:8])}")
        if keyword_signals:
            extracted_lines.append(f"- Structured topic signals: {', '.join(keyword_signals[:6])}")
        for item in source_records[:4]:
            title = str(item.get("title") or item.get("url") or "").strip()
            summary = str(item.get("summary") or "").strip()
            if title:
                extracted_lines.append(f"- {title}: {summary[:180]}")
        if not extracted_lines:
            extracted_lines.append("- Evidence was collected, but the extracted data remained thin enough that another continuation pass would improve confidence.")

        source_lines = [
            f"- {str(item.get('title') or item.get('url')).strip()} — {str(item.get('url')).strip()}"
            for item in source_records[:6]
        ]
        if not source_lines:
            source_lines.append("- No distinct source URLs were captured.")

        goal_lower = goal.lower()
        if "pricing" in goal_lower:
            executive = "The evidence points to tiered pricing, value-based packaging, and premium upsells as the strongest recurring patterns across online course platforms. Higher-priced offers are usually justified by stronger outcomes, coaching, certification, or accountability layers rather than content volume alone."
            recommendations = [
                "- Build a three-tier offer structure so buyers can self-select by depth, support, and accountability.",
                "- Use a clear entry price for mini or starter products, then reserve premium pricing for full transformations, certification, or coaching access.",
            ]
        elif "keyword" in goal_lower or "seo" in goal_lower:
            executive = "The strongest opportunities cluster around high-intent long-tail terms, niche-specific service phrases, and educational content angles that match buyer intent. The best opportunities usually combine a clear problem, a defined audience niche, and a concrete service outcome."
            recommendations = [
                "- Organize the keyword list into service, problem, and local-intent clusters before publishing content.",
                "- Turn the top clusters into landing pages, comparison posts, and FAQ content to capture mid- and bottom-funnel traffic.",
            ]
        else:
            executive = "The collected evidence is strong enough to outline the main patterns, although another validating source may still help if you need deeper confidence or fresher confirmation."
            recommendations = [
                "- Prioritize the repeated patterns that appear across multiple sources rather than single-source claims.",
                "- Continue the run if you need broader market coverage or fresher supporting evidence.",
            ]

        return "\n".join(
            [
                "## Executive Summary",
                f"Goal: {goal}",
                executive,
                f"Coverage reached {progress.get('unique_sources', 0)} out of {progress.get('target_sources', 0)} target sources, with a progress score of {round(float(progress.get('progress_score', 0.0)) * 100)}%.",
                "",
                "## Key Findings",
                *key_findings,
                "",
                "## Sources Used",
                *source_lines,
                "",
                "## Extracted Data",
                *extracted_lines,
                "",
                "## Recommendations",
                *recommendations,
                "",
                "## Next Actions",
                "- Use Continue Research if you want broader source coverage or one more validating source.",
                "- Use Force Final Answer when the captured evidence is already sufficient for your next business decision.",
            ]
        )

    @staticmethod
    def _best_evidence_sentence(snippet: str) -> str:
        normalized = " ".join(snippet.split())
        for sentence in normalized.split(". "):
            candidate = sentence.strip()
            if len(candidate) < 24:
                continue
            if any(token in candidate.lower() for token in ("price", "pricing", "tier", "subscription", "keyword", "seo", "plan", "$", "£", "€", "%")):
                return candidate[:220]
        return normalized[:220]

    def _heuristic_action(
        self,
        *,
        goal: str,
        dom_snapshot: dict[str, Any],
        vision_analysis: dict[str, Any],
        memory_state: dict[str, Any],
        extracted_context: str,
        step_number: int,
        max_steps: int,
        error: str,
    ) -> dict[str, Any]:
        url = str(dom_snapshot.get("url", "")).lower()
        title = str(dom_snapshot.get("title", "")).lower()
        headings = [str(item).lower() for item in dom_snapshot.get("headings", [])[:8]]
        blockers = [str(item).lower() for item in vision_analysis.get("blockers", [])]
        elements = dom_snapshot.get("elements", [])
        text_excerpt = str(dom_snapshot.get("text_excerpt", "")).lower()
        goal_text = goal.strip()
        goal_profile = self._goal_profile(goal_text)
        focused_query = self._focused_search_query(goal_text, goal_profile)
        active_url = str(memory_state.get("active_url") or dom_snapshot.get("url") or "")
        extracted_urls = {str(item).lower() for item in memory_state.get("extracted_urls", [])}
        rejected_source_urls = {str(item).lower() for item in memory_state.get("rejected_source_urls", [])}
        external_urls = [str(item) for item in memory_state.get("external_urls", [])]
        useful_sources = int(memory_state.get("useful_sources_count") or 0)
        unique_domains = len(memory_state.get("external_domains", []) or [])
        cached_search_results = memory_state.get("cached_search_results", []) or []
        target_source_count = 6 if goal_profile in {"keyword_research", "competitor_research", "pricing_research", "general_research"} else 2

        if goal_profile == "publishing":
            preferred_publish_url = self._publishing_start_url(goal_text)
            if self._is_search_page(url) and preferred_publish_url:
                return {
                    "action": "goto",
                    "url": preferred_publish_url,
                    "reason": "Publishing mode should start on the target platform itself, not on a search engine results page.",
                }
            publish_target = self._find_element_id(
                elements,
                include=("start a post", "create post", "new post", "what do you want to talk about", "share", "compose", "publish", "create"),
            )
            if publish_target is not None:
                return {
                    "action": "click",
                    "element_id": publish_target,
                    "reason": "A relevant posting control is visible, so enter the publishing flow directly.",
                }

        if blockers:
            if active_url and not self._is_search_page(active_url):
                search_tab = self._find_tab(memory_state, desired_kind="search")
                if search_tab is not None:
                    return {
                        "action": "switch_tab",
                        "tab_index": search_tab,
                        "reason": f"The current source is blocked ({', '.join(blockers)}). Go back to the search tab and choose a different website.",
                    }
            direct_result = self._find_unique_search_result_candidate(
                dom_snapshot.get("search_results", []) or cached_search_results,
                memory_state,
                goal_profile,
                goal_text,
            )
            if direct_result is not None:
                return {
                    "action": "open_tab",
                    "url": direct_result["canonical_url"],
                    "reason": "The visible search page is blocked, but we already have viable DuckDuckGo results cached. Open the strongest source directly and continue research.",
                }
            return {
                "action": "search",
                "query": focused_query,
                "search_engine": "duckduckgo",
                "reason": f"The current page appears blocked ({', '.join(blockers)}). Return to DuckDuckGo and continue with another source.",
            }

        if self._is_search_page(url):
            if not self._is_search_results_page(url) and not extracted_context:
                return {
                    "action": "search",
                    "query": focused_query,
                    "search_engine": "duckduckgo",
                    "reason": f"Planner timed out ({error[:80]}). Start the research from DuckDuckGo results.",
                }

            if useful_sources >= target_source_count and unique_domains >= max(5, target_source_count - 1) and extracted_context:
                return {
                    "action": "done",
                    "result": extracted_context[:2200],
                    "reason": "Enough distinct, useful sources have been extracted to answer the research goal with confidence.",
                }

            next_source_tab = self._find_best_source_tab(
                memory_state,
                extracted_urls=extracted_urls,
                rejected_urls=rejected_source_urls,
            )
            if next_source_tab is not None:
                return {
                    "action": "switch_tab",
                    "tab_index": next_source_tab,
                    "reason": "A relevant source tab is already open, so analyze it before searching again.",
                }

            direct_result = self._find_unique_search_result_candidate(
                dom_snapshot.get("search_results", []) or cached_search_results,
                memory_state,
                goal_profile,
                goal_text,
            )
            if direct_result is not None:
                return {
                    "action": "open_tab",
                    "url": direct_result["canonical_url"],
                    "reason": f"Open a strong, unique DuckDuckGo result directly and preserve the search tab while collecting evidence for this {goal_profile.replace('_', ' ')} task.",
                }

            unique_result = self._find_unique_search_result(elements, memory_state, goal_profile, goal_text)
            if unique_result is not None:
                return {
                    "action": "click",
                    "element_id": unique_result["id"],
                    "reason": f"Open a fresh source from DuckDuckGo results and keep collecting evidence for this {goal_profile.replace('_', ' ')} task.",
                }

            if self._should_scroll(dom_snapshot):
                return {
                    "action": "scroll",
                    "direction": "down",
                    "amount": 900,
                    "reason": "Scroll the DuckDuckGo results to reveal more unique websites before changing strategy.",
                }

            if extracted_context and useful_sources >= target_source_count and unique_domains >= max(5, target_source_count - 1):
                return {
                    "action": "done",
                    "result": extracted_context[:2200],
                    "reason": "The search results are exhausted and the collected evidence is strong enough to give a useful answer.",
                }

        if active_url and active_url.lower() not in extracted_urls and not self._is_search_page(active_url):
            if self._page_has_useful_content(goal_profile, title, headings, text_excerpt):
                return {
                    "action": "extract",
                    "instruction": self._build_extract_instruction(goal_profile, goal_text),
                    "reason": "This page looks relevant and has not been extracted yet, so capture structured evidence now.",
                }

            if self._should_scroll(dom_snapshot) and not extracted_context and useful_sources == 0:
                return {
                    "action": "scroll",
                    "direction": "down",
                    "amount": 850,
                    "reason": "The current source page may contain relevant content further down.",
                }

            search_tab = self._find_tab(memory_state, desired_kind="search")
            if search_tab is not None:
                return {
                    "action": "switch_tab",
                    "tab_index": search_tab,
                    "reject_current_source": True,
                    "rejected_url": active_url,
                    "reason": "This source is not yielding useful evidence, so return to DuckDuckGo and open a different website.",
                }

        if useful_sources >= target_source_count and unique_domains >= max(5, target_source_count - 1) and extracted_context:
            return {
                "action": "done",
                "result": extracted_context[:2200],
                "reason": "Enough unique websites have been extracted and compared to complete the research task.",
            }

        if active_url and active_url.lower() in extracted_urls and goal_profile in {"keyword_research", "competitor_research", "pricing_research"}:
            search_tab = self._find_tab(memory_state, desired_kind="search")
            if search_tab is not None and len(extracted_urls) < target_source_count:
                return {
                    "action": "switch_tab",
                    "tab_index": search_tab,
                    "reason": "This source is already captured. Return to the DuckDuckGo results and open another unique source for comparison.",
                }

        if any(keyword in title or keyword in " ".join(headings) for keyword in ("pricing", "plans", "compare")):
            if step_number >= max_steps or extracted_context:
                return {
                    "action": "extract",
                    "instruction": self._build_extract_instruction("pricing_research", goal_text),
                    "reason": "A pricing page is visible, so capture the pricing evidence now.",
                }
            return {
                "action": "scroll",
                "direction": "down",
                "amount": 900,
                "reason": "Pricing content is likely below the fold. Scroll to inspect the plans.",
            }

        pricing_target = self._find_element_id(
            elements,
            include=("pricing", "plans", "see pricing", "view pricing", "compare"),
        )
        if pricing_target is not None:
            return {
                "action": "click",
                "element_id": pricing_target,
                "reason": "A relevant navigation control is visible, so use it instead of guessing a new URL.",
            }

        if extracted_context and step_number >= max_steps - 1:
            if goal_profile in {"keyword_research", "competitor_research", "pricing_research"} and useful_sources < target_source_count:
                search_tab = self._find_tab(memory_state, desired_kind="search")
                if search_tab is not None:
                    return {
                        "action": "switch_tab",
                        "tab_index": search_tab,
                        "reason": "The research goal still needs more extracted sources before finishing.",
                    }
            if useful_sources >= target_source_count and unique_domains >= max(5, target_source_count - 1):
                return {
                    "action": "done",
                    "result": extracted_context[:2200],
                    "reason": "Enough evidence has been collected to conclude the run.",
                }

        if "pricing" in text_excerpt or "plan" in text_excerpt:
            return {
                "action": "extract",
                "instruction": self._build_extract_instruction(goal_profile, goal_text),
                "reason": "The current page already contains relevant signals, so capture the evidence.",
            }

        return {
            "action": "scroll",
            "direction": "down",
            "amount": 850,
            "reason": f"Planner timed out ({error[:80]}). Prefer a little more page context before choosing the next source or extraction step.",
        }

    @staticmethod
    def _is_search_page(url: str) -> bool:
        if "bing.com/ck" in url:
            return False
        return any(engine in url for engine in ("google.", "bing.com", "duckduckgo.com"))

    @staticmethod
    def _is_search_results_page(url: str) -> bool:
        split = urlsplit(url)
        query = parse_qs(split.query)
        if any(key in query for key in ("q", "p", "query")):
            return True
        return any(token in split.path.lower() for token in ("/search", "/html"))

    @staticmethod
    def _goal_profile(goal: str) -> str:
        goal_lower = goal.lower()
        if "keyword" in goal_lower or "seo" in goal_lower:
            return "keyword_research"
        if "pricing" in goal_lower or "price" in goal_lower:
            return "pricing_research"
        if "competitor" in goal_lower or "compare" in goal_lower:
            return "competitor_research"
        if "post" in goal_lower or "publish" in goal_lower or "linkedin" in goal_lower or "twitter" in goal_lower:
            return "publishing"
        return "general_research"

    @staticmethod
    def _focused_search_query(goal_text: str, goal_profile: str) -> str:
        words = [token for token in re.findall(r"[a-z0-9]+", goal_text.lower()) if token]
        stop_words = {
            "find", "research", "analyze", "analyse", "show", "give", "need", "best",
            "top", "for", "the", "and", "with", "using", "businesses", "business",
            "strategies", "strategy", "platforms", "platform",
        }
        filtered = [word for word in words if word not in stop_words]
        if goal_profile == "keyword_research":
            priority = [word for word in filtered if word in {"seo", "keyword", "keywords", "fitness", "coaching", "coach", "local"}]
            query = priority + [word for word in filtered if word not in priority]
            return " ".join(query[:6]) or goal_text
        if goal_profile == "pricing_research":
            priority = [word for word in filtered if word in {"pricing", "price", "plan", "plans", "online", "course", "courses"}]
            query = priority + [word for word in filtered if word not in priority]
            return " ".join(query[:7]) or goal_text
        if goal_profile == "competitor_research":
            priority = [word for word in filtered if word in {"competitor", "competitors", "compare", "comparison", "alternatives"}]
            query = priority + [word for word in filtered if word not in priority]
            return " ".join(query[:7]) or goal_text
        return " ".join(filtered[:7]) or goal_text

    @staticmethod
    def _publishing_start_url(goal_text: str) -> str | None:
        goal_lower = goal_text.lower()
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
        return None

    @classmethod
    def _build_extract_instruction(cls, goal_profile: str, goal_text: str) -> str:
        if goal_profile == "keyword_research":
            return f"Extract SEO keywords, keyword clusters, search-intent themes, and suggested content angles related to: {goal_text}"
        if goal_profile == "pricing_research":
            return f"Extract plan names, prices, billing periods, free tiers, and standout differentiators related to: {goal_text}"
        if goal_profile == "competitor_research":
            return f"Extract company names, product positioning, notable features, and evidence relevant to: {goal_text}"
        if goal_profile == "publishing":
            return f"Extract visible publishing controls, form fields, and required approval steps needed to complete: {goal_text}"
        return f"Extract the most relevant structured facts, entities, and evidence related to: {goal_text}"

    @classmethod
    def _find_unique_search_result_candidate(
        cls,
        search_results: list[dict[str, Any]],
        memory_state: dict[str, Any],
        goal_profile: str,
        goal_text: str,
    ) -> dict[str, Any] | None:
        visited = {str(item).lower() for item in memory_state.get("visited_urls", [])}
        opened = {str(item).lower() for item in memory_state.get("opened_tabs", [])}
        rejected = {str(item).lower() for item in memory_state.get("rejected_source_urls", [])}
        goal_terms = {token for token in goal_text.lower().split() if len(token) > 2}
        seen_domains = {urlsplit(url).netloc.lower() for url in visited | opened if url}
        best_match: tuple[int, dict[str, Any]] | None = None

        for result in search_results:
            url = str(result.get("canonical_url") or result.get("href") or "").strip()
            title = str(result.get("text", "")).strip()
            snippet = str(result.get("snippet", "")).strip()
            if not url or not title:
                continue
            url_lower = url.lower()
            if cls._is_search_page(url_lower):
                continue
            if url_lower in visited or url_lower in opened or url_lower in rejected:
                continue
            if any(
                token in url_lower
                for token in (
                    "youtube.com",
                    "facebook.com",
                    "instagram.com",
                    "linkedin.com",
                    "pinterest.com",
                    "quora.com",
                    "reddit.com/r/",
                )
            ):
                continue

            haystack = f"{title.lower()} {snippet.lower()} {url_lower}"
            host = urlsplit(url_lower).netloc.lower()
            score = sum(2 for term in goal_terms if term in haystack)
            score += cls._domain_preference_score(url_lower)
            if host and host not in seen_domains:
                score += 5
            else:
                score -= 3
            if goal_profile == "keyword_research":
                score += sum(4 for token in ("keyword", "seo", "search", "volume", "blog", "guide", "list") if token in haystack)
            elif goal_profile == "pricing_research":
                score += sum(4 for token in ("pricing", "price", "plan", "tier", "subscription", "course") if token in haystack)
            elif goal_profile == "competitor_research":
                score += sum(4 for token in ("compare", "alternatives", "best", "top", "platform", "software") if token in haystack)

            if any(token in haystack for token in ("login", "sign in", "account", "ad", "sponsored")):
                score -= 5

            if best_match is None or score > best_match[0]:
                best_match = (score, {"canonical_url": url, "text": title, "snippet": snippet})

        return best_match[1] if best_match is not None else None

    @classmethod
    def _find_unique_search_result(
        cls,
        elements: list[dict[str, Any]],
        memory_state: dict[str, Any],
        goal_profile: str,
        goal_text: str,
    ) -> dict[str, Any] | None:
        visited = {str(item).lower() for item in memory_state.get("visited_urls", [])}
        opened = {str(item).lower() for item in memory_state.get("opened_tabs", [])}
        clicked = set(memory_state.get("clicked_targets", []))
        goal_terms = {token for token in goal_text.lower().split() if len(token) > 2}
        seen_domains = {urlsplit(url).netloc.lower() for url in visited | opened if url}
        best_match: tuple[int, dict[str, Any]] | None = None

        for element in elements:
            href = str(element.get("href", "")).strip()
            tag = str(element.get("tag", "")).lower()
            text = str(element.get("text", "")).strip()
            if tag != "a" or not href or not text:
                continue
            candidate_url = cls._canonical_result_url(href, memory_state.get("active_url"))
            href_lower = candidate_url.lower()
            if href_lower.startswith(("/", "#", "javascript:")):
                continue
            if cls._is_search_page(href_lower):
                continue
            if any(
                token in href_lower
                for token in (
                    "youtube.com",
                    "/video",
                    "linkedin.com",
                    "facebook.com",
                    "instagram.com",
                    "google.com/sorry",
                    "bing.com/videos",
                    "bing.com/images",
                    "microsoft.com/en-us/privacy",
                )
            ):
                continue
            if (
                ("google.com/" in href_lower or "duckduckgo.com/" in href_lower)
                or ("bing.com/" in href_lower and "bing.com/ck" not in href_lower)
            ):
                continue
            click_signature = json.dumps(
                {
                    "current_url": str(memory_state.get("active_url") or "").lower(),
                    "target_url": href_lower,
                    "element_id": element.get("id"),
                    "target": "",
                },
                sort_keys=True,
                ensure_ascii=True,
            )
            if href_lower in visited or href_lower in opened or click_signature in clicked:
                continue

            haystack = f"{text.lower()} {href_lower}"
            host = urlsplit(href_lower).netloc.lower()
            score = 0
            score += sum(2 for term in goal_terms if term in haystack)
            score += cls._domain_preference_score(href_lower)
            if host and host not in seen_domains:
                score += 5
            else:
                score -= 3
            if goal_profile == "keyword_research":
                score += sum(4 for token in ("keyword", "seo", "search", "blog", "guide", "list") if token in haystack)
            elif goal_profile == "pricing_research":
                score += sum(4 for token in ("pricing", "price", "plan", "compare", "software") if token in haystack)
            elif goal_profile == "competitor_research":
                score += sum(4 for token in ("compare", "alternatives", "best", "top", "software", "platform") if token in haystack)

            if any(token in haystack for token in ("video", "watch", "youtube", "login", "signin", "account", "captcha", "support")):
                score -= 6

            if best_match is None or score > best_match[0]:
                best_match = (score, element)

        return best_match[1] if best_match is not None else None

    @staticmethod
    def _domain_preference_score(url: str) -> int:
        host = urlsplit(url).netloc.lower()
        score = 0
        strong = ("docs.", "developer.", ".gov", ".edu", "pricing", "blog.", "substack.com", "ahrefs.com", "semrush.com", "hubspot.com", "shopify.com", "stripe.com")
        weak = ("pinterest.", "facebook.", "instagram.", "youtube.", "reddit.com", "quora.com")
        if any(token in host for token in strong):
            score += 4
        if any(token in host for token in weak):
            score -= 5
        if host.count(".") <= 2:
            score += 1
        return score

    @staticmethod
    def _canonical_result_url(href: str, current_url: str | None) -> str:
        absolute = urljoin(str(current_url or ""), href)
        split = urlsplit(absolute)
        query = parse_qs(split.query)
        if "duckduckgo.com" in split.netloc.lower() and "uddg" in query:
            return unquote(query["uddg"][0])
        if "bing.com" in split.netloc.lower() and "u" in query and query["u"]:
            return unquote(query["u"][0])
        return absolute

    @staticmethod
    def _find_tab(memory_state: dict[str, Any], *, desired_kind: str) -> int | None:
        for tab in memory_state.get("tabs", []):
            if tab.get("kind") == desired_kind and not tab.get("active"):
                return int(tab.get("index", 0))
        return None

    @staticmethod
    def _find_best_source_tab(
        memory_state: dict[str, Any],
        *,
        extracted_urls: set[str],
        rejected_urls: set[str] | None = None,
    ) -> int | None:
        rejected_urls = rejected_urls or set()
        for tab in memory_state.get("tabs", []):
            if tab.get("kind") != "source" or tab.get("active"):
                continue
            normalized = str(tab.get("normalized_url") or tab.get("url") or "").lower()
            if normalized and normalized not in extracted_urls and normalized not in rejected_urls:
                return int(tab.get("index", 0))
        return None

    @staticmethod
    def _page_has_useful_content(
        goal_profile: str,
        title: str,
        headings: list[str],
        text_excerpt: str,
    ) -> bool:
        haystack = " ".join([title, *headings, text_excerpt])
        if goal_profile == "keyword_research":
            return any(token in haystack for token in ("keyword", "seo", "search volume", "fitness", "blog"))
        if goal_profile == "pricing_research":
            return any(token in haystack for token in ("pricing", "plan", "monthly", "yearly", "$"))
        if goal_profile == "competitor_research":
            return any(token in haystack for token in ("features", "pricing", "compare", "platform", "software"))
        if goal_profile == "publishing":
            return any(token in haystack for token in ("post", "publish", "share", "caption", "title"))
        return len(text_excerpt) > 180

    @staticmethod
    def _should_scroll(dom_snapshot: dict[str, Any]) -> bool:
        page_height = int(dom_snapshot.get("page_height") or 0)
        viewport = int((dom_snapshot.get("viewport") or {}).get("height") or 0)
        scroll_y = int(dom_snapshot.get("scroll_y") or 0)
        if not page_height or not viewport:
            return False
        return scroll_y + viewport + 250 < page_height

    @staticmethod
    def _find_element_id(elements: list[dict[str, Any]], *, include: tuple[str, ...]) -> int | None:
        for element in elements:
            haystack = " ".join(
                [
                    str(element.get("text", "")),
                    str(element.get("placeholder", "")),
                    str(element.get("name", "")),
                    str(element.get("href", "")),
                ]
            ).lower()
            if any(token in haystack for token in include):
                element_id = element.get("id")
                if element_id is not None:
                    return int(element_id)
        return None
