"""OAuth manager service for encrypted provider tokens."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.oauth_token import OAuthToken
from app.models.user_integration import UserIntegration

logger = logging.getLogger(__name__)

# Platform OAuth configuration
PLATFORM_CONFIG: dict[str, dict] = {
    "gmail": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": [
            "openid",
            "email",
            "profile",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/calendar.events",
        ],
        "client_prefix": "google",
    },
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["openid", "email", "profile", "https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/calendar.events"],
        "client_prefix": "google",
    },
    "linkedin": {
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "scopes": ["openid", "profile", "email", "w_member_social"],
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
        "client_prefix": "meta",
    },
    "instagram": {
        "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
        "scopes": ["instagram_basic", "instagram_content_publish", "pages_show_list"],
        "client_prefix": "meta",
    },
    "meta": {
        "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
        "scopes": ["pages_show_list", "pages_read_engagement"],
        "client_prefix": "meta",
    },
    "google_ads": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/adwords"],
        "client_prefix": "google",
    },
    "meta_ads": {
        "auth_url": "https://www.facebook.com/v18.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v18.0/oauth/access_token",
        "scopes": ["ads_management", "ads_read"],
        "client_prefix": "meta",
    },
    "sendgrid": {
        "auth_url": None,  # API key based, no OAuth
        "token_url": None,
        "scopes": [],
        "client_prefix": "sendgrid",
    },
    "mailchimp": {
        "auth_url": "https://login.mailchimp.com/oauth2/authorize",
        "token_url": "https://login.mailchimp.com/oauth2/token",
        "scopes": [],
    },
    "notion": {
        "auth_url": "https://api.notion.com/v1/oauth/authorize",
        "token_url": "https://api.notion.com/v1/oauth/token",
        "scopes": [],
    },
    "slack": {
        "auth_url": "https://slack.com/oauth/v2/authorize",
        "token_url": "https://slack.com/api/oauth.v2.access",
        "scopes": ["chat:write", "channels:read", "users:read"],
    },
    "wordpress": {
        "auth_url": "https://public-api.wordpress.com/oauth2/authorize",
        "token_url": "https://public-api.wordpress.com/oauth2/token",
        "scopes": ["global"],
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
        self._secret = settings.token_encryption_key or settings.encryption_key
        self._legacy_secret = settings.jwt_secret_key

    def _decrypt_token(self, value: str) -> str:
        for secret in [self._secret, self._legacy_secret]:
            try:
                return _decrypt(value, secret)
            except Exception:
                continue
        return _decrypt(value, self._secret)

    @staticmethod
    def _as_uuid(value: str | UUID | None) -> UUID | None:
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        cleaned = str(value).strip()
        if not cleaned:
            return None
        try:
            return UUID(cleaned)
        except ValueError:
            if len(cleaned) == 32:
                return UUID(cleaned)
            raise

    @staticmethod
    def _parse_expires_at(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    async def _sync_user_integration(
        self,
        *,
        user_id: str,
        business_id: str,
        platform: str,
        access_token_enc: str,
        refresh_token_enc: str | None,
        expires_at: str | None,
        account_id: str | None,
        account_name: str | None,
        scopes: list[str] | None,
        provider_payload: dict | None,
        status: str = "connected",
    ) -> None:
        normalized_user_id = self._as_uuid(user_id)
        normalized_business_id = self._as_uuid(business_id)
        if normalized_user_id is None:
            return

        result = await self.db.execute(
            select(UserIntegration).where(
                UserIntegration.user_id == normalized_user_id,
                UserIntegration.business_id == normalized_business_id,
                UserIntegration.provider == platform,
            )
        )
        integration = result.scalar_one_or_none()
        if integration is None:
            integration = UserIntegration(
                user_id=normalized_user_id,
                business_id=normalized_business_id,
                provider=platform,
            )
            self.db.add(integration)

        integration.provider_account_id = account_id
        profile = (provider_payload or {}).get("profile") or {}
        integration.provider_account_email = profile.get("email") if isinstance(profile, dict) else None
        integration.provider_account_name = account_name
        integration.access_token_encrypted = access_token_enc
        integration.refresh_token_encrypted = refresh_token_enc
        integration.expires_at = self._parse_expires_at(expires_at)
        integration.scopes = scopes or []
        integration.status = status
        integration.metadata_json = provider_payload or {}

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
        return self._decrypt_token(token.access_token_enc)

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
        await self._sync_user_integration(
            user_id=user_id,
            business_id=business_id,
            platform=platform,
            access_token_enc=enc_access,
            refresh_token_enc=enc_refresh,
            expires_at=expires_at,
            account_id=account_id,
            account_name=account_name,
            scopes=scopes,
            provider_payload=provider_payload,
            status="connected",
        )

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

        refresh_token = self._decrypt_token(token.refresh_token_enc)
        try:
            from app.core.config import settings
            prefix = PLATFORM_CONFIG.get(token.platform, {}).get("client_prefix") or token.platform
            client_id = getattr(settings, f"{prefix}_client_id", None) or (getattr(settings, "google_client_id", None) if prefix == "gmail" else None)
            client_secret = getattr(settings, f"{prefix}_client_secret", None) or (getattr(settings, "google_client_secret", None) if prefix == "gmail" else None)
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(token_url, data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": client_id,
                    "client_secret": client_secret,
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
        result = await self.db.execute(
            select(UserIntegration).where(
                UserIntegration.user_id == self._as_uuid(token.user_id),
                UserIntegration.business_id == self._as_uuid(token.business_id),
                UserIntegration.provider == token.platform,
            )
        )
        integration = result.scalar_one_or_none()
        if integration:
            integration.status = "disconnected"
            integration.access_token_encrypted = ""
            integration.refresh_token_encrypted = None
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
            if platform == "gmail" and not token:
                token = connected.get("google")
            if platform == "sendgrid":
                from app.core.config import settings
                if settings.sendgrid_api_key:
                    statuses.append({
                        "platform": platform,
                        "status": "connected",
                        "account_name": "Environment API key",
                        "account_id": "env:SENDGRID_API_KEY",
                        "has_oauth": False,
                        "connection_error": None,
                    })
                    continue
            statuses.append({
                "platform": platform,
                "status": token.status if token else "disconnected",
                "account_name": token.account_name if token else None,
                "account_id": token.account_id if token else None,
                "has_oauth": PLATFORM_CONFIG[platform].get("auth_url") is not None,
                "connection_error": token.last_error if token else None,
            })
        return statuses
