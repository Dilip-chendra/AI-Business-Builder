from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.core.cache import cache
from app.core.config import settings


@dataclass(slots=True)
class OAuthStatePayload:
    provider: str
    csrf: str
    user_id: str
    business_id: str
    workspace_id: str | None
    integration_id: str
    ts: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "csrf": self.csrf,
            "user_id": self.user_id,
            "business_id": self.business_id,
            "workspace_id": self.workspace_id,
            "integration_id": self.integration_id,
            "ts": self.ts,
        }


class OAuthStateError(ValueError):
    """Raised when an OAuth state payload is missing, invalid, or expired."""


class OAuthStateService:
    """Issues opaque, replay-protected OAuth state payloads.

    We encrypt the contextual payload with Fernet so raw IDs are not exposed in
    the browser URL, then we keep a short-lived CSRF marker in cache to prevent
    replay and cross-request tampering.
    """

    ttl_seconds = 15 * 60

    def __init__(self) -> None:
        self._secret = settings.jwt_secret_key

    def _derive_key(self) -> bytes:
        return base64.urlsafe_b64encode(hashlib.sha256(self._secret.encode("utf-8")).digest())

    def _load_fernet(self):
        from cryptography.fernet import Fernet

        return Fernet(self._derive_key())

    def _sign_digest(self, payload: OAuthStatePayload) -> str:
        body = json.dumps(payload.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hmac.new(self._secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    async def issue(
        self,
        *,
        provider: str,
        user_id: str,
        business_id: str,
        workspace_id: str | None,
    ) -> tuple[str, OAuthStatePayload]:
        payload = OAuthStatePayload(
            provider=provider,
            csrf=secrets.token_urlsafe(24),
            user_id=str(user_id),
            business_id=str(business_id),
            workspace_id=str(workspace_id) if workspace_id else None,
            integration_id=str(uuid4()),
            ts=int(time.time()),
        )
        token = self._load_fernet().encrypt(
            json.dumps(payload.to_dict(), separators=(",", ":")).encode("utf-8")
        ).decode("utf-8")
        await cache.set(
            f"oauth:state:pending:{payload.provider}:{payload.csrf}",
            {
                "digest": self._sign_digest(payload),
                "integration_id": payload.integration_id,
                "ts": payload.ts,
            },
            ttl=self.ttl_seconds,
        )
        return token, payload

    async def consume(self, provider: str, token: str) -> OAuthStatePayload:
        try:
            decrypted = self._load_fernet().decrypt(token.encode("utf-8")).decode("utf-8")
            decoded = json.loads(decrypted)
        except Exception as exc:  # pragma: no cover - crypto exceptions vary
            raise OAuthStateError("Invalid OAuth state payload.") from exc

        payload = OAuthStatePayload(
            provider=str(decoded.get("provider") or ""),
            csrf=str(decoded.get("csrf") or ""),
            user_id=str(decoded.get("user_id") or ""),
            business_id=str(decoded.get("business_id") or ""),
            workspace_id=str(decoded.get("workspace_id")) if decoded.get("workspace_id") else None,
            integration_id=str(decoded.get("integration_id") or ""),
            ts=int(decoded.get("ts") or 0),
        )

        if payload.provider != provider:
            raise OAuthStateError("OAuth state provider mismatch.")
        if not payload.csrf or not payload.user_id or not payload.business_id or not payload.integration_id:
            raise OAuthStateError("OAuth state is incomplete.")
        if int(time.time()) - payload.ts > self.ttl_seconds:
            raise OAuthStateError("OAuth state has expired.")

        pending_key = f"oauth:state:pending:{payload.provider}:{payload.csrf}"
        used_key = f"oauth:state:used:{payload.provider}:{payload.csrf}"
        if await cache.get(used_key):
            raise OAuthStateError("OAuth state has already been used.")

        pending = await cache.get(pending_key)
        if not pending:
            raise OAuthStateError("OAuth state is missing or already consumed.")

        if pending.get("digest") != self._sign_digest(payload):
            raise OAuthStateError("OAuth state signature mismatch.")

        await cache.delete(pending_key)
        await cache.set(
            used_key,
            {"integration_id": payload.integration_id, "ts": payload.ts},
            ttl=self.ttl_seconds,
        )
        return payload
