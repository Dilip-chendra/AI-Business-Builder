from __future__ import annotations

import asyncio
import base64
import logging
import random
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.async_api import Browser, BrowserContext, Page, Playwright, async_playwright
from playwright_stealth import Stealth

from app.core.config import settings

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

VIEWPORTS = [
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1536, "height": 864},
    {"width": 1600, "height": 900},
]

BLOCK_PATTERNS = [
    "unusual traffic",
    "verify you are human",
    "access denied",
    "captcha",
    "robot",
    "security check",
    "temporarily blocked",
    "error getting results",
    "too many requests",
    "unable to process this search",
    "we hit an error",
]

TRACKING_QUERY_PREFIXES = ("utm_",)
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


class SessionManager:
    """Owns a persistent Playwright browser context and active tabs."""

    def __init__(self, *, headless: bool | None = None, session_id: str | None = None) -> None:
        self.headless = settings.browser_headless if headless is None else headless
        self.session_id = session_id or "default"
        root = Path(settings.browser_session_root)
        root.mkdir(parents=True, exist_ok=True)
        self.user_data_dir = root / f"autonomous_browser_agent_{self.session_id}"
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.storage_state_path = self.user_data_dir / "storage-state.json"
        self._downloads_dir = self.user_data_dir / "downloads"
        self._downloads_dir.mkdir(parents=True, exist_ok=True)

        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._current_page: Page | None = None
        self._user_agent = random.choice(USER_AGENTS)
        self._viewport = random.choice(VIEWPORTS)
        self._stealth = Stealth(navigator_user_agent_override=self._user_agent)
        self._context_wired = False

    async def start(self) -> Page:
        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._browser is None:
            logger.info(
                "Launching browser session=%s headless=%s profile=%s",
                self.session_id,
                self.headless,
                self.user_data_dir,
            )
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-infobars",
                    "--disable-features=IsolateOrigins,site-per-process",
                ],
            )
        if self._context is None:
            context_kwargs: dict[str, Any] = {
                "viewport": self._viewport,
                "user_agent": self._user_agent,
                "locale": "en-US",
                "timezone_id": "Asia/Kolkata",
                "color_scheme": "light",
                "accept_downloads": True,
                "ignore_https_errors": True,
                "java_script_enabled": True,
            }
            if self.storage_state_path.exists():
                context_kwargs["storage_state"] = str(self.storage_state_path)
            self._context = await self._browser.new_context(**context_kwargs)
            await self._context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
                window.chrome = window.chrome || { runtime: {} };
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                """
            )
            self._wire_context(self._context)

        if not self._context.pages:
            self._current_page = await self._context.new_page()
        elif self._current_page is None or self._current_page.is_closed():
            self._current_page = self._context.pages[0]

        await self._apply_stealth(self._current_page)
        self._wire_page(self._current_page)
        return self._current_page

    async def get_page(self) -> Page:
        if self._current_page is None or self._current_page.is_closed():
            return await self.start()
        return self._current_page

    async def create_tab(self, url: str | None = None) -> Page:
        if url:
            existing = await self.find_tab_by_url(url)
            if existing is not None:
                await existing.bring_to_front()
                self._current_page = existing
                return existing
        context = await self._get_context()
        page = await context.new_page()
        await self._apply_stealth(page)
        self._wire_page(page)
        self._current_page = page
        if url:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await self.enforce_tab_policy()
        return page

    async def switch_tab(self, tab_index: int) -> Page:
        context = await self._get_context()
        pages = context.pages
        if tab_index < 0 or tab_index >= len(pages):
            raise IndexError(f"Tab index {tab_index} is out of range.")
        self._current_page = pages[tab_index]
        await self._current_page.bring_to_front()
        return self._current_page

    async def close_current_tab(self) -> Page | None:
        page = await self.get_page()
        await page.close()
        context = await self._get_context()
        pages = [candidate for candidate in context.pages if not candidate.is_closed()]
        self._current_page = pages[-1] if pages else None
        return self._current_page

    async def list_tabs(self) -> list[dict[str, Any]]:
        await self.enforce_tab_policy()
        context = await self._get_context()
        tabs = []
        current = await self.get_page()
        for index, page in enumerate(context.pages):
            normalized_url = self.normalize_url(page.url)
            tabs.append(
                {
                    "index": index,
                    "url": page.url,
                    "normalized_url": normalized_url,
                    "title": await page.title(),
                    "active": page == current,
                    "kind": self._classify_tab(page.url, await page.title()),
                }
            )
        return tabs

    async def find_tab_by_url(self, url: str) -> Page | None:
        desired = self.normalize_url(url)
        if not desired:
            return None
        context = await self._get_context()
        for page in context.pages:
            if page.is_closed():
                continue
            if self.normalize_url(page.url) == desired:
                return page
        return None

    async def focus_or_create_tab(self, url: str) -> tuple[Page, bool]:
        existing = await self.find_tab_by_url(url)
        if existing is not None:
            await existing.bring_to_front()
            self._current_page = existing
            return existing, True
        page = await self.create_tab(url)
        return page, False

    async def switch_to_page(self, page: Page) -> Page:
        self._current_page = page
        await page.bring_to_front()
        return page

    async def enforce_tab_policy(self) -> None:
        context = await self._get_context()
        pages = [page for page in context.pages if not page.is_closed()]
        if not pages:
            return

        active = await self.get_page()
        keepers: dict[str, Page] = {}
        for page in list(pages):
            normalized_url = self.normalize_url(page.url)
            if not normalized_url:
                continue

            existing = keepers.get(normalized_url)
            if existing is None:
                keepers[normalized_url] = page
                continue

            keeper = active if active in {existing, page} else existing
            duplicate = page if keeper is existing else existing
            if duplicate == self._current_page:
                self._current_page = keeper
            if not duplicate.is_closed():
                await duplicate.close()
            keepers[normalized_url] = keeper

        pages = [page for page in context.pages if not page.is_closed()]
        max_tabs = max(1, settings.browser_max_tabs)
        if len(pages) <= max_tabs:
            return

        closable = [page for page in pages if page != self._current_page]
        closable.sort(key=lambda page: 1 if self._classify_tab(page.url, "") == "search" else 0)
        while len(pages) > max_tabs and closable:
            candidate = closable.pop(0)
            if candidate.is_closed():
                continue
            await candidate.close()
            pages = [page for page in context.pages if not page.is_closed()]

    async def capture_screenshot_base64(self, *, full_page: bool = False) -> str:
        page = await self.get_page()
        image = await page.screenshot(type="jpeg", quality=65, full_page=full_page)
        return base64.b64encode(image).decode("utf-8")

    async def get_dom_snapshot(self) -> dict[str, Any]:
        page = await self.get_page()
        snapshot = None
        last_error: Exception | None = None
        for _ in range(3):
            try:
                snapshot = await page.evaluate(
                    """
                    () => {
                      const simplify = (text) => (text || "").replace(/\\s+/g, " ").trim().slice(0, 160);
                      const selectors = [
                        "a",
                        "button",
                        "input",
                        "textarea",
                        "select",
                        "[role='button']",
                        "[role='link']",
                        "[contenteditable='true']",
                        "[tabindex]:not([tabindex='-1'])"
                      ];
                      const nodes = [...document.querySelectorAll(selectors.join(","))];
                      const elements = [];
                      nodes.forEach((node, index) => {
                        const rect = node.getBoundingClientRect();
                        const style = window.getComputedStyle(node);
                        if (!rect.width || !rect.height || style.visibility === "hidden" || style.display === "none") {
                          return;
                        }
                        if (rect.bottom < 0 || rect.right < 0) {
                          return;
                        }
                        elements.push({
                          id: index,
                          tag: node.tagName.toLowerCase(),
                          type: node.getAttribute("type") || "",
                          text: simplify(node.innerText || node.textContent || node.value || node.placeholder || node.getAttribute("aria-label")),
                          name: node.getAttribute("name") || "",
                          placeholder: node.getAttribute("placeholder") || "",
                          href: node.getAttribute("href") || "",
                          role: node.getAttribute("role") || "",
                          disabled: !!node.disabled,
                          x: Math.round(rect.left + rect.width / 2),
                          y: Math.round(rect.top + rect.height / 2),
                          width: Math.round(rect.width),
                          height: Math.round(rect.height),
                        });
                      });

                      const headings = [...document.querySelectorAll("h1,h2,h3")]
                        .map((node) => simplify(node.textContent))
                        .filter(Boolean)
                        .slice(0, 12);

                      const bodyText = simplify(document.body?.innerText || "");

                      const canonicalResultUrl = (href) => {
                        try {
                          const absolute = new URL(href, window.location.href);
                          const host = absolute.hostname.toLowerCase();
                          if (host.includes("duckduckgo.com")) {
                            const uddg = absolute.searchParams.get("uddg");
                            if (uddg) {
                              return decodeURIComponent(uddg);
                            }
                          }
                          if (host.includes("bing.com")) {
                            const redirected = absolute.searchParams.get("u");
                            if (redirected) {
                              return decodeURIComponent(redirected);
                            }
                          }
                          return absolute.href;
                        } catch (_error) {
                          return href || "";
                        }
                      };

                      const searchResults = Array.from(
                        document.querySelectorAll(
                          ".result__title a[href], .result__a[href], .links_main a[href], a.result-link[href], a[href][rel='nofollow']"
                        )
                      )
                        .map((node, index) => {
                          const href = node.getAttribute("href") || "";
                          const canonical = canonicalResultUrl(href);
                          const card =
                            node.closest(".result") ||
                            node.closest(".result-link") ||
                            node.closest("tr") ||
                            node.closest("td") ||
                            node.parentElement;
                          const snippet = simplify(card?.innerText || card?.textContent || "");
                          return {
                            id: `result-${index}`,
                            text: simplify(node.innerText || node.textContent || ""),
                            href,
                            canonical_url: canonical,
                            snippet: snippet.slice(0, 320),
                          };
                        })
                        .filter((item) =>
                          item.text &&
                          item.canonical_url &&
                          !item.canonical_url.startsWith("javascript:") &&
                          !item.canonical_url.startsWith("#")
                        )
                        .slice(0, 12);

                      return {
                        url: window.location.href,
                        title: document.title,
                        viewport: {
                          width: window.innerWidth,
                          height: window.innerHeight,
                        },
                        headings,
                        elements,
                        search_results: searchResults,
                        text_excerpt: bodyText.slice(0, 2000),
                        page_height: document.documentElement.scrollHeight || document.body.scrollHeight || 0,
                        scroll_y: window.scrollY || 0,
                      };
                    }
                    """
                )
                break
            except Exception as exc:
                last_error = exc
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=8000)
                except Exception:
                    await asyncio.sleep(0.6)
                page = await self.get_page()

        if snapshot is None:
            logger.debug("Falling back to minimal DOM snapshot after evaluate failure", exc_info=last_error)
            current_url = page.url
            try:
                title = await page.title()
            except Exception:
                title = ""
            body_text = ""
            try:
                body_text = await page.locator("body").inner_text(timeout=3000)
            except Exception:
                body_text = ""
            snapshot = {
                "url": current_url,
                "title": title,
                "viewport": {"width": 0, "height": 0},
                "headings": [],
                "elements": [],
                "search_results": [],
                "text_excerpt": body_text[:2000],
                "page_height": 0,
                "scroll_y": 0,
            }
        snapshot["blockers"] = self._find_blockers(
            snapshot.get("title", ""),
            snapshot.get("text_excerpt", ""),
            snapshot.get("url", ""),
        )
        return snapshot

    async def current_url(self) -> str:
        page = await self.get_page()
        return page.url

    async def current_title(self) -> str:
        page = await self.get_page()
        return await page.title()

    async def persist_storage_state(self) -> None:
        if self._context is None:
            return
        try:
            await self._context.storage_state(path=str(self.storage_state_path))
        except Exception:
            logger.debug("Could not persist storage state for browser session %s", self.session_id, exc_info=True)

    async def close(self) -> None:
        try:
            if self._context is not None:
                await self.persist_storage_state()
                try:
                    await self._context.close()
                except Exception:
                    logger.debug("Could not close browser context for session %s cleanly", self.session_id, exc_info=True)
            if self._browser is not None:
                try:
                    await self._browser.close()
                except Exception:
                    logger.debug("Could not close browser for session %s cleanly", self.session_id, exc_info=True)
            if self._playwright is not None:
                try:
                    await self._playwright.stop()
                except Exception:
                    logger.debug("Could not stop Playwright for session %s cleanly", self.session_id, exc_info=True)
        finally:
            self._context = None
            self._browser = None
            self._playwright = None
            self._current_page = None

    async def detect_blockers(self) -> list[str]:
        page = await self.get_page()
        url = page.url
        title = await page.title()
        body = ""
        try:
            body = await page.locator("body").inner_text(timeout=5000)
        except Exception:
            body = ""
        return self._find_blockers(title, body, url)

    def download_dir(self) -> str:
        return str(self._downloads_dir)

    async def _get_context(self) -> BrowserContext:
        await self.start()
        assert self._context is not None
        return self._context

    def _wire_context(self, context: BrowserContext) -> None:
        if self._context_wired:
            return
        self._context_wired = True

        def _on_new_page(page: Page) -> None:
            async def _prepare() -> None:
                try:
                    await self._apply_stealth(page)
                    self._wire_page(page)
                    self._current_page = page
                    await self.enforce_tab_policy()
                except Exception as exc:
                    logger.warning("Could not prepare new page in browser session %s: %s", self.session_id, exc)

            asyncio.create_task(_prepare())

        context.on("page", _on_new_page)

    def _wire_page(self, page: Page) -> None:
        if getattr(page, "_autonomous_browser_wired", False):
            return
        setattr(page, "_autonomous_browser_wired", True)

        async def _accept_dialog(dialog) -> None:
            logger.info("Auto-accepting dialog: %s", dialog.message)
            await dialog.accept()

        def _on_dialog(dialog) -> None:
            asyncio.create_task(_accept_dialog(dialog))

        page.on("dialog", _on_dialog)

        def _on_page_error(exc: Exception) -> None:
            message = str(exc)
            if "sj_evt is not defined" in message or "Cannot redefine property: offsetHeight" in message:
                return
            logger.warning("Page error in browser session %s: %s", self.session_id, exc)

        page.on("pageerror", _on_page_error)

    async def _apply_stealth(self, page: Page) -> None:
        if getattr(page, "_autonomous_browser_stealth_applied", False):
            return
        await self._stealth.apply_stealth_async(page)
        setattr(page, "_autonomous_browser_stealth_applied", True)

    @staticmethod
    def _find_blockers(title: str, body_text: str, url: str = "") -> list[str]:
        haystack = f"{title}\n{body_text}\n{url}".lower()
        blockers = [pattern for pattern in BLOCK_PATTERNS if pattern in haystack]
        if "duckduckgo.com/static-pages/418" in haystack:
            blockers.append("error getting results")
        if "google.com/sorry" in haystack:
            blockers.append("unusual traffic")
        if "/captcha/" in haystack or "recaptcha" in haystack:
            blockers.append("captcha")
        return list(dict.fromkeys(blockers))

    @classmethod
    def normalize_url(cls, url: str | None) -> str:
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
        query = urlencode(filtered_query, doseq=True)
        return urlunsplit((split.scheme.lower(), netloc, path, query, ""))

    @staticmethod
    def _classify_tab(url: str, title: str) -> str:
        url_lower = (url or "").lower()
        title_lower = (title or "").lower()
        if any(engine in url_lower for engine in ("google.", "bing.com", "duckduckgo.com")):
            return "search"
        if any(token in title_lower or token in url_lower for token in ("docs", "documentation", "guide", "help")):
            return "documentation"
        if any(token in title_lower for token in ("summary", "result", "report")):
            return "final_result"
        return "source"
