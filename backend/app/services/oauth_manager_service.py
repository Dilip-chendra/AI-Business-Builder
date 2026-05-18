"""OAuth manager service for encrypted provider tokens."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth_token import OAuthToken

logger = logging.getLogger(__name__)

# Platform OAuth configuration
PLATFORM_CONFIG: dict[str, dict] = {
    "linkedin": {
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "scopes": ["r_liteprofile", "r_emailaddress", "w_member_social"],
    },
    "twitter": {
        "auth_url": "https://twitter.com/i/oauth2/authorize",
        "token_url": "https://api.twitter.com/2/oauth2/token",
        "scopes": ["tweet.read", "tweet.write", "users.read"],
    },
    "facebook": {
        "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
        "scopes": ["pages_manage_posts", "pages_read_engagement"],
    },
    "instagram": {
        "auth_url": "https://api.instagram.com/oauth/authorize",
        "token_url": "https://api.instagram.com/oauth/access_token",
        "scopes": ["instagram_basic", "instagram_content_publish"],
    },
    "google_ads": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/adwords"],
    },
    "meta_ads": {
        "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
        "scopes": ["ads_management", "ads_read"],
    },
    "sendgrid": {
        "auth_url": None,  # API key based, no OAuth
        "token_url": None,
        "scopes": [],
    },
    "mailchimp": {
        "auth_url": "https://login.mailchimp.com/oauth2/authorize",
        "token_url": "https://login.mailchimp.com/oauth2/token",
        "scopes": [],
    },
    "wordpress": {
        "auth_url": None,  # Application password based
        "token_url": None,
        "scopes": [],
    },
}


def _derive_key(secret: str) -> bytes:
    """Derive a 32-byte Fernet-compatible key from the JWT secret."""
    return base64.urlsafe_b64encode(
        hashlib.sha256(secret.encode()).digest()
    )


def _encrypt(value: str, secret: str) -> str:
    """Encrypt a string value using Fernet symmetric encryption."""
    try:
        from cryptography.fernet import Fernet
        key = _derive_key(secret)
        f = Fernet(key)
        return f.encrypt(value.encode()).decode()
    except ImportError:
        # Fallback: base64 encode (not secure — install cryptography package)
        logger.warning("cryptography package not installed — using base64 encoding (NOT secure for production)")
        return base64.b64encode(value.encode()).decode()


def _decrypt(value: str, secret: str) -> str:
    """Decrypt a Fernet-encrypted string."""
    try:
        from cryptography.fernet import Fernet, InvalidToken
        key = _derive_key(secret)
        f = Fernet(key)
        return f.decrypt(value.encode()).decode()
    except ImportError:
        return base64.b64decode(value.encode()).decode()
    except Exception:
        # If decryption fails (e.g. old base64 value), try base64 decode
        try:
            return base64.b64decode(value.encode()).decode()
        except Exception:
            return value


class OAuthManagerService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        from app.core.config import settings
        self._secret = settings.jwt_secret_key

    async def get_token(
        self, user_id: str, business_id: str, platform: str
    ) -> OAuthToken | None:
        result = await self.db.execute(
            select(OAuthToken).where(
                OAuthToken.user_id == str(user_id),
                OAuthToken.business_id == str(business_id),
                OAuthToken.platform == platform,
            )
        )
        return result.scalar_one_or_none()

    async def get_decrypted_token(
        self, user_id: str, business_id: str, platform: str
    ) -> str | None:
        """Return the decrypted access token, refreshing if needed."""
        token = await self.get_token(user_id, business_id, platform)
        if not token or token.status == "disconnected":
            return None
        token = await self.refresh_if_needed(token)
        return _decrypt(token.access_token_enc, self._secret)

    async def save_token(
        self,
        user_id: str,
        business_id: str,
        platform: str,
        access_token: str,
        workspace_id: str | None = None,
        refresh_token: str | None = None,
        expires_at: str | None = None,
        account_id: str | None = None,
        account_name: str | None = None,
        scopes: list[str] | None = None,
        provider_payload: dict | None = None,
        last_error: str | None = None,
    ) -> OAuthToken:
        existing = await self.get_token(user_id, business_id, platform)
        enc_access = _encrypt(access_token, self._secret)
        enc_refresh = _encrypt(refresh_token, self._secret) if refresh_token else None

        if existing:
            existing.workspace_id = workspace_id
            existing.access_token_enc = enc_access
            existing.refresh_token_enc = enc_refresh
            existing.expires_at = expires_at
            existing.account_id = account_id
            existing.account_name = account_name
            existing.status = "connected"
            existing.last_error = last_error
            existing.provider_payload = provider_payload or {}
            if scopes:
                existing.scopes = json.dumps(scopes)
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        token = OAuthToken(
            user_id=str(user_id),
            workspace_id=str(workspace_id) if workspace_id else None,
            business_id=str(business_id),
            platform=platform,
            access_token_enc=enc_access,
            refresh_token_enc=enc_refresh,
            expires_at=expires_at,
            account_id=account_id,
            account_name=account_name,
            status="connected",
            scopes=json.dumps(scopes or []),
            provider_payload=provider_payload or {},
            last_error=last_error,
        )
        self.db.add(token)
        await self.db.commit()
        await self.db.refresh(token)
        logger.info("OAuth token saved  platform=%s  business=%s", platform, business_id)
        return token

    async def refresh_if_needed(self, token: OAuthToken) -> OAuthToken:
        """Refresh the access token if it expires within 5 minutes."""
        if not token.expires_at or not token.refresh_token_enc:
            return token
        try:
            expires = datetime.fromisoformat(token.expires_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if (expires - now).total_seconds() > 300:
                return token  # still valid
        except Exception:
            return token

        # Attempt refresh
        cfg = PLATFORM_CONFIG.get(token.platform, {})
        token_url = cfg.get("token_url")
        if not token_url:
            return token

        refresh_token = _decrypt(token.refresh_token_enc, self._secret)
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(token_url, data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                })
                if resp.status_code == 200:
                    data = resp.json()
                    new_access = data.get("access_token", "")
                    new_refresh = data.get("refresh_token", refresh_token)
                    new_expires = None
                    if "expires_in" in data:
                        from datetime import timedelta
                        new_expires = (datetime.now(timezone.utc) + timedelta(seconds=data["expires_in"])).isoformat()
                    token.access_token_enc = _encrypt(new_access, self._secret)
                    token.refresh_token_enc = _encrypt(new_refresh, self._secret)
                    token.expires_at = new_expires
                    token.status = "connected"
                    await self.db.commit()
                    logger.info("OAuth token refreshed  platform=%s", token.platform)
                else:
                    token.status = "expired"
                    await self.db.commit()
        except Exception as exc:
            logger.warning("Token refresh failed  platform=%s: %s", token.platform, exc)
            token.status = "expired"
            await self.db.commit()

        return token

    async def revoke(self, token: OAuthToken) -> None:
        """Mark token as disconnected and clear credentials."""
        token.status = "disconnected"
        token.access_token_enc = ""
        token.refresh_token_enc = None
        token.last_error = None
        await self.db.commit()
        logger.info("OAuth token revoked  platform=%s  business=%s", token.platform, token.business_id)

    async def list_statuses(self, user_id: str, business_id: str) -> list[dict]:
        """Return connection status for all supported platforms."""
        result = await self.db.execute(
            select(OAuthToken).where(
                OAuthToken.user_id == str(user_id),
                OAuthToken.business_id == str(business_id),
            )
        )
        connected = {t.platform: t for t in result.scalars().all()}
        statuses = []
        for platform in PLATFORM_CONFIG:
            token = connected.get(platform)
            statuses.append({
                "platform": platform,
                "status": token.status if token else "disconnected",
                "account_name": token.account_name if token else None,
                "account_id": token.account_id if token else None,
                "has_oauth": PLATFORM_CONFIG[platform].get("auth_url") is not None,
                "connection_error": token.last_error if token else None,
            })
        return statuses
