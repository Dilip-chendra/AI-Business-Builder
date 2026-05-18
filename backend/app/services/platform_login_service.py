from __future__ import annotations

import asyncio
import logging
from typing import Any

from playwright.async_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from app.services.browser_agent.session_manager import SessionManager

logger = logging.getLogger(__name__)


class PlatformLoginService:
    """Restores authenticated browser sessions for platform publishing flows."""

    def __init__(self, session_manager: SessionManager) -> None:
        self.session_manager = session_manager

    async def ensure_session(self, *, platform: str, credentials: dict[str, Any] | None) -> dict[str, Any]:
        if not credentials:
            return {
                "status": "skipped",
                "message": f"No saved {platform} browser credentials were found. The operator will rely on existing cookies or ask for manual sign-in.",
            }

        if platform == "linkedin":
            return await self._ensure_linkedin_session(credentials)
        if platform == "instagram":
            return await self._ensure_instagram_session(credentials)
        if platform == "facebook":
            return await self._ensure_facebook_session(credentials)
        if platform == "wordpress":
            return {
                "status": "skipped",
                "message": "WordPress browser login is platform-specific. Existing session cookies will be reused when available.",
            }
        return {
            "status": "skipped",
            "message": f"No dedicated login bootstrap exists for {platform} yet. Existing browser session state will be reused when possible.",
        }

    async def _ensure_linkedin_session(self, credentials: dict[str, Any]) -> dict[str, Any]:
        page = await self.session_manager.get_page()
        login_identifier = self._best_login_identifier(credentials)
        password = credentials.get("password")
        if not login_identifier or not password:
            return {"status": "failed", "message": "Saved LinkedIn credentials are incomplete."}

        try:
            for candidate in (
                "https://www.linkedin.com/feed/",
                "https://www.linkedin.com/",
            ):
                try:
                    await self._safe_goto(page, candidate)
                    await self._pause(1.0)
                    if await self._linkedin_logged_in():
                        await self.session_manager.persist_storage_state()
                        return {"status": "connected", "message": "LinkedIn session is already active."}
                except Exception:
                    continue

            await self._safe_goto(page, "https://www.linkedin.com/login")
            await self._dismiss_cookie_dialog(page, ["Accept cookies", "Accept", "Allow all", "Got it"])
            username_locator = await self._find_first_locator(
                page,
                ["#username", "input[name='session_key']", "input[aria-label='Email or phone']", "input[type='email']", "input[type='text']"],
                timeout_ms=20000,
            )
            password_locator = await self._find_first_locator(
                page,
                ["#password", "input[name='session_password']", "input[aria-label='Password']", "input[type='password']"],
                timeout_ms=20000,
            )
            submit_locator = await self._find_first_locator(
                page,
                [
                    "form button[type='submit']",
                    "button[type='submit']",
                    "button[aria-label='Sign in'][type='submit']",
                    "button.btn__primary--large",
                    "button:has-text('Continue')",
                ],
                timeout_ms=12000,
            )

            await username_locator.fill(str(login_identifier))
            await password_locator.fill(str(password))
            await self._pause()
            await submit_locator.click(timeout=12000)
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            await self._pause(2.2)
        except PlaywrightTimeoutError:
            logger.warning("Timed out during LinkedIn login bootstrap for session %s", self.session_manager.session_id)
            return {"status": "failed", "message": "LinkedIn login timed out before the session could be restored."}
        except Exception:
            logger.exception("LinkedIn login bootstrap failed for session %s", self.session_manager.session_id)
            return {"status": "failed", "message": "LinkedIn could not complete the automated login flow."}

        if await self._wait_for_authenticated_state(self._linkedin_logged_in, timeout_seconds=24):
            await self.session_manager.persist_storage_state()
            return {"status": "connected", "message": "LinkedIn session restored successfully."}
        if await page.locator("input[name='pin'], input[autocomplete='one-time-code'], input[placeholder*='code']").count():
            return {"status": "failed", "message": "LinkedIn is asking for a verification code before the session can continue."}
        if await page.locator("#error-for-username, #error-for-password, [role='alert']").count():
            return {"status": "failed", "message": "LinkedIn rejected the saved login details or asked for extra review."}
        return {"status": "failed", "message": "LinkedIn needs additional verification before the session can be restored."}

    async def _ensure_instagram_session(self, credentials: dict[str, Any]) -> dict[str, Any]:
        page = await self.session_manager.get_page()
        await self._safe_goto(page, "https://www.instagram.com/")
        await self._pause()

        if await self._instagram_logged_in():
            await self.session_manager.persist_storage_state()
            return {"status": "connected", "message": "Instagram session is already active."}

        login_identifier = self._best_login_identifier(credentials)
        password = credentials.get("password")
        if not login_identifier or not password:
            return {"status": "failed", "message": "Saved Instagram credentials are incomplete."}

        try:
            await self._safe_goto(page, "https://www.instagram.com/accounts/login/")
            await self._dismiss_cookie_dialog(page, ["Allow all cookies", "Allow all", "Accept All", "Accept"])
            username_locator = await self._find_first_locator(
                page,
                ["input[name='username']", "input[aria-label='Phone number, username, or email']", "input[type='text']"],
                timeout_ms=20000,
            )
            password_locator = await self._find_first_locator(
                page,
                ["input[name='password']", "input[aria-label='Password']", "input[type='password']"],
                timeout_ms=20000,
            )
            submit_locator = await self._find_first_locator(
                page,
                ["button[type='submit']", "button:has-text('Log in')"],
                timeout_ms=12000,
            )
            await username_locator.fill(str(login_identifier))
            await password_locator.fill(str(password))
            await self._pause()
            await submit_locator.click(timeout=12000)
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            await self._pause(2.0)
            await self._dismiss_instagram_save_prompts()
        except PlaywrightTimeoutError:
            logger.warning("Timed out during Instagram login bootstrap for session %s", self.session_manager.session_id)
            return {"status": "failed", "message": "Instagram login timed out before the session could be restored."}

        if await self._wait_for_authenticated_state(self._instagram_logged_in, timeout_seconds=24):
            await self.session_manager.persist_storage_state()
            return {"status": "connected", "message": "Instagram session restored successfully."}
        if await page.locator("input[name='verificationCode'], input[autocomplete='one-time-code']").count():
            return {"status": "failed", "message": "Instagram is asking for a verification code before the session can continue."}
        return {"status": "failed", "message": "Instagram needs additional verification before the session can be restored."}

    async def _ensure_facebook_session(self, credentials: dict[str, Any]) -> dict[str, Any]:
        page = await self.session_manager.get_page()
        await self._safe_goto(page, "https://www.facebook.com/")
        await self._pause()

        if await self._facebook_logged_in():
            await self.session_manager.persist_storage_state()
            return {"status": "connected", "message": "Facebook session is already active."}

        login_identifier = self._best_login_identifier(credentials)
        password = credentials.get("password")
        if not login_identifier or not password:
            return {"status": "failed", "message": "Saved Facebook credentials are incomplete."}

        try:
            username_locator = await self._find_first_locator(
                page,
                ["#email", "input[name='email']", "input[aria-label='Email address or phone number']"],
                timeout_ms=15000,
            )
            password_locator = await self._find_first_locator(
                page,
                ["#pass", "input[name='pass']", "input[aria-label='Password']"],
                timeout_ms=15000,
            )
            submit_locator = await self._find_first_locator(
                page,
                ["button[name='login']", "button[type='submit']"],
                timeout_ms=12000,
            )
            await username_locator.fill(str(login_identifier))
            await password_locator.fill(str(password))
            await self._pause()
            await submit_locator.click(timeout=12000)
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
            await self._pause(1.8)
        except PlaywrightTimeoutError:
            logger.warning("Timed out during Facebook login bootstrap for session %s", self.session_manager.session_id)
            return {"status": "failed", "message": "Facebook login timed out before the session could be restored."}

        if await self._facebook_logged_in():
            await self.session_manager.persist_storage_state()
            return {"status": "connected", "message": "Facebook session restored successfully."}
        return {"status": "failed", "message": "Facebook needs additional verification before the session can be restored."}

    async def _linkedin_logged_in(self) -> bool:
        page = await self.session_manager.get_page()
        if "linkedin.com" in page.url and "/login" not in page.url and "/checkpoint/" not in page.url:
            selectors = [
                "button:has-text('Start a post')",
                "button[aria-label*='Start a post']",
                "div[role='button']:has-text('Start a post')",
                "a[href*='/feed/']",
                "input[placeholder*='Search']",
                "nav.global-nav",
                "[aria-label='Home']",
            ]
            for selector in selectors:
                try:
                    locator = page.locator(selector).first
                    if await locator.count():
                        return True
                except Exception:
                    continue
        return False

    async def _instagram_logged_in(self) -> bool:
        page = await self.session_manager.get_page()
        if "/accounts/login" not in page.url and await page.locator("svg[aria-label='Home'], a[href='/'], input[aria-label='Search']").count():
            return True
        return False

    async def _facebook_logged_in(self) -> bool:
        page = await self.session_manager.get_page()
        if "facebook.com" in page.url and await page.locator("[aria-label='Facebook'], [role='navigation']").count():
            return True
        return False

    async def _dismiss_instagram_save_prompts(self) -> None:
        page = await self.session_manager.get_page()
        for label in ["Not now", "Not Now"]:
            try:
                button = page.get_by_role("button", name=label).first
                if await button.count():
                    await button.click(timeout=5000)
                    await self._pause(0.8)
                    return
            except Exception:
                continue

    async def _dismiss_cookie_dialog(self, page: Page, labels: list[str]) -> None:
        for label in labels:
            try:
                button = page.get_by_role("button", name=label).first
                if await button.count() and await button.is_visible():
                    await button.click(timeout=4000)
                    await self._pause(0.7)
                    return
            except Exception:
                continue

    async def _wait_for_authenticated_state(self, detector, *, timeout_seconds: float) -> bool:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            try:
                if await detector():
                    return True
            except Exception:
                pass
            await self._pause(1.0)
        return False

    @staticmethod
    def _best_login_identifier(credentials: dict[str, Any]) -> str | None:
        email = str(credentials.get("email") or "").strip()
        phone = str(credentials.get("phone") or "").strip()
        if email and "*" not in email and "@" in email:
            return email
        digits = "".join(ch for ch in phone if ch.isdigit())
        if len(digits) >= 6:
            return phone
        if email and "*" not in email:
            return email
        return None

    async def _find_first_locator(self, page: Page, selectors: list[str], *, timeout_ms: int) -> Locator:
        deadline = asyncio.get_running_loop().time() + (timeout_ms / 1000)
        last_error: Exception | None = None
        while asyncio.get_running_loop().time() < deadline:
            for selector in selectors:
                try:
                    locator = page.locator(selector).first
                    if await locator.count():
                        return locator
                except Exception as exc:
                    last_error = exc
                    continue
            await self._pause(0.4)
        if last_error:
            raise PlaywrightTimeoutError(str(last_error))
        raise PlaywrightTimeoutError(f"Could not find any expected selector: {', '.join(selectors)}")

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
    async def _pause(seconds: float = 1.2) -> None:
        await asyncio.sleep(seconds)
