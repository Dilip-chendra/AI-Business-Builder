"""Publishing Service — real platform API calls for campaign publishing."""
from __future__ import annotations

import asyncio
import logging

import httpx

from app.models.oauth_token import OAuthToken

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_DELAYS = [1.0, 2.0, 4.0]


async def _post_with_retry(
    url: str,
    headers: dict,
    json_body: dict,
    timeout: float = 30.0,
) -> dict:
    """POST with exponential backoff retry on 429/5xx."""
    last_exc: Exception | None = None
    for attempt, delay in enumerate(_RETRY_DELAYS):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=json_body)
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < _MAX_RETRIES - 1:
                    logger.warning("Publish attempt %d failed (%d) — retrying in %.0fs", attempt + 1, resp.status_code, delay)
                    await asyncio.sleep(delay)
                    continue
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code not in (429, 500, 502, 503, 504):
                raise
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(delay)
        except Exception as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES - 1:
                await asyncio.sleep(delay)
    raise last_exc or RuntimeError("All retry attempts failed")


class PublishingService:
    """Publish campaign content to real platform APIs."""

    def __init__(self, oauth_svc: object) -> None:
        self._oauth = oauth_svc  # OAuthManagerService instance

    async def publish_linkedin_post(self, token: OAuthToken, content: dict) -> dict:
        """POST to LinkedIn Share API v2."""
        from app.services.oauth_manager_service import _decrypt
        from app.core.config import settings
        access_token = _decrypt(token.access_token_enc, settings.jwt_secret_key)
        author = f"urn:li:person:{token.account_id}" if token.account_id else "urn:li:person:me"
        body = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content.get("text", "")},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        result = await _post_with_retry(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json", "X-Restli-Protocol-Version": "2.0.0"},
            json_body=body,
        )
        logger.info("LinkedIn post published  id=%s", result.get("id"))
        return {"platform": "linkedin", "post_id": result.get("id"), "status": "published"}

    async def publish_twitter_post(self, token: OAuthToken, content: dict) -> dict:
        """POST to Twitter API v2."""
        from app.services.oauth_manager_service import _decrypt
        from app.core.config import settings
        access_token = _decrypt(token.access_token_enc, settings.jwt_secret_key)
        result = await _post_with_retry(
            "https://api.twitter.com/2/tweets",
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json_body={"text": content.get("text", "")[:280]},
        )
        tweet_id = result.get("data", {}).get("id")
        logger.info("Twitter post published  id=%s", tweet_id)
        return {"platform": "twitter", "post_id": tweet_id, "status": "published"}

    async def publish_facebook_post(self, token: OAuthToken, content: dict) -> dict:
        """POST to Facebook Graph API."""
        from app.services.oauth_manager_service import _decrypt
        from app.core.config import settings
        access_token = _decrypt(token.access_token_enc, settings.jwt_secret_key)
        page_id = token.account_id or "me"
        result = await _post_with_retry(
            f"https://graph.facebook.com/v18.0/{page_id}/feed",
            headers={"Content-Type": "application/json"},
            json_body={"message": content.get("text", ""), "access_token": access_token},
        )
        post_id = result.get("id")
        logger.info("Facebook post published  id=%s", post_id)
        return {"platform": "facebook", "post_id": post_id, "status": "published"}

    async def publish_instagram_post(self, token: OAuthToken, content: dict) -> dict:
        """POST to Instagram Graph API (two-step: create container then publish)."""
        from app.services.oauth_manager_service import _decrypt
        from app.core.config import settings
        access_token = _decrypt(token.access_token_enc, settings.jwt_secret_key)
        ig_user_id = token.account_id
        if not ig_user_id:
            raise ValueError("Instagram account_id (ig_user_id) is required")

        # Step 1: Create media container
        container_resp = await _post_with_retry(
            f"https://graph.facebook.com/v18.0/{ig_user_id}/media",
            headers={"Content-Type": "application/json"},
            json_body={
                "caption": content.get("text", ""),
                "image_url": content.get("image_url", ""),
                "access_token": access_token,
            },
        )
        container_id = container_resp.get("id")

        # Step 2: Publish the container
        publish_resp = await _post_with_retry(
            f"https://graph.facebook.com/v18.0/{ig_user_id}/media_publish",
            headers={"Content-Type": "application/json"},
            json_body={"creation_id": container_id, "access_token": access_token},
        )
        post_id = publish_resp.get("id")
        logger.info("Instagram post published  id=%s", post_id)
        return {"platform": "instagram", "post_id": post_id, "status": "published"}

    async def send_sendgrid_email(self, token: OAuthToken, campaign: dict, recipients: list[str]) -> dict:
        """Send email via SendGrid API."""
        from app.services.oauth_manager_service import _decrypt
        from app.core.config import settings
        api_key = _decrypt(token.access_token_enc, settings.jwt_secret_key)
        content_data = campaign.get("content", {})
        result = await _post_with_retry(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json_body={
                "personalizations": [{"to": [{"email": r} for r in recipients]}],
                "from": {"email": "noreply@autonomousbusiness.ai", "name": "AI Business Builder"},
                "subject": content_data.get("subject", "Message from us"),
                "content": [
                    {"type": "text/html", "value": content_data.get("html_body", content_data.get("body", ""))},
                    {"type": "text/plain", "value": content_data.get("plain_text_body", "")},
                ],
            },
        )
        logger.info("SendGrid email sent  recipients=%d", len(recipients))
        return {"platform": "sendgrid", "sent": len(recipients), "status": "sent"}

    async def publish_wordpress_post(self, token: OAuthToken, content: dict) -> dict:
        """POST to WordPress REST API using application password."""
        from app.services.oauth_manager_service import _decrypt
        from app.core.config import settings
        credentials = _decrypt(token.access_token_enc, settings.jwt_secret_key)
        site_url = token.account_id or ""
        if not site_url:
            raise ValueError("WordPress site URL is required as account_id")
        result = await _post_with_retry(
            f"{site_url.rstrip('/')}/wp-json/wp/v2/posts",
            headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/json"},
            json_body={
                "title": content.get("title", "New Post"),
                "content": content.get("content_markdown", content.get("body", "")),
                "status": "publish",
                "excerpt": content.get("meta_description", ""),
            },
        )
        post_id = result.get("id")
        post_url = result.get("link", "")
        logger.info("WordPress post published  id=%s  url=%s", post_id, post_url)
        return {"platform": "wordpress", "post_id": post_id, "post_url": post_url, "status": "published"}
