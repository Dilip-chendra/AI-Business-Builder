"""Platform integration routes and reusable OAuth plumbing."""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.models.user_integration import IntegrationActionLog, OAuthStateRecord
from app.services.business_service import BusinessService
from app.services.integration_audit_service import IntegrationAuditService
from app.services.integration_account_service import IntegrationAccountService
from app.services.oauth_manager_service import OAuthManagerService, PLATFORM_CONFIG
from app.services.oauth_state_service import OAuthStateError, OAuthStateService

router = APIRouter()
logger = logging.getLogger(__name__)


class ApiKeyConnect(BaseModel):
    api_key: str
    account_id: str | None = None
    account_name: str | None = None


class OAuthConnectPayload(BaseModel):
    business_id: UUID


class IntegrationAccountPayload(BaseModel):
    email: str | None = None
    phone: str | None = None
    password: str | None = None


def _provider_redirect_uri(platform: str) -> str | None:
    cfg = PLATFORM_CONFIG.get(platform, {})
    if not cfg.get("auth_url"):
        return None
    configured = getattr(settings, f"{platform}_redirect_uri", None)
    generated = f"{str(settings.backend_url).rstrip('/')}/api/v1/integrations/{platform}/callback"
    if settings.is_production and configured:
        configured_text = str(configured)
        if "localhost" in configured_text or "127.0.0.1" in configured_text:
            return generated
    if configured:
        return str(configured)
    return generated


def _provider_client_prefix(platform: str) -> str:
    cfg = PLATFORM_CONFIG.get(platform, {})
    return str(cfg.get("client_prefix") or platform)


def _provider_client_id(platform: str) -> str | None:
    prefix = _provider_client_prefix(platform)
    value = getattr(settings, f"{prefix}_client_id", None)
    if not value and prefix == "gmail":
        value = getattr(settings, "google_client_id", None)
    return value


def _provider_client_secret(platform: str) -> str | None:
    prefix = _provider_client_prefix(platform)
    value = getattr(settings, f"{prefix}_client_secret", None)
    if not value and prefix == "gmail":
        value = getattr(settings, "google_client_secret", None)
    return value


def _provider_required_env_vars(platform: str) -> list[str]:
    prefix = _provider_client_prefix(platform).upper()
    return [f"{prefix}_CLIENT_ID", f"{prefix}_CLIENT_SECRET"]


def _provider_name(platform: str) -> str:
    return platform.replace("_", " ").title()


def _provider_frontend_redirect(
    *,
    platform: str,
    business_id: str | None,
    oauth_status: str,
    message: str | None = None,
) -> str:
    params = [f"tab=integrations", f"provider={quote_plus(platform)}", f"oauth={quote_plus(oauth_status)}"]
    if business_id:
        params.append(f"business_id={quote_plus(business_id)}")
    if message:
        params.append(f"message={quote_plus(message)}")
    return f"{settings.frontend_url}/marketing?{'&'.join(params)}"


async def _resolve_business_for_user(
    db: AsyncSession,
    *,
    business_id: UUID,
    current_user: User,
):
    business = await BusinessService(db).get(business_id, user_id=current_user.id)
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


async def _exchange_oauth_code(
    *,
    platform: str,
    code: str,
    redirect_uri: str,
    code_verifier: str | None = None,
) -> dict:
    cfg = PLATFORM_CONFIG.get(platform)
    if not cfg or not cfg.get("token_url"):
        raise HTTPException(status_code=400, detail=f"Platform {platform} does not support OAuth callback")

    client_id = _provider_client_id(platform)
    client_secret = _provider_client_secret(platform)
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail=f"{platform} is not configured.")

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if platform == "twitter" and code_verifier:
        payload["code_verifier"] = code_verifier
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if platform == "notion":
        encoded = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
        headers["Authorization"] = f"Basic {encoded}"
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
    async with httpx.AsyncClient(timeout=25.0) as client:
        if platform == "notion":
            response = await client.post(cfg["token_url"], json=payload, headers={**headers, "Content-Type": "application/json"})
            if response.status_code >= 400:
                # Some OAuth-compatible gateways still accept the form variant. Try it once before surfacing a clean provider error.
                response = await client.post(cfg["token_url"], data=payload, headers=headers)
        else:
            response = await client.post(cfg["token_url"], data=payload, headers=headers)
        response.raise_for_status()
        return response.json()


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


async def _fetch_linkedin_account(access_token: str) -> tuple[str | None, str | None, dict]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        profile_response = await client.get("https://api.linkedin.com/v2/me", headers=headers)
        if profile_response.status_code >= 400:
            profile_response = await client.get("https://api.linkedin.com/v2/userinfo", headers=headers)
        profile_response.raise_for_status()
        profile = profile_response.json()

    account_id = profile.get("id") or profile.get("sub")
    first_name = profile.get("localizedFirstName") or ""
    last_name = profile.get("localizedLastName") or ""
    account_name = " ".join(part for part in [first_name, last_name] if part).strip() or profile.get("name") or profile.get("email") or None
    return account_id, account_name, profile


async def _fetch_provider_account(platform: str, access_token: str, token_data: dict) -> tuple[str | None, str | None, dict]:
    if platform == "linkedin":
        try:
            return await _fetch_linkedin_account(access_token)
        except Exception:
            pass
    if platform in {"gmail", "google", "google_ads"}:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get("https://www.googleapis.com/oauth2/v3/userinfo", headers=headers)
            response.raise_for_status()
            profile = response.json()
        return profile.get("sub") or profile.get("email"), profile.get("email") or profile.get("name"), profile
    if platform in {"facebook", "instagram", "meta", "meta_ads"}:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                "https://graph.facebook.com/v18.0/me",
                params={"fields": "id,name,email", "access_token": access_token},
            )
            response.raise_for_status()
            profile = response.json()
        return profile.get("id"), profile.get("name") or profile.get("email"), profile
    if platform == "twitter":
        headers = {"Authorization": f"Bearer {access_token}"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get("https://api.twitter.com/2/users/me", headers=headers)
            response.raise_for_status()
            payload = response.json()
        profile = payload.get("data") or {}
        return profile.get("id"), profile.get("username") or profile.get("name"), payload
    if platform == "slack":
        team = token_data.get("team") or {}
        authed_user = token_data.get("authed_user") or {}
        return team.get("id") or authed_user.get("id"), team.get("name"), {"team": team, "authed_user": authed_user}
    if platform == "notion":
        owner = token_data.get("owner") or {}
        workspace_name = token_data.get("workspace_name")
        return token_data.get("workspace_id"), workspace_name, {"owner": owner, "workspace_name": workspace_name}
    if platform == "wordpress":
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                "https://public-api.wordpress.com/rest/v1.1/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            profile = response.json()
        return str(profile.get("ID") or ""), profile.get("display_name") or profile.get("username"), profile
    return None, None, {}


def _sanitize_token_payload(token_data: dict) -> dict:
    redacted_keys = {"access_token", "refresh_token", "id_token"}
    return {key: ("[encrypted]" if key in redacted_keys else value) for key, value in token_data.items()}


def _state_hash(state_token: str) -> str:
    return hashlib.sha256(state_token.encode("utf-8")).hexdigest()


async def _record_oauth_state(db: AsyncSession, state_token: str, state_payload, redirect_after: str | None = None) -> None:
    record = OAuthStateRecord(
        user_id=UUID(state_payload.user_id),
        business_id=UUID(state_payload.business_id) if state_payload.business_id else None,
        provider=state_payload.provider,
        state_hash=_state_hash(state_token),
        redirect_after=redirect_after,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=OAuthStateService.ttl_seconds),
    )
    db.add(record)
    await db.commit()


async def _mark_oauth_state_used(db: AsyncSession, state_token: str) -> None:
    result = await db.execute(select(OAuthStateRecord).where(OAuthStateRecord.state_hash == _state_hash(state_token)))
    record = result.scalar_one_or_none()
    if record:
        record.used_at = datetime.now(timezone.utc)
        await db.commit()


@router.get("/{business_id}")
async def list_integrations(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    business = await _resolve_business_for_user(db, business_id=business_id, current_user=current_user)
    svc = OAuthManagerService(db)
    statuses = await svc.list_statuses(str(current_user.id), str(business_id))
    enriched: list[dict] = []
    for item in statuses:
        cfg = PLATFORM_CONFIG.get(item["platform"], {})
        redirect_uri = _provider_redirect_uri(item["platform"])
        client_id = _provider_client_id(item["platform"])
        client_secret = _provider_client_secret(item["platform"])
        ready_to_connect = not cfg.get("auth_url") or bool(client_id and client_secret)
        state_label = item["status"]
        if item["status"] == "disconnected" and not ready_to_connect:
            state_label = "not_configured"
        elif item["status"] == "disconnected" and ready_to_connect:
            state_label = "ready_to_connect"
        enriched.append(
            {
                **item,
                "workspace_id": str(business.workspace_id) if business.workspace_id else None,
                "state_label": state_label,
                "ready_to_connect": ready_to_connect,
                "connect_mode": "oauth" if cfg.get("auth_url") else "browser_or_api_key",
                "redirect_uri": redirect_uri,
                "required_env_vars": _provider_required_env_vars(item["platform"]) if cfg.get("auth_url") else [],
                "scopes": cfg.get("scopes", []),
                "connection_error": item.get("connection_error")
                or (None if ready_to_connect else "OAuth app credentials are not configured by the app owner yet."),
            }
        )
    return enriched


@router.get("/{business_id}/accounts")
async def list_integration_accounts(
    business_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    business = await _resolve_business_for_user(db, business_id=business_id, current_user=current_user)
    svc = IntegrationAccountService(db)
    accounts = await svc.list_for_business(user_id=current_user.id, business_id=business_id)
    by_platform = {account.platform: svc.summary(account) for account in accounts}
    supported = ["linkedin", "instagram", "gmail", "browser_automation"]
    return [
        by_platform.get(
            platform,
            {
                "id": None,
                "platform": platform,
                "status": "disconnected",
                "identifier_preview": "",
                "last_active_at": None,
                "last_tested_at": None,
                "last_error": None,
            },
        )
        for platform in supported
    ]


@router.put("/{business_id}/accounts/{platform}")
async def save_integration_account(
    business_id: UUID,
    platform: str,
    payload: IntegrationAccountPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    business = await _resolve_business_for_user(db, business_id=business_id, current_user=current_user)
    svc = IntegrationAccountService(db)
    account = await svc.save(
        user_id=current_user.id,
        workspace_id=business.workspace_id,
        business_id=business.id,
        platform=platform,
        login_identifier=(payload.email or "").strip() or None,
        password=(payload.password or "").strip() or None,
        phone=(payload.phone or "").strip() or None,
        metadata={"provider": platform},
    )
    return svc.summary(account)


@router.post("/{business_id}/accounts/{platform}/test")
async def test_integration_account(
    business_id: UUID,
    platform: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _resolve_business_for_user(db, business_id=business_id, current_user=current_user)
    svc = IntegrationAccountService(db)
    account = await svc.get(user_id=current_user.id, business_id=business_id, platform=platform)
    if not account:
        raise HTTPException(status_code=404, detail="No saved credentials for this platform.")
    revealed = svc.reveal(account)
    ok = bool(revealed.get("password") and (revealed.get("email") or revealed.get("phone")))
    updated = await svc.mark_test_result(account, ok=ok, error=None if ok else "Missing login identifier or password.")
    return svc.summary(updated)


@router.delete("/{business_id}/accounts/{platform}")
async def delete_integration_account(
    business_id: UUID,
    platform: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _resolve_business_for_user(db, business_id=business_id, current_user=current_user)
    svc = IntegrationAccountService(db)
    account = await svc.get(user_id=current_user.id, business_id=business_id, platform=platform)
    if not account:
        return {"status": "not_found", "platform": platform}
    await svc.delete(account)
    return {"status": "deleted", "platform": platform}


async def _build_oauth_connect_response(
    platform: str,
    *,
    business_id: UUID,
    current_user: User,
    db: AsyncSession,
) -> dict:
    business = await _resolve_business_for_user(db, business_id=business_id, current_user=current_user)
    cfg = PLATFORM_CONFIG.get(platform)
    if not cfg:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    if not cfg.get("auth_url"):
        return {
            "platform": platform,
            "type": "api_key",
            "message": f"{_provider_name(platform)} uses API-key or browser automation fallback instead of OAuth.",
            "instructions": _get_api_key_instructions(platform),
        }

    client_id = _provider_client_id(platform)
    client_secret = _provider_client_secret(platform)
    redirect_uri = _provider_redirect_uri(platform)
    ready_to_connect = bool(client_id and client_secret)
    if not ready_to_connect:
        return {
            "platform": platform,
            "type": "provider_config_missing",
            "message": "This OAuth provider is not configured by the app owner yet. Add the provider app credentials to backend/.env, then users can connect with one click.",
            "provider_name": _provider_name(platform),
            "redirect_uri": redirect_uri,
            "required_env_vars": _provider_required_env_vars(platform),
            "scopes": cfg.get("scopes", []),
            "ready_to_connect": False,
        }

    code_verifier = None
    code_challenge = None
    if platform == "twitter":
        code_verifier, code_challenge = _pkce_pair()

    state_token, state_payload = await OAuthStateService().issue(
        provider=platform,
        user_id=str(current_user.id),
        business_id=str(business.id),
        workspace_id=str(business.workspace_id) if business.workspace_id else None,
        code_verifier=code_verifier,
    )
    await _record_oauth_state(db, state_token, state_payload, redirect_after=f"{settings.frontend_url}/marketing?tab=integrations")
    await IntegrationAuditService(db).record(
        user_id=current_user.id,
        business_id=business.id,
        provider=platform,
        action="oauth_connect_started",
        status="pending",
        message=f"{_provider_name(platform)} OAuth authorization URL generated.",
    )
    scopes = quote_plus(" ".join(cfg["scopes"]))
    extra_params = ""
    if platform in {"gmail", "google", "google_ads"}:
        extra_params = "&access_type=offline&prompt=consent&include_granted_scopes=true"
    if platform == "notion":
        extra_params = "&owner=user"
    if platform == "twitter" and code_challenge:
        extra_params = f"{extra_params}&code_challenge={quote_plus(code_challenge)}&code_challenge_method=S256"
    auth_url = (
        f"{cfg['auth_url']}?"
        f"response_type=code&"
        f"client_id={quote_plus(str(client_id))}&"
        f"redirect_uri={quote_plus(redirect_uri or '')}&"
        f"scope={scopes}&"
        f"state={quote_plus(state_token)}"
        f"{extra_params}"
    )
    return {
        "platform": platform,
        "type": "oauth",
        "auth_url": auth_url,
        "authorization_url": auth_url,
        "message": f"Redirecting to {_provider_name(platform)} for secure OAuth authorization.",
    }


@router.get("/{platform}/connect")
async def connect_platform_get(
    platform: str,
    business_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await _build_oauth_connect_response(platform, business_id=business_id, current_user=current_user, db=db)


@router.post("/{platform}/connect")
async def connect_platform(
    platform: str,
    payload: OAuthConnectPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await _build_oauth_connect_response(platform, business_id=payload.business_id, current_user=current_user, db=db)


@router.get("/{platform}/callback")
async def oauth_callback(
    platform: str,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    if error:
        logger.warning("OAuth callback error platform=%s error=%s description=%s", platform, error, error_description)
        return RedirectResponse(
            _provider_frontend_redirect(
                platform=platform,
                business_id=None,
                oauth_status="error",
                message=error_description or error,
            ),
            status_code=status.HTTP_302_FOUND,
        )

    if not code or not state:
        raise HTTPException(status_code=400, detail="OAuth callback is missing the code or state.")

    try:
        state_payload = await OAuthStateService().consume(platform, state)
        await _mark_oauth_state_used(db, state)
    except OAuthStateError as exc:
        logger.warning("OAuth state validation failed platform=%s: %s", platform, exc)
        return RedirectResponse(
            _provider_frontend_redirect(
                platform=platform,
                business_id=None,
                oauth_status="error",
                message=str(exc),
            ),
            status_code=status.HTTP_302_FOUND,
        )

    try:
        business = await BusinessService(db).get(UUID(state_payload.business_id), user_id=UUID(state_payload.user_id))
        if not business:
            raise HTTPException(status_code=404, detail="Business not found for OAuth callback.")

        redirect_uri = _provider_redirect_uri(platform)
        token_data = await _exchange_oauth_code(
            platform=platform,
            code=code,
            redirect_uri=redirect_uri or "",
            code_verifier=state_payload.code_verifier,
        )

        expires_at = None
        if token_data.get("expires_in"):
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(token_data["expires_in"]))).isoformat()

        account_id = None
        account_name = None
        provider_payload: dict = {"oauth_response": _sanitize_token_payload(token_data)}
        if token_data.get("access_token"):
            try:
                account_id, account_name, profile = await _fetch_provider_account(platform, token_data["access_token"], token_data)
                provider_payload["profile"] = profile
            except Exception as profile_exc:
                logger.warning("OAuth profile lookup failed platform=%s: %s", platform, profile_exc)

        await OAuthManagerService(db).save_token(
            user_id=state_payload.user_id,
            workspace_id=state_payload.workspace_id or (str(business.workspace_id) if business.workspace_id else None),
            business_id=state_payload.business_id,
            platform=platform,
            access_token=token_data.get("access_token", ""),
            refresh_token=token_data.get("refresh_token"),
            expires_at=expires_at,
            account_id=account_id,
            account_name=account_name,
            scopes=PLATFORM_CONFIG.get(platform, {}).get("scopes", []),
            provider_payload=provider_payload,
            last_error=None,
        )
        if platform == "google":
            await OAuthManagerService(db).save_token(
                user_id=state_payload.user_id,
                workspace_id=state_payload.workspace_id or (str(business.workspace_id) if business.workspace_id else None),
                business_id=state_payload.business_id,
                platform="gmail",
                access_token=token_data.get("access_token", ""),
                refresh_token=token_data.get("refresh_token"),
                expires_at=expires_at,
                account_id=account_id,
                account_name=account_name,
                scopes=PLATFORM_CONFIG.get("gmail", {}).get("scopes", []),
                provider_payload={**provider_payload, "alias_of": "google"},
                last_error=None,
            )
        await IntegrationAuditService(db).record(
            user_id=state_payload.user_id,
            business_id=state_payload.business_id,
            provider=platform,
            action="oauth_callback_completed",
            status="success",
            message=f"{_provider_name(platform)} connected successfully.",
            metadata={"account_id": account_id, "account_name": account_name},
        )
        logger.info(
            "OAuth callback completed platform=%s business=%s user=%s",
            platform,
            state_payload.business_id,
            state_payload.user_id,
        )
        return RedirectResponse(
            _provider_frontend_redirect(
                platform=platform,
                business_id=state_payload.business_id,
                oauth_status="success",
                message=f"{_provider_name(platform)} connected successfully.",
            ),
            status_code=status.HTTP_302_FOUND,
        )
    except Exception as exc:
        logger.exception("OAuth callback failed platform=%s business=%s", platform, state_payload.business_id)
        return RedirectResponse(
            _provider_frontend_redirect(
                platform=platform,
                business_id=state_payload.business_id,
                oauth_status="error",
                message=str(exc),
            ),
            status_code=status.HTTP_302_FOUND,
        )


@router.post("/{business_id}/{platform}/disconnect")
async def disconnect_platform(
    business_id: UUID,
    platform: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _resolve_business_for_user(db, business_id=business_id, current_user=current_user)
    svc = OAuthManagerService(db)
    token = await svc.get_token(str(current_user.id), str(business_id), platform)
    if platform == "gmail" and not token:
        token = await svc.get_token(str(current_user.id), str(business_id), "google")
    if not token:
        return {"status": "not_connected", "platform": platform}
    await svc.revoke(token)
    if platform in {"gmail", "google"}:
        alias_platform = "google" if platform == "gmail" else "gmail"
        alias_token = await svc.get_token(str(current_user.id), str(business_id), alias_platform)
        if alias_token:
            await svc.revoke(alias_token)
    await IntegrationAuditService(db).record(
        user_id=current_user.id,
        business_id=business_id,
        provider=platform,
        action="disconnect",
        status="success",
        message=f"{_provider_name(platform)} disconnected.",
    )
    return {"status": "disconnected", "platform": platform}


@router.get("/{platform}/status")
async def get_platform_status(
    platform: str,
    business_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _resolve_business_for_user(db, business_id=business_id, current_user=current_user)
    cfg = PLATFORM_CONFIG.get(platform)
    if not cfg:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")
    if platform == "sendgrid":
        configured = bool(settings.sendgrid_api_key)
        return {
            "platform": platform,
            "status": "connected" if configured else "not_configured",
            "account_id": "env:SENDGRID_API_KEY" if configured else None,
            "account_name": "Environment API key" if configured else None,
            "expires_at": None,
            "scopes": [],
            "ready_to_connect": configured,
            "connect_mode": "env_api_key",
            "last_error": None if configured else "SendGrid not configured. Add SENDGRID_API_KEY to backend/.env.",
        }
    manager = OAuthManagerService(db)
    token = await manager.get_token(str(current_user.id), str(business_id), platform)
    if platform == "gmail" and not token:
        token = await manager.get_token(str(current_user.id), str(business_id), "google")
    ready_to_connect = not cfg.get("auth_url") or bool(_provider_client_id(platform) and _provider_client_secret(platform))
    return {
        "platform": platform,
        "status": token.status if token else "disconnected",
        "account_id": token.account_id if token else None,
        "account_name": token.account_name if token else None,
        "expires_at": token.expires_at if token else None,
        "scopes": cfg.get("scopes", []),
        "ready_to_connect": ready_to_connect,
        "connect_mode": "oauth" if cfg.get("auth_url") else "browser_or_api_key",
        "last_error": token.last_error if token else (None if ready_to_connect else "OAuth app credentials are not configured by the app owner yet."),
    }


@router.delete("/{platform}")
async def disconnect_platform_delete(
    platform: str,
    business_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _resolve_business_for_user(db, business_id=business_id, current_user=current_user)
    svc = OAuthManagerService(db)
    token = await svc.get_token(str(current_user.id), str(business_id), platform)
    if platform == "gmail" and not token:
        token = await svc.get_token(str(current_user.id), str(business_id), "google")
    if not token:
        return {"status": "not_connected", "platform": platform}
    await svc.revoke(token)
    if platform in {"gmail", "google"}:
        alias_platform = "google" if platform == "gmail" else "gmail"
        alias_token = await svc.get_token(str(current_user.id), str(business_id), alias_platform)
        if alias_token:
            await svc.revoke(alias_token)
    await IntegrationAuditService(db).record(
        user_id=current_user.id,
        business_id=business_id,
        provider=platform,
        action="disconnect",
        status="success",
        message=f"{_provider_name(platform)} disconnected.",
    )
    return {"status": "disconnected", "platform": platform}


@router.delete("/{platform}/disconnect")
async def disconnect_platform_delete_alias(
    platform: str,
    business_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await disconnect_platform_delete(platform=platform, business_id=business_id, current_user=current_user, db=db)


@router.post("/{platform}/refresh")
async def refresh_platform_token(
    platform: str,
    business_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _resolve_business_for_user(db, business_id=business_id, current_user=current_user)
    if platform == "sendgrid":
        if not settings.sendgrid_api_key:
            raise HTTPException(status_code=404, detail="SendGrid not configured. Add SENDGRID_API_KEY to backend/.env.")
        return {"platform": platform, "status": "connected", "expires_at": None, "message": "SendGrid uses backend/.env API key configuration and does not need token refresh."}
    svc = OAuthManagerService(db)
    token = await svc.get_token(str(current_user.id), str(business_id), platform)
    if platform == "gmail" and not token:
        token = await svc.get_token(str(current_user.id), str(business_id), "google")
    if not token:
        raise HTTPException(status_code=404, detail=f"{_provider_name(platform)} is not connected.")
    refreshed = await svc.refresh_if_needed(token)
    await IntegrationAuditService(db).record(
        user_id=current_user.id,
        business_id=business_id,
        provider=platform,
        action="refresh",
        status=refreshed.status,
        message=f"{_provider_name(platform)} token refresh checked.",
    )
    return {
        "platform": platform,
        "status": refreshed.status,
        "expires_at": refreshed.expires_at,
        "message": "Token refresh checked. Reconnect if the provider reports an expired authorization.",
    }


@router.post("/{platform}/test")
async def test_platform_connection(
    platform: str,
    business_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _resolve_business_for_user(db, business_id=business_id, current_user=current_user)
    if platform == "sendgrid":
        if not settings.sendgrid_api_key:
            raise HTTPException(status_code=400, detail="SendGrid not configured. Add SENDGRID_API_KEY to backend/.env.")
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.sendgrid.com/v3/user/account",
                headers={"Authorization": f"Bearer {settings.sendgrid_api_key}"},
            )
        if response.status_code >= 400:
            await IntegrationAuditService(db).record(
                user_id=current_user.id,
                business_id=business_id,
                provider="sendgrid",
                action="test_connection",
                status="failed",
                message="SendGrid API key validation failed.",
                metadata={"status_code": response.status_code},
            )
            raise HTTPException(status_code=400, detail="SendGrid API key validation failed. Check SENDGRID_API_KEY permissions.")
        await IntegrationAuditService(db).record(
            user_id=current_user.id,
            business_id=business_id,
            provider="sendgrid",
            action="test_connection",
            status="success",
            message="SendGrid API key is valid.",
        )
        return {"platform": platform, "status": "connected", "account_name": "Environment API key", "message": "SendGrid API key is valid."}
    manager = OAuthManagerService(db)
    token = await manager.get_token(str(current_user.id), str(business_id), platform)
    if platform == "gmail" and not token:
        token = await manager.get_token(str(current_user.id), str(business_id), "google")
    if not token or token.status != "connected":
        raise HTTPException(status_code=400, detail=f"Connect {_provider_name(platform)} before testing it.")
    await IntegrationAuditService(db).record(
        user_id=current_user.id,
        business_id=business_id,
        provider=platform,
        action="test_connection",
        status="success",
        message=f"{_provider_name(platform)} authorization is stored securely.",
    )
    return {
        "platform": platform,
        "status": "connected",
        "account_name": token.account_name,
        "message": f"{_provider_name(platform)} authorization is stored securely. Provider API action tests run when publishing tools are invoked.",
    }


@router.get("/actions/logs")
async def list_integration_action_logs(
    business_id: UUID = Query(...),
    platform: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    await _resolve_business_for_user(db, business_id=business_id, current_user=current_user)
    stmt = (
        select(IntegrationActionLog)
        .where(
            IntegrationActionLog.user_id == current_user.id,
            IntegrationActionLog.business_id == business_id,
        )
        .order_by(IntegrationActionLog.created_at.desc())
        .limit(limit)
    )
    if platform:
        stmt = stmt.where(IntegrationActionLog.provider == platform)
    result = await db.execute(stmt)
    return [
        {
            "id": str(log.id),
            "provider": log.provider,
            "action": log.action,
            "status": log.status,
            "message": log.message,
            "metadata": log.metadata_json or {},
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in result.scalars().all()
    ]


@router.post("/{business_id}/{platform}/connect-apikey")
async def connect_with_api_key(
    business_id: UUID,
    platform: str,
    payload: ApiKeyConnect,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    business = await _resolve_business_for_user(db, business_id=business_id, current_user=current_user)
    svc = OAuthManagerService(db)
    await svc.save_token(
        user_id=str(current_user.id),
        workspace_id=str(business.workspace_id) if business.workspace_id else None,
        business_id=str(business_id),
        platform=platform,
        access_token=payload.api_key,
        account_id=payload.account_id,
        account_name=payload.account_name or platform,
        provider_payload={"mode": "api_key"},
        last_error=None,
    )
    return {"status": "connected", "platform": platform}


def _get_api_key_instructions(platform: str) -> str:
    instructions = {
        "sendgrid": "Create an API key at https://app.sendgrid.com/settings/api_keys with Mail Send permission.",
        "wordpress": "Create an Application Password at your WordPress site: Users > Profile > Application Passwords. Use format username:app_password as the API key.",
        "mailchimp": "Get your API key at https://mailchimp.com/help/about-api-keys/.",
    }
    return instructions.get(platform, f"Provide your {platform} API key or credentials.")


