from __future__ import annotations

import asyncio
import html
import random
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote_plus, unquote, urljoin

import httpx

from playwright.async_api import Download, Locator, TimeoutError as PlaywrightTimeoutError

from app.services.browser_agent.session_manager import SessionManager


@dataclass
class ExecutionResult:
    success: bool
    message: str
    blocked: bool = False
    data: dict[str, Any] = field(default_factory=dict)


class BrowserExecutor:
    """Executes browser actions through Playwright with human-like pacing."""

    def __init__(self, session_manager: SessionManager) -> None:
        self.session_manager = session_manager

    async def execute(self, action: dict[str, Any], dom_snapshot: dict[str, Any]) -> ExecutionResult:
        page = await self.session_manager.get_page()
        act = str(action.get("action", "")).strip().lower()

        try:
            if act == "goto":
                url = self._normalize_url(action.get("url", ""))
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await self._pause(1.0, 1.8)
                return await self._finalize(f"Navigated to {url}")

            if act == "search":
                query = str(action.get("query", "")).strip()
                engine = str(action.get("search_engine", "duckduckgo")).lower()
                return await self._search(query, engine)

            if act == "click":
                current_url = page.url
                locator = await self._resolve_locator(action, dom_snapshot)
                target_url = await self._get_target_url(locator, action, dom_snapshot)
                opens_new_tab = await self._opens_new_tab(locator)

                if target_url:
                    existing = await self.session_manager.find_tab_by_url(target_url)
                    if existing is not None:
                        await self.session_manager.switch_to_page(existing)
                        return await self._finalize(
                            f"Focused existing tab for {self._describe_target(action)}",
                            data={
                                "url": existing.url,
                                "source_url": current_url,
                                "target_url": target_url,
                                "reused_tab": True,
                            },
                        )

                    if self._should_open_result_in_new_tab(current_url, target_url):
                        opened_page, reused = await self.session_manager.focus_or_create_tab(target_url)
                        await self._pause(0.8, 1.4)
                        return await self._finalize(
                            f"Opened search result in tab for {self._describe_target(action)}",
                            data={
                                "url": opened_page.url,
                                "source_url": current_url,
                                "target_url": target_url,
                                "opened_in_new_tab": not reused,
                                "reused_tab": reused,
                                "preserved_search_tab": True,
                            },
                        )

                    if opens_new_tab:
                        opened_page, reused = await self.session_manager.focus_or_create_tab(target_url)
                        await self._pause(0.8, 1.4)
                        return await self._finalize(
                            f"Opened target in tab for {self._describe_target(action)}",
                            data={
                                "url": opened_page.url,
                                "source_url": current_url,
                                "target_url": target_url,
                                "opened_in_new_tab": not reused,
                                "reused_tab": reused,
                            },
                        )

                await self._hover_locator(locator)
                await locator.click(timeout=12000)
                await self._pause(1.0, 1.8)
                await self.session_manager.enforce_tab_policy()
                return await self._finalize(
                    f"Clicked {self._describe_target(action)}",
                    data={"source_url": current_url, "target_url": target_url},
                )

            if act == "type":
                locator = await self._resolve_locator(action, dom_snapshot)
                await locator.click(timeout=12000)
                await self._pause(0.1, 0.3)
                await locator.fill("")
                await self._type_like_human(str(action.get("text", "")))
                if action.get("submit"):
                    await page.keyboard.press("Enter")
                await self._pause(0.8, 1.6)
                return await self._finalize(f"Typed into {self._describe_target(action)}")

            if act == "press":
                await page.keyboard.press(str(action.get("key", "Enter")))
                await self._pause(0.5, 1.0)
                return await self._finalize(f"Pressed {action.get('key', 'Enter')}")

            if act == "hover":
                locator = await self._resolve_locator(action, dom_snapshot)
                await self._hover_locator(locator)
                return await self._finalize(f"Hovered {self._describe_target(action)}")

            if act == "scroll":
                direction = str(action.get("direction", "down")).lower()
                amount = int(action.get("amount", 700))
                await page.mouse.wheel(0, amount if direction == "down" else -amount)
                await self._pause(0.7, 1.3)
                return await self._finalize(f"Scrolled {direction} by {amount}px")

            if act == "wait":
                seconds = max(1.0, min(float(action.get("seconds", 2)), 10.0))
                await asyncio.sleep(seconds)
                return await self._finalize(f"Waited {seconds:.1f}s")

            if act == "extract":
                instruction = str(action.get("instruction", "Extract useful information."))
                text = await page.locator("body").inner_text(timeout=10000)
                relevant_excerpt = self._extract_relevant_excerpt(text, instruction)
                page_artifacts = await page.evaluate(
                    """
                    () => {
                      const clean = (value) => (value || "").replace(/\\s+/g, " ").trim();
                      const collect = (selector, limit = 12) =>
                        Array.from(document.querySelectorAll(selector))
                          .map((node) => clean(node.innerText || node.textContent || ""))
                          .filter(Boolean)
                          .slice(0, limit);

                      const collectLinks = () =>
                        Array.from(document.querySelectorAll("a[href]"))
                          .map((node) => ({
                            text: clean(node.innerText || node.textContent || ""),
                            href: node.href || "",
                          }))
                          .filter((item) => item.href && item.text && item.text.length > 2)
                          .slice(0, 20);

                      const articleRoot =
                        document.querySelector("article") ||
                        document.querySelector("main") ||
                        document.querySelector("[role='main']") ||
                        document.body;

                      const meta = (name) =>
                        document.querySelector(`meta[name="${name}"]`)?.getAttribute("content") ||
                        document.querySelector(`meta[property="${name}"]`)?.getAttribute("content") ||
                        "";

                      return {
                        page_title: clean(document.title),
                        headings: collect("h1, h2, h3", 14),
                        lists: Array.from(document.querySelectorAll("ul, ol"))
                          .slice(0, 6)
                          .map((list) =>
                            Array.from(list.querySelectorAll("li"))
                              .map((item) => clean(item.innerText || item.textContent || ""))
                              .filter(Boolean)
                              .slice(0, 8)
                          )
                          .filter((items) => items.length > 0),
                        links: collectLinks(),
                        author: clean(
                          meta("author") ||
                          document.querySelector("[rel='author']")?.textContent ||
                          document.querySelector("[itemprop='author']")?.textContent ||
                          ""
                        ),
                        published_at: clean(
                          meta("article:published_time") ||
                          meta("publish_date") ||
                          document.querySelector("time")?.getAttribute("datetime") ||
                          document.querySelector("time")?.textContent ||
                          ""
                        ),
                        main_content: clean(articleRoot?.innerText || articleRoot?.textContent || "").slice(0, 7000),
                      };
                    }
                    """
                )
                tables = await page.evaluate(
                    """
                    () => Array.from(document.querySelectorAll("table")).slice(0, 3).map((table) =>
                      Array.from(table.querySelectorAll("tr")).slice(0, 8).map((row) =>
                        Array.from(row.querySelectorAll("th,td")).map((cell) => cell.innerText.trim())
                      )
                    )
                    """
                )
                data = {
                    "instruction": instruction,
                    "title": page_artifacts.get("page_title") or page.title(),
                    "headings": page_artifacts.get("headings") or [],
                    "lists": page_artifacts.get("lists") or [],
                    "links": page_artifacts.get("links") or [],
                    "author": page_artifacts.get("author") or "",
                    "published_at": page_artifacts.get("published_at") or "",
                    "main_content": page_artifacts.get("main_content") or "",
                    "content": text[:5000],
                    "summary_excerpt": relevant_excerpt,
                    "tables": tables,
                }
                return await self._finalize(f"Extracted page content for: {instruction}", data=data)

            if act == "select_option":
                locator = await self._resolve_locator(action, dom_snapshot)
                value = str(action.get("value", ""))
                await locator.select_option(value=value)
                await self._pause(0.6, 1.2)
                return await self._finalize(f"Selected option '{value}' in {self._describe_target(action)}")

            if act == "upload_file":
                locator = await self._resolve_locator(action, dom_snapshot)
                await locator.set_input_files(str(action.get("file_path", "")))
                await self._pause(0.8, 1.4)
                return await self._finalize(f"Uploaded file via {self._describe_target(action)}")

            if act == "download":
                locator = await self._resolve_locator(action, dom_snapshot)
                async with page.expect_download(timeout=20000) as download_info:
                    await locator.click()
                download = await download_info.value
                file_path = await self._save_download(download)
                return await self._finalize("Downloaded file", data={"file_path": file_path})

            if act == "open_tab":
                url = self._normalize_url(action.get("url", ""))
                page, reused = await self.session_manager.focus_or_create_tab(url)
                message = f"{'Focused existing tab' if reused else 'Opened new tab'}: {url}"
                return await self._finalize(message, data={"url": page.url, "target_url": url, "reused_tab": reused})

            if act == "switch_tab":
                tab_index = int(action.get("tab_index", 0))
                page = await self.session_manager.switch_tab(tab_index)
                return await self._finalize(f"Switched to tab {tab_index}", data={"url": page.url})

            if act == "close_tab":
                page = await self.session_manager.close_current_tab()
                url = page.url if page else ""
                return await self._finalize("Closed current tab", data={"url": url})

            if act == "back":
                await page.go_back(wait_until="domcontentloaded")
                await self._pause(0.8, 1.4)
                return await self._finalize("Navigated back")

            if act == "done":
                return await self._finalize(action.get("result", "Task completed."))

            if act == "error":
                return ExecutionResult(success=False, message=str(action.get("error", "Planner returned an error")))

            return ExecutionResult(success=False, message=f"Unsupported action '{act}'")
        except PlaywrightTimeoutError as exc:
            return await self._blocked_or_failed(f"Timed out while executing {act}: {exc}")
        except Exception as exc:
            return await self._blocked_or_failed(f"Execution failed for {act}: {exc}")

    async def _search(self, query: str, engine: str) -> ExecutionResult:
        page = await self.session_manager.get_page()
        engine = engine.lower()
        search_configs = {
            "bing": (
                "https://www.bing.com/",
                'textarea[name="q"], input[name="q"]',
                "https://www.bing.com/search?q={query}",
                "#b_results a[href]",
            ),
            "duckduckgo": (
                "https://lite.duckduckgo.com/lite/?q={query}",
                'input[name="q"]',
                "https://lite.duckduckgo.com/lite/?q={query}",
                ".result__title a[href], .result__a[href], .links_main a[href], a.result-link[href], a[href][rel='nofollow']",
            ),
        }
        ordered_engines = []
        fallback_candidates = [engine]
        if engine not in search_configs:
            fallback_candidates.append("duckduckgo")
        for candidate in fallback_candidates:
            if candidate not in ordered_engines:
                ordered_engines.append(candidate)

        last_error = "Search failed."
        for candidate in ordered_engines:
            if candidate not in search_configs:
                continue
            try:
                url, selector, search_template, result_selector = search_configs[candidate]
                direct_url = search_template.format(query=quote_plus(query))
                if candidate == "duckduckgo":
                    await page.goto(direct_url, wait_until="domcontentloaded", timeout=45000)
                else:
                    await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                    await self._pause(1.0, 1.7)
                    box = page.locator(selector).first
                    await box.wait_for(timeout=12000)
                    await box.click()
                    await self._type_like_human(query)
                    await page.keyboard.press("Enter")
                await self._wait_for_search_results(page, result_selector)
                await self._pause(1.0, 1.8)
                blockers = await self.session_manager.detect_blockers()
                if blockers:
                    last_error = f"Search engine {candidate} blocked automation: {', '.join(blockers)}"
                    if candidate == "duckduckgo":
                        bootstrap_results = await self._fetch_duckduckgo_results(query)
                        if len(bootstrap_results) >= 3:
                            return ExecutionResult(
                                success=True,
                                message=f"Prepared DuckDuckGo result set for '{query}' via resilient search bootstrap",
                                data={"search_results": bootstrap_results, "search_query": query, "search_engine": candidate},
                            )
                    await page.goto(direct_url, wait_until="domcontentloaded", timeout=45000)
                    await self._wait_for_search_results(page, result_selector)
                    await self._pause(1.0, 1.8)
                    blockers = await self.session_manager.detect_blockers()
                    if blockers:
                        if candidate == "duckduckgo":
                            bootstrap_results = await self._fetch_duckduckgo_results(query)
                            if len(bootstrap_results) >= 3:
                                return ExecutionResult(
                                    success=True,
                                    message=f"Prepared DuckDuckGo result set for '{query}' via resilient search bootstrap",
                                    data={"search_results": bootstrap_results, "search_query": query, "search_engine": candidate},
                                )
                        continue
                    result_count = await self._count_search_results(page, result_selector)
                    if result_count < 2:
                        last_error = f"{candidate} direct search returned too few usable results"
                        if candidate == "duckduckgo":
                            bootstrap_results = await self._fetch_duckduckgo_results(query)
                            if len(bootstrap_results) >= 3:
                                return ExecutionResult(
                                    success=True,
                                    message=f"Prepared DuckDuckGo result set for '{query}' via resilient search bootstrap",
                                    data={"search_results": bootstrap_results, "search_query": query, "search_engine": candidate},
                                )
                        continue
                    return await self._finalize(f"Searched {candidate} for '{query}' via direct search URL")
                result_count = await self._count_search_results(page, result_selector)
                if result_count < 2:
                    last_error = f"{candidate} search returned too few usable results"
                    if candidate == "duckduckgo":
                        bootstrap_results = await self._fetch_duckduckgo_results(query)
                        if len(bootstrap_results) >= 3:
                            return ExecutionResult(
                                success=True,
                                message=f"Prepared DuckDuckGo result set for '{query}' via resilient search bootstrap",
                                data={"search_results": bootstrap_results, "search_query": query, "search_engine": candidate},
                            )
                    continue
                return await self._finalize(f"Searched {candidate} for '{query}'")
            except Exception as exc:
                last_error = f"{candidate} search failed: {exc}"

        return await self._blocked_or_failed(last_error)

    async def _fetch_duckduckgo_results(self, query: str) -> list[dict[str, str]]:
        search_url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                response = await client.get(search_url, headers=headers)
                response.raise_for_status()
                markup = response.text
        except Exception:
            return []

        matches = re.findall(r'<a rel="nofollow" href="([^"]+)".*?>(.*?)</a>', markup, flags=re.IGNORECASE | re.DOTALL)
        results: list[dict[str, str]] = []
        seen: set[str] = set()
        for href, raw_title in matches:
            title = html.unescape(re.sub(r"<.*?>", "", raw_title or "")).strip()
            target_url = self._canonical_search_result_url(href, base_url="https://lite.duckduckgo.com/")
            lower_url = target_url.lower()
            if not title or not target_url or lower_url in seen:
                continue
            if any(token in lower_url for token in ("duckduckgo.com/y.js", "bing.com/aclick", "javascript:", "mailto:")):
                continue
            seen.add(lower_url)
            results.append({"canonical_url": target_url, "title": title, "snippet": ""})
            if len(results) >= 10:
                break
        return results

    async def _resolve_locator(self, action: dict[str, Any], dom_snapshot: dict[str, Any]) -> Locator:
        page = await self.session_manager.get_page()

        if action.get("element_id") is not None:
            element_id = int(action["element_id"])
            element = next((item for item in dom_snapshot.get("elements", []) if item.get("id") == element_id), None)
            if element:
                return await self._locator_from_element(element)

        target = str(action.get("target", "")).strip()
        if target:
            escaped = target.replace('"', '\\"')
            candidate_selectors = [
                f'text="{escaped}"',
                f'button:has-text("{escaped}")',
                f'a:has-text("{escaped}")',
                f'input[placeholder*="{escaped}" i]',
                f'input[aria-label*="{escaped}" i]',
                f'text=/{self._regex_escape(target)}/i',
            ]
            for selector in candidate_selectors:
                locator = page.locator(selector).first
                if await locator.count():
                    return locator

        raise ValueError(f"Could not resolve target: {action}")

    async def _locator_from_element(self, element: dict[str, Any]) -> Locator:
        page = await self.session_manager.get_page()
        text = str(element.get("text", "")).strip()
        href = str(element.get("href", "")).strip()
        placeholder = str(element.get("placeholder", "")).strip()
        name = str(element.get("name", "")).strip()
        tag = str(element.get("tag", "")).strip()
        safe_text = text.replace('"', '\\"')

        selectors = []
        if href:
            selectors.append(f'{tag}[href="{href}"]')
        if name:
            selectors.append(f'{tag}[name="{name}"]')
        if placeholder:
            selectors.append(f'{tag}[placeholder="{placeholder}"]')
        if text and tag in {"button", "a"}:
            selectors.append(f'{tag}:has-text("{safe_text}")')
        if text:
            selectors.append(f'text="{safe_text}"')

        for selector in selectors:
            locator = page.locator(selector).first
            if await locator.count():
                return locator

        x = element.get("x")
        y = element.get("y")
        if x is not None and y is not None:
            return page.locator(f"body").first

        raise ValueError(f"Unable to resolve element {element}")

    async def _get_target_url(
        self,
        locator: Locator,
        action: dict[str, Any],
        dom_snapshot: dict[str, Any],
    ) -> str:
        page = await self.session_manager.get_page()
        if action.get("url"):
            return self._normalize_url(str(action.get("url", "")))

        try:
            href = await locator.get_attribute("href")
            if href:
                return self._normalize_url(urljoin(page.url, href))
        except Exception:
            pass

        element_id = action.get("element_id")
        if element_id is not None:
            element = next((item for item in dom_snapshot.get("elements", []) if item.get("id") == int(element_id)), None)
            if element and element.get("href"):
                return self._normalize_url(urljoin(page.url, str(element.get("href", ""))))

        return ""

    async def _opens_new_tab(self, locator: Locator) -> bool:
        try:
            target = await locator.get_attribute("target")
            rel = (await locator.get_attribute("rel") or "").lower()
            return target == "_blank" or "noopener" in rel or "noreferrer" in rel
        except Exception:
            return False

    async def _hover_locator(self, locator: Locator) -> None:
        await locator.hover(timeout=10000)
        await self._pause(0.1, 0.3)

    async def _type_like_human(self, text: str) -> None:
        page = await self.session_manager.get_page()
        for char in text:
            await page.keyboard.type(char, delay=random.randint(40, 120))
            if random.random() < 0.08:
                await asyncio.sleep(random.uniform(0.05, 0.15))

    async def _pause(self, min_seconds: float, max_seconds: float) -> None:
        await asyncio.sleep(random.uniform(min_seconds, max_seconds))

    async def _wait_for_search_results(self, page, selector: str) -> None:
        try:
            await page.locator(selector).first.wait_for(timeout=8000)
        except Exception:
            await self._pause(1.5, 2.2)
        await page.wait_for_load_state("domcontentloaded")

    async def _count_search_results(self, page, selector: str) -> int:
        try:
            locator = page.locator(selector)
            count = await locator.count()
            if count <= 0:
                return 0
            usable = 0
            for index in range(min(count, 12)):
                href = (await locator.nth(index).get_attribute("href") or "").strip().lower()
                if not href or href.startswith("mailto:"):
                    continue
                usable += 1
            return usable
        except Exception:
            return 0

    async def _finalize(self, message: str, *, data: dict[str, Any] | None = None) -> ExecutionResult:
        blockers = await self.session_manager.detect_blockers()
        return ExecutionResult(
            success=not blockers,
            blocked=bool(blockers),
            message=message if not blockers else f"{message} | blockers: {', '.join(blockers)}",
            data=data or {},
        )

    async def _blocked_or_failed(self, message: str) -> ExecutionResult:
        blockers = await self.session_manager.detect_blockers()
        return ExecutionResult(success=False, blocked=bool(blockers), message=message, data={"blockers": blockers})

    async def _save_download(self, download: Download) -> str:
        target = self.session_manager.download_dir()
        suggested = download.suggested_filename
        path = f"{target}/{suggested}"
        await download.save_as(path)
        return path

    @staticmethod
    def _normalize_url(url: str) -> str:
        url = url.strip()
        if url.startswith("http://") or url.startswith("https://"):
            return url
        return f"https://{url}"

    @staticmethod
    def _canonical_search_result_url(href: str, *, base_url: str) -> str:
        absolute = urljoin(base_url, href)
        if "uddg=" in absolute:
            try:
                encoded = absolute.split("uddg=", 1)[1].split("&", 1)[0]
                return unquote(html.unescape(encoded))
            except Exception:
                return absolute
        return absolute

    @staticmethod
    def _describe_target(action: dict[str, Any]) -> str:
        if action.get("target"):
            return str(action["target"])
        if action.get("element_id") is not None:
            return f"element #{action['element_id']}"
        return "target"

    @staticmethod
    def _regex_escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("/", "\\/").replace('"', '\\"')

    @staticmethod
    def _should_open_result_in_new_tab(current_url: str, target_url: str) -> bool:
        current_lower = (current_url or "").lower()
        target_lower = (target_url or "").lower()
        is_search_page = any(host in current_lower for host in ("duckduckgo.com", "bing.com", "google."))
        is_external = bool(target_lower) and not any(host in target_lower for host in ("duckduckgo.com", "bing.com", "google."))
        return is_search_page and is_external

    @staticmethod
    def _extract_relevant_excerpt(text: str, instruction: str) -> str:
        lines = [" ".join(line.split()) for line in text.splitlines()]
        filtered = [
            line for line in lines
            if len(line) >= 28
            and not line.lower().startswith(("log in", "sign up", "skip to", "contact", "book demo", "try for free"))
        ]
        instruction_terms = {token.lower().strip(".,:;!?") for token in instruction.split() if len(token) > 3}
        scored: list[tuple[int, str]] = []
        for line in filtered:
            lower = line.lower()
            score = sum(2 for term in instruction_terms if term in lower)
            score += sum(3 for token in ("pricing", "price", "plan", "subscription", "keyword", "seo", "tier", "$", "£", "€", "%") if token in lower)
            if "cookie" in lower or "privacy" in lower or "menu" in lower:
                score -= 4
            if score > 0:
                scored.append((score, line))
        scored.sort(key=lambda item: item[0], reverse=True)
        chosen = [line for _score, line in scored[:8]]
        if not chosen:
            chosen = filtered[:8]
        return "\n".join(chosen)[:2400]
