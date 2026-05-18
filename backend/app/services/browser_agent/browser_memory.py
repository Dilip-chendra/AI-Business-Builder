from __future__ import annotations

import json
import logging
import re
from collections import Counter
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

logger = logging.getLogger(__name__)

TRACKING_QUERY_PREFIXES = ("utm_", "__cf", "cf_")
TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "msclkid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "source",
    "sourceid",
    "__cf_chl_rt_tk",
    "ved",
    "ei",
    "oq",
    "aqs",
    "form",
    "sp",
    "ghc",
    "lq",
    "pq",
    "sc",
    "qs",
    "sk",
    "cvid",
}
SEARCH_HOST_HINTS = ("google.", "bing.com", "duckduckgo.com", "search.yahoo.")


class BrowserMemory:
    """Short-term browser memory for planning, loop prevention, and evidence tracking."""

    def __init__(self, max_history: int = 18) -> None:
        self.max_history = max_history
        self.history: list[dict[str, Any]] = []
        self.extractions: list[dict[str, Any]] = []
        self.evidence: list[dict[str, Any]] = []
        self.source_records: dict[str, dict[str, Any]] = {}
        self.search_queries: list[str] = []
        self.visited_urls: list[str] = []
        self.clicked_targets: list[str] = []
        self.opened_tabs: list[str] = []
        self.completed_goals: list[str] = []
        self.failed_actions: list[str] = []
        self.rejected_actions: list[dict[str, Any]] = []
        self.rejected_sources: list[dict[str, Any]] = []
        self.extracted_urls: list[str] = []
        self.search_result_cache: list[dict[str, Any]] = []
        self.active_tab_url: str | None = None
        self._visited_set: set[str] = set()
        self._clicked_set: set[str] = set()
        self._open_tab_set: set[str] = set()
        self._extracted_url_set: set[str] = set()

    def observe_state(self, *, url: str | None = None, tabs: list[dict[str, Any]] | None = None) -> None:
        normalized_url = self.normalize_url(url)
        if normalized_url:
            self.active_tab_url = normalized_url
            self._remember_url(normalized_url)

        if not tabs:
            return

        for tab in tabs:
            tab_url = self.normalize_url(tab.get("url"))
            if not tab_url:
                continue
            if tab_url not in self._open_tab_set:
                self._open_tab_set.add(tab_url)
                self.opened_tabs.append(tab_url)
            if tab.get("active"):
                self.active_tab_url = tab_url

    def add_step(
        self,
        *,
        step: int,
        action: dict[str, Any],
        thought: str,
        result: str,
        success: bool,
        url: str | None = None,
        blocked: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        metadata = metadata or {}
        final_url = self.normalize_url(url)
        if final_url:
            self._remember_url(final_url)
            self.active_tab_url = final_url

        target_url = self.normalize_url(metadata.get("target_url") or action.get("url"))
        if target_url and action.get("action") in {"goto", "click", "open_tab"}:
            self._remember_url(target_url)
            if action.get("action") == "open_tab" or metadata.get("opened_in_new_tab") or metadata.get("reused_tab"):
                self._remember_tab(target_url)

        click_signature = self._click_signature(action, metadata, final_url)
        if click_signature and success and action.get("action") == "click":
            self._remember_click(click_signature)

        if action.get("action") == "extract" and success:
            extract_url = final_url or target_url
            if extract_url and extract_url not in self._extracted_url_set:
                self._extracted_url_set.add(extract_url)
                self.extracted_urls.append(extract_url)
            raw_content = str(metadata.get("summary_excerpt") or metadata.get("content") or "").strip()
            snippet = (raw_content or result)[:2400].strip()
            source_record = self._build_source_record(
                url=extract_url or "",
                instruction=str(action.get("instruction", ""))[:180],
                snippet=snippet,
                metadata=metadata,
            )
            self.source_records[source_record["url"]] = source_record
            self.evidence = list(self.source_records.values())[-12:]
            if not source_record["useful"]:
                self.rejected_sources.append(
                    {
                        "url": source_record["url"],
                        "title": source_record["title"],
                        "reason": "Low relevance or weak extractable content.",
                        "relevance_score": source_record["relevance_score"],
                    }
                )
                self.rejected_sources = self.rejected_sources[-8:]

        if blocked and final_url and not self._is_search_url(final_url):
            rejection = {
                "url": final_url,
                "title": str(metadata.get("title") or "").strip(),
                "reason": str(metadata.get("blockers") or result or "Blocked or low-quality source.")[:240],
                "relevance_score": 0.0,
            }
            if all(item.get("url") != final_url for item in self.rejected_sources):
                self.rejected_sources.append(rejection)
                self.rejected_sources = self.rejected_sources[-8:]

        rejected_url = self.normalize_url(action.get("rejected_url"))
        if action.get("reject_current_source") and rejected_url and not self._is_search_url(rejected_url):
            rejection = {
                "url": rejected_url,
                "title": str(metadata.get("title") or "").strip(),
                "reason": str(action.get("reason") or "The page was reviewed and rejected as low value.")[:240],
                "relevance_score": 0.0,
            }
            if all(item.get("url") != rejected_url for item in self.rejected_sources):
                self.rejected_sources.append(rejection)
                self.rejected_sources = self.rejected_sources[-8:]

        if action.get("action") == "search" and success and metadata.get("search_results"):
            cached_results = []
            for item in metadata.get("search_results", [])[:12]:
                url = self.normalize_url(item.get("canonical_url") or item.get("url") or item.get("href"))
                title = str(item.get("title") or item.get("text") or "").strip()
                snippet = str(item.get("snippet") or "").strip()
                if not url or not title:
                    continue
                cached_results.append({"canonical_url": url, "text": title, "snippet": snippet})
            self.search_result_cache = cached_results

        if action.get("action") == "search" and success:
            query = str(action.get("query", "")).strip()
            if query:
                self.search_queries.append(query)
                self.search_queries = self.search_queries[-12:]

        if action.get("action") == "done" and success:
            summary = str(action.get("reason") or action.get("result") or "Completed task")[:200]
            if summary not in self.completed_goals:
                self.completed_goals.append(summary)
                self.completed_goals = self.completed_goals[-8:]

        if not success:
            signature = self.action_signature(action, current_url=final_url, metadata=metadata)
            self.failed_actions.append(signature)
            self.failed_actions = self.failed_actions[-12:]

        entry = {
            "step": step,
            "action": action,
            "thought": thought,
            "result": result,
            "success": success,
            "url": final_url or url,
            "blocked": blocked,
            "metadata": metadata,
        }
        self.history.append(entry)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        if action.get("action") == "extract":
            self.extractions.append(
                {
                    "step": step,
                    "url": final_url or url,
                    "instruction": action.get("instruction", ""),
                    "result": result[:4000],
                }
            )
            if len(self.extractions) > 12:
                self.extractions.pop(0)

    def record_rejected_action(self, *, step: int, action: dict[str, Any], reason: str, url: str | None = None) -> None:
        signature = self.action_signature(action, current_url=self.normalize_url(url))
        rejection = {
            "step": step,
            "signature": signature,
            "reason": reason,
            "url": self.normalize_url(url) or url,
        }
        self.rejected_actions.append(rejection)
        self.rejected_actions = self.rejected_actions[-10:]
        self.failed_actions.append(signature)
        self.failed_actions = self.failed_actions[-12:]

    def recent_history_text(self, count: int = 6) -> str:
        summary = self.summary()
        lines = [
            "Memory Snapshot:",
            f"- Active URL: {summary.get('active_url') or '-'}",
            f"- Visited URLs ({len(summary['visited_urls'])}): {', '.join(summary['visited_urls'][:6]) or '-'}",
            f"- Open tabs ({len(summary['opened_tabs'])}): {', '.join(summary['opened_tabs'][:5]) or '-'}",
            f"- Extracted from ({len(summary['extracted_urls'])}): {', '.join(summary['extracted_urls'][:4]) or '-'}",
            f"- Completed objectives: {', '.join(summary['completed_goals'][:4]) or '-'}",
            f"- Recent failed actions: {', '.join(summary['failed_actions'][:4]) or '-'}",
        ]

        recent = self.history[-count:]
        if not recent:
            lines.append("Recent Steps: none")
            return "\n".join(lines)

        lines.append("Recent Steps:")
        for item in recent:
            status = "SUCCESS" if item["success"] else "FAILED"
            blocked = " BLOCKED" if item.get("blocked") else ""
            action_blob = json.dumps(item["action"], ensure_ascii=True)
            result = item["result"][:250].replace("\n", " ")
            url = item.get("url") or "-"
            lines.append(
                f"Step {item['step']}: {status}{blocked} | url={url} | "
                f"action={action_blob} | thought={item['thought'][:160]} | result={result}"
            )
        return "\n".join(lines)

    def extracted_context(self) -> str:
        source_records = self.sorted_source_records(useful_only=True)
        if not source_records:
            source_records = self.sorted_source_records(useful_only=False)
        if not source_records:
            return "No extracted data yet."
        lines: list[str] = []
        for item in source_records[:5]:
            lines.extend(
                [
                    f"Source: {item['title'] or item['url']}",
                    f"URL: {item['url']}",
                    f"Summary: {item['summary']}",
                    f"Key Points: {'; '.join(item['key_points'][:4]) or '-'}",
                    f"Extracted Data: {json.dumps(item['extracted_data'], ensure_ascii=True)[:700]}",
                    "",
                ]
            )
        return "\n".join(lines)

    def report_context(self, *, limit: int = 6) -> str:
        source_records = self.sorted_source_records(useful_only=True)[:limit]
        if not source_records:
            source_records = self.sorted_source_records(useful_only=False)[:limit]
        if not source_records:
            return "No usable source records yet."
        lines: list[str] = []
        for index, item in enumerate(source_records, start=1):
            extracted = item.get("extracted_data", {}) or {}
            lines.extend(
                [
                    f"Source {index}: {item.get('title') or item.get('url')}",
                    f"URL: {item.get('url')}",
                    f"Scores: relevance={item.get('relevance_score', 0.0)}, quality={item.get('quality_score', 0.0)}, authority={item.get('authority_score', 0.0)}, freshness={item.get('freshness_score', 0.0)}",
                    f"Summary: {item.get('summary', '')}",
                    f"Key Points: {'; '.join(item.get('key_points', [])[:5]) or '-'}",
                    f"Signals: {', '.join(extracted.get('signals', [])[:6]) or '-'}",
                    f"Prices: {', '.join(extracted.get('prices', [])[:6]) or '-'}",
                    f"Stats: {', '.join(extracted.get('statistics', [])[:6]) or '-'}",
                    "",
                ]
            )
        return "\n".join(lines).strip()

    def synthesis_history_text(self, *, count: int = 8) -> str:
        source_records = self.sorted_source_records(useful_only=True)[:count]
        if not source_records:
            source_records = self.sorted_source_records(useful_only=False)[:count]

        lines = [
            "Run Summary:",
            f"- Search queries used: {', '.join(self.search_queries[-4:]) or '-'}",
            f"- Distinct external pages visited: {len({url for url in self.visited_urls if url and not self._is_search_url(url)})}",
            f"- Extracted sources: {len(self.extracted_urls)}",
        ]
        if self.completed_goals:
            lines.append(f"- Completed objectives: {', '.join(self.completed_goals[-4:])}")

        if source_records:
            lines.append("Source Notes:")
            for item in source_records:
                title = item.get("title") or item.get("url") or "Untitled source"
                summary = str(item.get("summary") or "").strip()
                points = item.get("key_points", [])[:3]
                point_text = "; ".join(str(point).strip() for point in points if str(point).strip())
                lines.append(f"- {title}: {summary[:220] or point_text or 'Evidence extracted.'}")
        else:
            lines.append("Source Notes: none")
        return "\n".join(lines)

    def research_progress(self, *, goal: str, target_sources: int) -> dict[str, Any]:
        source_records = self.sorted_source_records()
        useful_records = [item for item in source_records if item.get("useful")]
        analyzed_records = useful_records or source_records
        unique_sources = [item["url"] for item in analyzed_records if item.get("url")]
        unique_domains = {
            urlsplit(item["url"]).netloc.lower()
            for item in analyzed_records
            if item.get("url")
        }
        evidence_items = analyzed_records[-target_sources:]
        avg_quality = round(
            sum(item.get("quality_score", 0.0) for item in evidence_items) / max(len(evidence_items), 1),
            2,
        )
        avg_relevance = round(
            sum(item.get("relevance_score", 0.0) for item in evidence_items) / max(len(evidence_items), 1),
            2,
        )
        avg_authority = round(
            sum(item.get("authority_score", 0.0) for item in evidence_items) / max(len(evidence_items), 1),
            2,
        )
        avg_uniqueness = round(
            sum(item.get("uniqueness_score", 0.0) for item in evidence_items) / max(len(evidence_items), 1),
            2,
        )
        evidence_density = round(
            sum(len(item.get("key_points", [])) for item in evidence_items) / max(len(evidence_items), 1),
            2,
        )
        domain_diversity = round(min(1.0, len(unique_domains) / max(target_sources, 1)), 2)
        coverage_met = (
            len([item["url"] for item in analyzed_records if item.get("url")]) >= target_sources
            and len(evidence_items) >= target_sources
            and len(unique_domains) >= max(3, min(target_sources, 5))
            and avg_relevance >= 0.14
            and evidence_density >= 0.8
        )
        return {
            "goal": goal,
            "target_sources": target_sources,
            "unique_sources": len(unique_sources),
            "unique_domains": len(unique_domains),
            "extracted_sources": len(evidence_items),
            "useful_sources": len(useful_records) if useful_records else len(analyzed_records),
            "coverage_met": coverage_met,
            "avg_quality": avg_quality,
            "avg_relevance": avg_relevance,
            "avg_authority": avg_authority,
            "avg_uniqueness": avg_uniqueness,
            "evidence_density": evidence_density,
            "domain_diversity": domain_diversity,
            "completion_ready": coverage_met and (
                (avg_quality >= 0.38 or avg_authority >= 0.52)
                and domain_diversity >= 0.75
            ),
            "progress_score": min(
                1.0,
                (
                    (len(unique_sources) / max(target_sources, 1)) * 0.34
                    + (len(evidence_items) / max(target_sources, 1)) * 0.18
                    + (avg_relevance * 0.2)
                    + (avg_quality * 0.12)
                    + (avg_authority * 0.08)
                    + (min(evidence_density / 4.0, 1.0) * 0.04)
                    + (domain_diversity * 0.04)
                ),
            ),
        }

    def structured_evidence(self, *, limit: int = 6) -> list[dict[str, Any]]:
        items = self.sorted_source_records(useful_only=True)[:limit]
        if not items:
            items = self.sorted_source_records(useful_only=False)[:limit]
        return [
            {
                "url": item.get("url", ""),
                "title": item.get("title", ""),
                "summary": item.get("summary", ""),
                "key_points": item.get("key_points", [])[:5],
                "extracted_data": item.get("extracted_data", {}),
                "author": item.get("author", ""),
                "published_at": item.get("published_at", ""),
                "quality_score": item.get("quality_score", 0.0),
                "relevance_score": item.get("relevance_score", 0.0),
                "authority_score": item.get("authority_score", 0.0),
                "freshness_score": item.get("freshness_score", 0.0),
                "uniqueness_score": item.get("uniqueness_score", 0.0),
                "useful": item.get("useful", False),
            }
            for item in items
        ]

    def summary(self) -> dict[str, Any]:
        open_tabs = self.opened_tabs[-8:]
        visited_urls = self.visited_urls[-12:]
        external_urls = [url for url in visited_urls if url and not self._is_search_url(url)]
        repeated_actions = Counter(
            self.action_signature(item["action"], current_url=item.get("url"), metadata=item.get("metadata"))
            for item in self.history[-8:]
        )
        loop_hotspots = [signature for signature, count in repeated_actions.items() if count >= 2]
        return {
            "active_url": self.active_tab_url,
            "search_queries": self.search_queries[-8:],
            "visited_urls": visited_urls,
            "external_urls": external_urls[-8:],
            "external_domains": sorted({urlsplit(url).netloc.lower() for url in external_urls if url}),
            "clicked_targets": self.clicked_targets[-12:],
            "opened_tabs": open_tabs,
            "completed_goals": self.completed_goals[-8:],
            "failed_actions": self.failed_actions[-8:],
            "rejected_actions": self.rejected_actions[-6:],
            "rejected_sources": self.rejected_sources[-6:],
            "rejected_source_urls": [str(item.get("url")) for item in self.rejected_sources[-8:] if item.get("url")],
            "extracted_urls": self.extracted_urls[-8:],
            "evidence_count": len(self.evidence),
            "useful_sources_count": sum(1 for item in self.source_records.values() if item.get("useful")),
            "cached_search_results": self.search_result_cache[:8],
            "loop_hotspots": loop_hotspots[:5],
        }

    def evidence_snapshot(self, *, limit: int = 6) -> dict[str, Any]:
        records = self.sorted_source_records()[:limit]
        return {
            "sources": records,
            "useful_sources": [item for item in records if item.get("useful")],
            "rejected_sources": self.rejected_sources[-limit:],
        }

    def duplicate_action_reason(
        self,
        action: dict[str, Any],
        *,
        current_url: str | None = None,
        tabs: list[dict[str, Any]] | None = None,
    ) -> str | None:
        act = str(action.get("action", "")).lower()
        normalized_current = self.normalize_url(current_url)
        normalized_target_url = self.normalize_url(action.get("url"))
        signature = self.action_signature(action, current_url=normalized_current)

        if act == "click":
            click_signature = self._click_signature(action, {}, normalized_current)
            if click_signature and click_signature in self._clicked_set:
                return "This element was already clicked on the current page."
            click_target_url = self.normalize_url(action.get("url"))
            if click_target_url and (click_target_url in self._open_tab_set or click_target_url in self._extracted_url_set):
                return "That result is already open or already extracted."

        if act in {"goto", "open_tab"} and normalized_target_url:
            if normalized_target_url in self._open_tab_set:
                return "That destination is already open in an existing tab."
            if normalized_target_url in self._visited_set:
                return "That URL was already visited in this run."

        if act == "switch_tab":
            desired_index = action.get("tab_index")
            if isinstance(desired_index, int) and tabs:
                for tab in tabs:
                    if tab.get("index") == desired_index and tab.get("active"):
                        return "That tab is already active."

        if act == "search":
            query = str(action.get("query", "")).strip().lower()
            prior_same_search = [
                item for item in self.history[-4:]
                if item["action"].get("action") == "search"
                and str(item["action"].get("query", "")).strip().lower() == query
            ]
            if len(prior_same_search) >= 2:
                return "The same search query has already been run multiple times."

        if act == "extract" and normalized_current:
            if normalized_current in self._extracted_url_set:
                return "This page was already extracted, so gather a new source or synthesize the findings."

        duplicate_count = sum(
            1 for item in self.history[-5:]
            if self.action_signature(item["action"], current_url=item.get("url"), metadata=item.get("metadata")) == signature
        )
        if duplicate_count >= 2:
            return "This action pattern has already repeated on the same page."

        return None

    def loop_detected(self) -> bool:
        if len(self.history) < 4:
            return False

        last_four = self.history[-4:]
        signatures = [
            self.action_signature(item["action"], current_url=item.get("url"), metadata=item.get("metadata"))
            for item in last_four
        ]
        same_action_repeating = len(set(signatures)) == 1
        same_page = len({self.normalize_url(item.get("url")) for item in last_four}) == 1
        repeated_failures = sum(1 for item in last_four if not item["success"]) >= 2
        repeated_clicks = all(item["action"].get("action") == "click" for item in last_four)
        repeated_rejections = len(self.rejected_actions) >= 3 and len(
            {item["signature"] for item in self.rejected_actions[-3:]}
        ) == 1

        return repeated_rejections or (same_action_repeating and same_page and (repeated_failures or repeated_clicks))

    def last_failure_summary(self) -> str:
        failures = [item for item in self.history if not item["success"]]
        rejection_lines = [item["reason"] for item in self.rejected_actions[-2:]]
        if not failures and not rejection_lines:
            return "No recent failures."
        recent = [item["result"][:160] for item in failures[-3:]] + rejection_lines
        return " | ".join(recent[:4])

    def has_extracted_url(self, url: str | None) -> bool:
        normalized = self.normalize_url(url)
        return bool(normalized and normalized in self._extracted_url_set)

    def action_signature(
        self,
        action: dict[str, Any],
        *,
        current_url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        metadata = metadata or {}
        normalized_current = self.normalize_url(current_url)
        normalized_target = self.normalize_url(metadata.get("target_url") or action.get("url"))
        payload = {
            "action": str(action.get("action", "")).lower(),
            "current_url": normalized_current,
            "target_url": normalized_target,
            "element_id": action.get("element_id"),
            "target": str(action.get("target", "")).strip().lower(),
            "query": str(action.get("query", "")).strip().lower(),
            "instruction": str(action.get("instruction", "")).strip().lower()[:140],
            "tab_index": action.get("tab_index"),
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=True)

    @classmethod
    def normalize_url(cls, url: Any) -> str:
        if not url:
            return ""
        raw = str(url).strip()
        if not raw or raw in {"about:blank", "chrome://newtab/"}:
            return ""
        if not raw.startswith(("http://", "https://")):
            return raw.lower().rstrip("/")

        split = urlsplit(raw)
        netloc = split.netloc.lower()
        path = split.path or "/"
        if path != "/":
            path = path.rstrip("/")

        filtered_query = []
        for key, value in parse_qsl(split.query, keep_blank_values=True):
            key_lower = key.lower()
            if key_lower in TRACKING_QUERY_KEYS or any(key_lower.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
                continue
            filtered_query.append((key, value))

        filtered_query.sort()
        normalized_query = urlencode(filtered_query, doseq=True)
        return urlunsplit((split.scheme.lower(), netloc, path, normalized_query, ""))

    def _remember_url(self, normalized_url: str) -> None:
        if not normalized_url or normalized_url in self._visited_set:
            return
        self._visited_set.add(normalized_url)
        self.visited_urls.append(normalized_url)
        self.visited_urls = self.visited_urls[-18:]

    def _remember_tab(self, normalized_url: str) -> None:
        if not normalized_url or normalized_url in self._open_tab_set:
            return
        self._open_tab_set.add(normalized_url)
        self.opened_tabs.append(normalized_url)
        self.opened_tabs = self.opened_tabs[-10:]

    def _remember_click(self, signature: str) -> None:
        if not signature or signature in self._clicked_set:
            return
        self._clicked_set.add(signature)
        self.clicked_targets.append(signature)
        self.clicked_targets = self.clicked_targets[-18:]

    def _click_signature(self, action: dict[str, Any], metadata: dict[str, Any], current_url: str | None) -> str:
        if str(action.get("action", "")).lower() != "click":
            return ""
        normalized_current = self.normalize_url(metadata.get("source_url") or current_url)
        return json.dumps(
            {
                "current_url": normalized_current,
                "element_id": action.get("element_id"),
                "target": str(action.get("target", "")).strip().lower(),
            },
            sort_keys=True,
            ensure_ascii=True,
        )

    @staticmethod
    def _is_search_url(url: str) -> bool:
        return any(host_hint in url for host_hint in SEARCH_HOST_HINTS)

    @staticmethod
    def _quality_score(text: str) -> float:
        if not text:
            return 0.0
        compact = text.strip()
        length_factor = min(len(compact) / 800, 1.0)
        list_factor = 0.2 if "\n" in compact or "-" in compact else 0.0
        numeric_factor = 0.2 if any(char.isdigit() for char in compact) else 0.0
        return round(min(1.0, 0.3 + length_factor * 0.5 + list_factor + numeric_factor), 2)

    @staticmethod
    def _relevance_score(text: str, instruction: str) -> float:
        if not text:
            return 0.0
        text_lower = text.lower()
        raw_terms = set(re.findall(r"[a-z0-9]{4,}", instruction.lower()))
        stop_terms = {
            "extract",
            "exactly",
            "related",
            "instruction",
            "standout",
            "suggested",
            "themes",
            "angles",
            "what",
            "with",
            "from",
            "into",
            "that",
            "this",
            "needed",
        }
        terms = {token for token in raw_terms if token not in stop_terms}
        if not terms:
            return 0.4
        hits = sum(1 for token in terms if token in text_lower)
        core_hits = sum(1 for token in terms if token in {"seo", "keyword", "keywords", "pricing", "price", "plan", "plans", "fitness", "course", "courses", "competitor", "trend", "trends"} and token in text_lower)
        score = min(1.0, (hits / max(min(len(terms), 8), 1)) + (core_hits * 0.08))
        return round(score, 2)

    def sorted_source_records(self, *, useful_only: bool = False) -> list[dict[str, Any]]:
        records = list(self.source_records.values())
        if useful_only:
            records = [item for item in records if item.get("useful")]
        records.sort(
            key=lambda item: (
                item.get("useful", False),
                item.get("relevance_score", 0.0),
                item.get("quality_score", 0.0),
                item.get("authority_score", 0.0),
                item.get("uniqueness_score", 0.0),
            ),
            reverse=True,
        )
        return records

    def _build_source_record(
        self,
        *,
        url: str,
        instruction: str,
        snippet: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_url = self.normalize_url(url)
        title = str(metadata.get("title") or "").strip()
        headings = [str(item).strip() for item in metadata.get("headings") or [] if str(item).strip()]
        lists = metadata.get("lists") or []
        links = metadata.get("links") or []
        tables = metadata.get("tables") or []
        main_content = str(metadata.get("main_content") or metadata.get("content") or "").strip()
        author = str(metadata.get("author") or "").strip()
        published_at = str(metadata.get("published_at") or "").strip()
        summary = self._build_source_summary(title=title, snippet=snippet, main_content=main_content, headings=headings)
        key_points = self._extract_key_points(
            snippet=snippet,
            main_content=main_content,
            headings=headings,
            lists=lists,
        )
        extracted_data = self._extract_structured_data(snippet=snippet, main_content=main_content, tables=tables, links=links, headings=headings)
        quality_score = self._quality_score(snippet or main_content[:1200])
        relevance_score = self._relevance_score(f"{title}\n{snippet}\n{main_content[:1200]}", instruction)
        authority_score = self._authority_score(normalized_url)
        freshness_score = self._freshness_score(published_at, main_content)
        uniqueness_score = self._uniqueness_score(normalized_url, summary, key_points)
        useful = relevance_score >= 0.08 and quality_score >= 0.24 and (
            len(key_points) >= 2
            or bool(extracted_data.get("prices"))
            or bool(extracted_data.get("statistics"))
            or bool(extracted_data.get("important_links"))
            or bool(extracted_data.get("signals"))
            or len(main_content) >= 140
            or len(snippet) >= 70
        )
        return {
            "url": normalized_url,
            "title": title,
            "summary": summary,
            "key_points": key_points[:8],
            "extracted_data": extracted_data,
            "quality_score": quality_score,
            "relevance_score": relevance_score,
            "authority_score": authority_score,
            "freshness_score": freshness_score,
            "uniqueness_score": uniqueness_score,
            "useful": useful,
            "author": author,
            "published_at": published_at,
            "instruction": instruction,
            "headings": headings[:10],
            "links": links[:12],
            "tables": tables[:3],
        }

    @staticmethod
    def _build_source_summary(*, title: str, snippet: str, main_content: str, headings: list[str]) -> str:
        candidates = [title.strip(), *[item.strip() for item in headings[:3] if item.strip()]]
        cleaned_snippet = " ".join((snippet or main_content).split())
        if cleaned_snippet:
            candidates.append(cleaned_snippet[:320])
        summary = " ".join(item for item in candidates if item)
        summary = re.sub(r"\s+", " ", summary).strip()
        return summary[:420]

    @staticmethod
    def _extract_key_points(
        *,
        snippet: str,
        main_content: str,
        headings: list[str],
        lists: list[Any],
    ) -> list[str]:
        points: list[str] = []
        for heading in headings[:4]:
            if len(heading.split()) >= 3:
                points.append(heading)
        for item in lists[:4]:
            for entry in item[:3]:
                cleaned = " ".join(str(entry).split()).strip()
                if cleaned and len(cleaned) >= 20:
                    points.append(cleaned)
        for sentence in re.split(r"(?<=[.!?])\s+", " ".join((snippet or main_content[:1800]).split())):
            sentence = sentence.strip(" -•\t")
            if len(sentence) < 32:
                continue
            if any(token in sentence.lower() for token in ("price", "pricing", "tier", "subscription", "keyword", "seo", "trend", "revenue", "monthly", "yearly", "%", "$", "£", "€")):
                points.append(sentence)
            if len(points) >= 8:
                break
        deduped: list[str] = []
        seen: set[str] = set()
        for point in points:
            key = point.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(point[:240])
        return deduped[:8]

    @staticmethod
    def _extract_structured_data(
        *,
        snippet: str,
        main_content: str,
        tables: list[Any],
        links: list[Any],
        headings: list[str],
    ) -> dict[str, Any]:
        content_blob = f"{snippet}\n{main_content}"
        prices = re.findall(r"(?:[$£€]\s?\d[\d,]*(?:\.\d{1,2})?|(?:\d[\d,]*(?:\.\d{1,2})?)\s?(?:USD|GBP|EUR|dollars|per month|monthly|yearly))", content_blob, re.IGNORECASE)
        percents = re.findall(r"\b\d{1,3}%\b", content_blob)
        keywords = []
        for heading in headings[:6]:
            lower = heading.lower()
            if any(token in lower for token in ("keyword", "pricing", "plan", "tier", "trend", "strategy")):
                keywords.append(heading)
        return {
            "prices": prices[:10],
            "statistics": percents[:10],
            "tables": tables[:2],
            "important_links": links[:6],
            "signals": keywords[:6],
        }

    @staticmethod
    def _authority_score(url: str) -> float:
        host = urlsplit(url).netloc.lower()
        if not host:
            return 0.2
        strong_hosts = (
            ".gov", ".edu", "docs.", "developer.", "support.", "official", "pricing", "blog.", "substack.com", "medium.com",
        )
        weak_hosts = ("pinterest.", "facebook.", "instagram.", "youtube.", "tiktok.")
        score = 0.45
        if any(token in host for token in strong_hosts):
            score += 0.22
        if host.count(".") <= 2:
            score += 0.1
        if any(token in host for token in weak_hosts):
            score -= 0.18
        return round(max(0.1, min(score, 1.0)), 2)

    @staticmethod
    def _freshness_score(published_at: str, content: str) -> float:
        year_match = re.search(r"\b(20\d{2})\b", f"{published_at} {content[:800]}")
        if not year_match:
            return 0.45
        year = int(year_match.group(1))
        if year >= 2026:
            return 1.0
        if year >= 2025:
            return 0.85
        if year >= 2024:
            return 0.7
        if year >= 2023:
            return 0.58
        return 0.42

    def _uniqueness_score(self, url: str, summary: str, key_points: list[str]) -> float:
        existing = [item for existing_url, item in self.source_records.items() if existing_url != url]
        if not existing:
            return 0.95
        summary_terms = {token for token in re.findall(r"[a-z0-9]{4,}", summary.lower())}
        if not summary_terms:
            return 0.5
        overlap_scores = []
        for item in existing:
            other_terms = {token for token in re.findall(r"[a-z0-9]{4,}", str(item.get("summary", "")).lower())}
            if not other_terms:
                continue
            overlap = len(summary_terms & other_terms) / max(len(summary_terms | other_terms), 1)
            overlap_scores.append(overlap)
        overlap = max(overlap_scores, default=0.0)
        richness_bonus = min(len(key_points) / 6, 0.25)
        return round(max(0.15, min(1.0, 1.0 - overlap + richness_bonus)), 2)
