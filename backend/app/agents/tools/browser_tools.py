"""Browser tools — Playwright-based web automation tools.

Each tool wraps a Playwright action and returns a structured ToolResult.
The BrowserSession manages the browser lifecycle.
"""
from __future__ import annotations

import base64
import logging
from typing import Any

from app.agents.tools.registry import ToolDefinition, ToolRegistry, ToolResult

logger = logging.getLogger(__name__)

# Maximum characters of page HTML sent to the AI (keeps token usage low)
_MAX_HTML_CHARS = 8_000
# Maximum characters of extracted text
_MAX_TEXT_CHARS = 4_000


class BrowserSession:
    """Manages a single Playwright browser session.

    Lifecycle: create → use tools → close.
    The session is NOT thread-safe — use one per agent run.
    """

    def __init__(self) -> None:
        self._browser = None
        self._page = None
        self._playwright = None
        self._current_url: str = ""

    async def start(self, headless: bool = True) -> None:
        """Launch the browser. Raises ImportError if playwright is not installed."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "playwright is not installed. "
                "Run: pip install playwright && playwright install chromium"
            )
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        self._page = await self._browser.new_page()
        await self._page.set_extra_http_headers({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        })
        logger.info("Browser session started (headless=%s)", headless)

    async def close(self) -> None:
        """Close the browser and release resources."""
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as exc:
            logger.warning("Error closing browser: %s", exc)
        finally:
            self._browser = None
            self._page = None
            self._playwright = None

    @property
    def page(self):
        if self._page is None:
            raise RuntimeError("Browser session not started. Call start() first.")
        return self._page

    # ── Tool implementations ──────────────────────────────────────────────────

    async def open_url(self, url: str, timeout: int = 15_000) -> ToolResult:
        """Navigate to a URL."""
        try:
            await self.page.goto(url, timeout=timeout, wait_until="domcontentloaded")
            self._current_url = self.page.url
            title = await self.page.title()
            return ToolResult(
                success=True,
                tool_name="open_url",
                data={"url": self._current_url, "title": title},
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"Navigation failed: {exc}", tool_name="open_url")

    async def click(self, selector: str, timeout: int = 5_000) -> ToolResult:
        """Click an element by CSS selector."""
        try:
            await self.page.click(selector, timeout=timeout)
            return ToolResult(success=True, tool_name="click", data={"selector": selector})
        except Exception as exc:
            # Try text-based fallback
            try:
                await self.page.get_by_text(selector).first.click(timeout=timeout)
                return ToolResult(success=True, tool_name="click", data={"selector": selector, "method": "text"})
            except Exception:
                return ToolResult(success=False, error=f"Click failed: {exc}", tool_name="click")

    async def type_text(self, selector: str, text: str, timeout: int = 5_000) -> ToolResult:
        """Type text into an input element."""
        try:
            await self.page.fill(selector, text, timeout=timeout)
            return ToolResult(success=True, tool_name="type_text", data={"selector": selector})
        except Exception as exc:
            return ToolResult(success=False, error=f"Type failed: {exc}", tool_name="type_text")

    async def scroll(self, direction: str = "down", amount: int = 500) -> ToolResult:
        """Scroll the page."""
        try:
            dy = amount if direction == "down" else -amount
            await self.page.evaluate(f"window.scrollBy(0, {dy})")
            return ToolResult(success=True, tool_name="scroll", data={"direction": direction, "amount": amount})
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), tool_name="scroll")

    async def extract_text(self, selector: str = "body") -> ToolResult:
        """Extract visible text from an element."""
        try:
            element = await self.page.query_selector(selector)
            if not element:
                return ToolResult(success=False, error=f"Selector not found: {selector}", tool_name="extract_text")
            text = await element.inner_text()
            truncated = text[:_MAX_TEXT_CHARS]
            return ToolResult(
                success=True,
                tool_name="extract_text",
                data={"text": truncated, "truncated": len(text) > _MAX_TEXT_CHARS},
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), tool_name="extract_text")

    async def get_page_content(self) -> ToolResult:
        """Get trimmed page HTML for AI analysis."""
        try:
            html = await self.page.content()
            # Strip scripts and styles to reduce token usage
            import re
            html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
            # Collapse whitespace
            html = re.sub(r"\s+", " ", html).strip()
            truncated = html[:_MAX_HTML_CHARS]
            return ToolResult(
                success=True,
                tool_name="get_page_content",
                data={
                    "html": truncated,
                    "url": self._current_url,
                    "truncated": len(html) > _MAX_HTML_CHARS,
                    "char_count": len(html),
                },
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), tool_name="get_page_content")

    async def take_screenshot(self) -> ToolResult:
        """Take a screenshot and return it as base64."""
        try:
            screenshot_bytes = await self.page.screenshot(type="jpeg", quality=60)
            b64 = base64.b64encode(screenshot_bytes).decode()
            return ToolResult(
                success=True,
                tool_name="take_screenshot",
                data={"base64": b64, "format": "jpeg"},
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc), tool_name="take_screenshot")

    async def search_google(self, query: str) -> ToolResult:
        """Open Google and search for a query."""
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        result = await self.open_url(url)
        if not result.success:
            # Fallback to DuckDuckGo
            url = f"https://duckduckgo.com/?q={query.replace(' ', '+')}"
            result = await self.open_url(url)
        return result


# ── Tool handler wrappers (for ToolRegistry) ──────────────────────────────────

def _make_browser_handler(method_name: str):
    """Create a ToolRegistry-compatible handler that delegates to a BrowserSession method."""
    async def handler(params: dict, session: BrowserSession | None = None, **_) -> ToolResult:
        if session is None:
            return ToolResult(
                success=False,
                error="No browser session provided. Start a BrowserAgent run first.",
                tool_name=method_name,
            )
        method = getattr(session, method_name)
        return await method(**params)
    handler.__name__ = method_name
    return handler


def register_browser_tools() -> None:
    """Register all browser tools into the global ToolRegistry (idempotent)."""
    registry = ToolRegistry.get()
    if not registry.register_category("browser"):
        return  # Already registered

    registry.register(ToolDefinition(
        name="open_url",
        description="Navigate the browser to a URL",
        category="browser",
        params_schema={"url": "string (https:// required)"},
        handler=_make_browser_handler("open_url"),
    ))
    registry.register(ToolDefinition(
        name="click",
        description="Click an element by CSS selector or visible text",
        category="browser",
        params_schema={"selector": "string (CSS selector or text)"},
        handler=_make_browser_handler("click"),
    ))
    registry.register(ToolDefinition(
        name="type_text",
        description="Type text into an input field",
        category="browser",
        params_schema={"selector": "string", "text": "string"},
        handler=_make_browser_handler("type_text"),
    ))
    registry.register(ToolDefinition(
        name="scroll",
        description="Scroll the page up or down",
        category="browser",
        params_schema={"direction": "up|down", "amount": "integer (pixels, default 500)"},
        handler=_make_browser_handler("scroll"),
    ))
    registry.register(ToolDefinition(
        name="extract_text",
        description="Extract visible text from a page element",
        category="browser",
        params_schema={"selector": "string (CSS selector, default 'body')"},
        handler=_make_browser_handler("extract_text"),
    ))
    registry.register(ToolDefinition(
        name="get_page_content",
        description="Get trimmed page HTML for AI analysis",
        category="browser",
        params_schema={},
        handler=_make_browser_handler("get_page_content"),
    ))
    registry.register(ToolDefinition(
        name="take_screenshot",
        description="Take a screenshot of the current page",
        category="browser",
        params_schema={},
        handler=_make_browser_handler("take_screenshot"),
    ))
    registry.register(ToolDefinition(
        name="search_google",
        description="Search Google (or DuckDuckGo fallback) for a query",
        category="browser",
        params_schema={"query": "string"},
        handler=_make_browser_handler("search_google"),
    ))
