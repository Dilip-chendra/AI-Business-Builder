from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, AsyncGenerator

from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

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
        run_id: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        if platform == "linkedin":
            async for event in self._publish_linkedin(text=text, image_hint=image_hint, run_id=run_id):
                yield event
            return
        if platform == "instagram":
            async for event in self._publish_instagram(text=text, image_hint=image_hint, run_id=run_id):
                yield event
            return
        yield {
            "type": "error",
            "message": f"Direct browser publishing is not implemented for {platform} yet.",
        }

    async def _publish_linkedin(self, *, text: str, image_hint: str | None, run_id: str | None) -> AsyncGenerator[dict[str, Any], None]:
        page = await self.session_manager.get_page()
        yield {"type": "status", "status": "running", "message": "Opening LinkedIn feed.", "phase": "platform_navigation"}
        await self._safe_goto(page, "https://www.linkedin.com/feed/")
        await self._wait(1.4)
        if self._is_linkedin_login(page.url):
            yield {"type": "status", "status": "waiting_for_manual_login", "message": "LinkedIn needs login. Complete login in the live browser; this run will continue automatically after the feed is available.", "phase": "manual_login", "url": page.url}
            if not await self._wait_until(lambda: not self._is_linkedin_login(page.url), timeout_seconds=180):
                yield {
                    "type": "result",
                    "status": "needs_login",
                    "text": "LinkedIn is still showing login or security verification. No post was drafted or published. Complete login in the live browser, then run Browser Agent again.",
                    "url": page.url,
                }
                yield {"type": "done", "status": "needs_login"}
                return
            await self.session_manager.persist_storage_state()
            yield {"type": "status", "status": "checking_session", "message": "LinkedIn login detected. Continuing to find the post composer.", "phase": "checking_session", "url": page.url}

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
            yield {
                "type": "result",
                "status": "composer_not_found",
                "text": "LinkedIn feed loaded, but the post composer trigger was not visible. Nothing was published.",
                "url": page.url,
            }
            yield {"type": "done", "status": "composer_not_found"}
            return
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
            yield {
                "type": "result",
                "status": "composer_not_found",
                "text": "LinkedIn composer opened, but the editor was not reachable. Nothing was published.",
                "url": page.url,
            }
            yield {"type": "done", "status": "composer_not_found"}
            return
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
            yield {
                "type": "result",
                "status": "publish_unconfirmed",
                "text": "LinkedIn post copy was inserted, but the final Post button was not visible. Review the draft in the browser and publish manually when ready.",
                "url": page.url,
            }
            yield {"type": "done", "status": "publish_unconfirmed"}
            return
        await self.session_manager.persist_storage_state()

        async for event in self._await_final_publish(
            page,
            run_id=run_id,
            publish_button=publish_button,
            platform="LinkedIn",
            ready_text="LinkedIn post copy is inserted and the final Post button is visible. Review the browser draft, then confirm final publish.",
        ):
            yield event

    async def _publish_instagram(self, *, text: str, image_hint: str | None, run_id: str | None) -> AsyncGenerator[dict[str, Any], None]:
        page = await self.session_manager.get_page()
        yield {"type": "status", "status": "running", "message": "Opening Instagram home.", "phase": "platform_navigation"}
        await self._safe_goto(page, "https://www.instagram.com/")
        await self._wait()
        if self._is_instagram_login(page.url):
            yield {"type": "status", "status": "waiting_for_manual_login", "message": "Instagram needs login. Complete login in the live browser; this run will continue automatically after home is available.", "phase": "manual_login", "url": page.url}
            if not await self._wait_until(lambda: not self._is_instagram_login(page.url), timeout_seconds=180):
                yield {
                    "type": "result",
                    "status": "needs_login",
                    "text": "Instagram is still showing login or verification. No post was drafted or published. Complete login in the live browser, then run Browser Agent again.",
                    "url": page.url,
                }
                yield {"type": "done", "status": "needs_login"}
                return
            await self.session_manager.persist_storage_state()
            yield {"type": "status", "status": "checking_session", "message": "Instagram login detected. Continuing to create the post draft.", "phase": "checking_session", "url": page.url}

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
            yield {
                "type": "result",
                "status": "composer_not_found",
                "text": "Instagram opened, but the create-post control was not visible. Nothing was published.",
                "url": page.url,
            }
            yield {"type": "done", "status": "composer_not_found"}
            return
        await create_button.click()
        yield {"type": "step", "action": "click", "result": "Opened the Instagram create flow."}
        await self._wait(1.2)

        uploaded = await self._maybe_upload_media(page, image_hint=image_hint)
        if not uploaded:
            yield {
                "type": "result",
                "status": "image_required",
                "text": "Instagram posting needs an uploadable campaign image. Generate an image first, then run the Browser Agent again.",
                "url": page.url,
            }
            yield {"type": "done", "status": "image_required"}
            return
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
            yield {
                "type": "result",
                "status": "composer_not_found",
                "text": "Instagram media upload completed, but the caption field was not reachable. Nothing was published.",
                "url": page.url,
            }
            yield {"type": "done", "status": "composer_not_found"}
            return
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
            yield {
                "type": "result",
                "status": "publish_unconfirmed",
                "text": "Instagram caption is ready, but the final Share button was not visible. Review the draft and publish manually when ready.",
                "url": page.url,
            }
            yield {"type": "done", "status": "publish_unconfirmed"}
            return
        await self.session_manager.persist_storage_state()

        async for event in self._await_final_publish(
            page,
            run_id=run_id,
            publish_button=share_button,
            platform="Instagram",
            ready_text="Instagram media and caption are prepared and the final Share button is visible. Review the browser draft, then confirm final publish.",
        ):
            yield event

    async def _await_final_publish(
        self,
        page: Page,
        *,
        run_id: str | None,
        publish_button: Locator,
        platform: str,
        ready_text: str,
    ) -> AsyncGenerator[dict[str, Any], None]:
        from app.services.browser_agent.run_manager import browser_run_manager

        yield {
            "type": "status",
            "status": "awaiting_final_confirmation",
            "message": ready_text,
            "phase": "awaiting_final_confirmation",
            "run_id": run_id,
            "url": page.url,
        }
        if run_id:
            state = browser_run_manager.get(run_id)
            if state:
                state.status = "awaiting_final_confirmation"
                state.last_phase = "awaiting_final_confirmation"
                state.result_preview = ready_text

        waited = 0.0
        while run_id and waited < 300:
            state = browser_run_manager.get(run_id)
            if state and state.confirm_publish_requested:
                break
            await asyncio.sleep(0.5)
            waited += 0.5

        state = browser_run_manager.get(run_id) if run_id else None
        if not state or not state.confirm_publish_requested:
            yield {
                "type": "result",
                "status": "awaiting_user_approval",
                "text": f"{platform} draft is ready, but final publish was not confirmed. Nothing was posted.",
                "url": page.url,
                "run_id": run_id,
            }
            yield {"type": "done", "status": "awaiting_user_approval", "run_id": run_id}
            return

        try:
            await publish_button.click(timeout=15000)
            await self._wait(3.0)
        except Exception:
            yield {
                "type": "result",
                "status": "publish_unconfirmed",
                "text": f"{platform} final publish click failed. Review the browser draft manually; the campaign was not marked published.",
                "url": page.url,
                "run_id": run_id,
            }
            yield {"type": "done", "status": "publish_unconfirmed", "run_id": run_id}
            return

        still_visible = False
        try:
            still_visible = await publish_button.is_visible()
        except Exception:
            still_visible = False
        if still_visible:
            yield {
                "type": "result",
                "status": "publish_unconfirmed",
                "text": f"{platform} final publish was clicked, but the publish dialog still appears open. Verify the result in the browser.",
                "url": page.url,
                "run_id": run_id,
            }
            yield {"type": "done", "status": "publish_unconfirmed", "run_id": run_id}
            return

        yield {
            "type": "result",
            "status": "published",
            "text": f"{platform} final publish click completed and the composer closed.",
            "url": page.url,
            "run_id": run_id,
        }
        yield {"type": "done", "status": "published", "run_id": run_id}

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
    def _is_linkedin_login(url: str) -> bool:
        lower = (url or "").lower()
        return "linkedin.com/login" in lower or "linkedin.com/uas/login" in lower or "/checkpoint/" in lower

    @staticmethod
    def _is_instagram_login(url: str) -> bool:
        lower = (url or "").lower()
        return "instagram.com/accounts/login" in lower or "instagram.com/challenge" in lower

    @staticmethod
    async def _wait(seconds: float = 1.0) -> None:
        await asyncio.sleep(seconds)

    async def _wait_until(self, predicate, *, timeout_seconds: float) -> bool:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            try:
                result = await predicate() if asyncio.iscoroutinefunction(predicate) else predicate()
                if result:
                    return True
            except Exception:
                pass
            await self._wait(1.0)
        return False
