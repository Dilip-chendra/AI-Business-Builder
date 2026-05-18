from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncGenerator

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.services.browser_agent.session_manager import SessionManager


class PlatformPublishService:
    """Deterministic platform posting flows for marketing publish actions."""

    def __init__(self, session_manager: SessionManager) -> None:
        self.session_manager = session_manager

    async def publish(
        self,
        *,
        platform: str,
        text: str,
        image_hint: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        if platform == "linkedin":
            async for event in self._publish_linkedin(text=text, image_hint=image_hint):
                yield event
            return
        if platform == "instagram":
            async for event in self._publish_instagram(text=text, image_hint=image_hint):
                yield event
            return
        yield {
            "type": "error",
            "message": f"Direct browser publishing is not implemented for {platform} yet.",
        }

    async def _publish_linkedin(self, *, text: str, image_hint: str | None) -> AsyncGenerator[dict[str, Any], None]:
        page = await self.session_manager.get_page()
        yield {"type": "status", "status": "running", "message": "Opening LinkedIn feed.", "phase": "platform_navigation"}
        await self._safe_goto(page, "https://www.linkedin.com/feed/")
        await self._wait(1.4)

        start_post = await self._first_visible(
            page,
            [
                "button:has-text('Start a post')",
                "button[aria-label*='Start a post']",
                "button[aria-label*='Create a post']",
                "div[role='button']:has-text('Start a post')",
                "button.share-box-feed-entry__trigger",
                "div.share-box-feed-entry__trigger",
            ],
            timeout_ms=20000,
        )
        if start_post is None:
            raise RuntimeError("LinkedIn feed loaded, but the post composer trigger was not visible.")
        await start_post.click()
        yield {"type": "step", "action": "click", "result": "Opened the LinkedIn post composer."}
        await self._wait(1.6)

        editor = await self._first_visible(
            page,
            [
                "div[role='textbox']",
                "div.ql-editor",
                "div[data-placeholder*='What do you want to talk about']",
            ],
            timeout_ms=20000,
        )
        if editor is None:
            raise RuntimeError("LinkedIn composer opened, but the text editor could not be located.")
        await editor.click(timeout=10000)
        await self._replace_rich_text(page, editor, text)
        yield {"type": "step", "action": "type", "result": "Inserted the generated LinkedIn post copy."}

        uploaded = await self._maybe_upload_media(page, image_hint=image_hint)
        if uploaded:
            yield {"type": "step", "action": "upload_file", "result": "Attached media to the LinkedIn post."}

        publish_button = await self._first_visible(
            page,
            [
                "button:has-text('Post')",
                "button[aria-label='Post']",
                "button.share-actions__primary-action",
            ],
            timeout_ms=20000,
        )
        if publish_button is None:
            raise RuntimeError("LinkedIn compose flow is ready, but the final Post button was not visible.")
        await publish_button.click()
        yield {"type": "step", "action": "click", "result": "Clicked the final LinkedIn Post button."}
        await self._wait(4.0)
        await self.session_manager.persist_storage_state()

        yield {
            "type": "result",
            "text": "The LinkedIn publishing flow completed in the browser.",
            "url": page.url,
        }
        yield {"type": "done", "status": "done"}

    async def _publish_instagram(self, *, text: str, image_hint: str | None) -> AsyncGenerator[dict[str, Any], None]:
        page = await self.session_manager.get_page()
        yield {"type": "status", "status": "running", "message": "Opening Instagram home.", "phase": "platform_navigation"}
        await self._safe_goto(page, "https://www.instagram.com/")
        await self._wait()

        create_button = await self._first_visible(
            page,
            [
                "svg[aria-label='New post']",
                "a[href='/create/select/']",
                "button:has(svg[aria-label='New post'])",
            ],
            timeout_ms=20000,
        )
        if create_button is None:
            raise RuntimeError("Instagram is open, but the new post control is not visible.")
        await create_button.click()
        yield {"type": "step", "action": "click", "result": "Opened the Instagram create flow."}
        await self._wait(1.2)

        uploaded = await self._maybe_upload_media(page, image_hint=image_hint)
        if not uploaded:
            raise RuntimeError("Instagram posting requires an image or video file that the browser can upload.")
        yield {"type": "step", "action": "upload_file", "result": "Uploaded media to Instagram."}

        caption = await self._first_visible(
            page,
            [
                "textarea[aria-label='Write a caption...']",
                "div[role='textbox']",
                "textarea",
            ],
            timeout_ms=30000,
        )
        if caption is None:
            raise RuntimeError("Instagram media upload completed, but the caption field could not be located.")
        await caption.click()
        try:
            await caption.fill("")
            await caption.type(text, delay=18)
        except Exception:
            await self._replace_rich_text(page, caption, text)
        yield {"type": "step", "action": "type", "result": "Inserted the Instagram caption."}

        share_button = await self._first_visible(
            page,
            [
                "button:has-text('Share')",
                "button:has-text('Post')",
            ],
            timeout_ms=30000,
        )
        if share_button is None:
            raise RuntimeError("Instagram caption is ready, but the final Share button was not visible.")
        await share_button.click()
        yield {"type": "step", "action": "click", "result": "Clicked the final Instagram Share button."}
        await self._wait(4.0)
        await self.session_manager.persist_storage_state()

        yield {
            "type": "result",
            "text": "The Instagram publishing flow completed in the browser.",
            "url": page.url,
        }
        yield {"type": "done", "status": "done"}

    async def _maybe_upload_media(self, page: Page, *, image_hint: str | None) -> bool:
        local_path = self._local_media_path(image_hint)
        if not local_path:
            return False

        selectors = [
            "input[type='file']",
            "label[for] input[type='file']",
        ]
        locator = await self._first_visible(page, selectors, timeout_ms=10000, allow_hidden=True)
        if locator is None:
            return False
        try:
            await locator.set_input_files(str(local_path))
            await self._wait(1.8)
            return True
        except PlaywrightTimeoutError:
            return False

    async def _replace_rich_text(self, page: Page, locator, text: str) -> None:
        await locator.focus()
        try:
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
        except Exception:
            pass
        await page.keyboard.type(text, delay=16)

    @staticmethod
    def _local_media_path(image_hint: str | None) -> Path | None:
        if not image_hint:
            return None
        candidate = str(image_hint).strip()
        if not candidate or candidate.startswith("data:") or candidate.startswith("http"):
            return None
        path = Path(candidate)
        if not path.is_absolute():
            path = (Path.cwd() / candidate).resolve()
        return path if path.exists() else None

    async def _first_visible(
        self,
        page: Page,
        selectors: list[str],
        *,
        timeout_ms: int,
        allow_hidden: bool = False,
    ):
        deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000)
        while asyncio.get_running_loop().time() < deadline:
            for selector in selectors:
                locator = page.locator(selector).first
                try:
                    count = await locator.count()
                    if count < 1:
                        continue
                    if allow_hidden:
                        return locator
                    if await locator.is_visible():
                        return locator
                except Exception:
                    continue
            await self._wait(0.35)
        return None

    async def _safe_goto(self, page: Page, url: str) -> None:
        if url in page.url:
            return
        attempts = [
            {"wait_until": "domcontentloaded", "timeout": 45000},
            {"wait_until": "load", "timeout": 30000},
            {"wait_until": "commit", "timeout": 15000},
        ]
        last_error: Exception | None = None
        for attempt in attempts:
            try:
                await page.goto(url, **attempt)
                return
            except Exception as exc:
                last_error = exc
                current = page.url or ""
                if current.startswith(url) or current.startswith(url.rstrip("/") + "/"):
                    return
        if last_error:
            raise last_error

    @staticmethod
    async def _wait(seconds: float = 1.0) -> None:
        await asyncio.sleep(seconds)
