"""Platform integration routes and reusable OAuth plumbing."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.models.user import User
from app.services.business_service import BusinessService
from app.services.integration_account_service import IntegrationAccountService
from app.services.oauth_manager_service import OAuthManagerService, PLATFORM_CONFIG
from app.services.oauth_state_service import OAuthStateError, OAuthStateService

router = APIRouter()
logger = logging.getLogger(__name__)
BACKEND_ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


class ApiKeyConnect(BaseModel):
    api_key: str
    account_id: str | None = None
    account_name: str | None = None


class ProviderSettingsPayload(BaseModel):
    client_id: str | None = None
    client_secret: str | None = None


class ProviderSettingsResponse(BaseModel):
    platform: str
    provider_name: str
    connect_mode: str
    redirect_uri: str | None = None
    required_env_vars: list[str]
    scopes: list[str]
    client_id_configured: bool
    client_secret_configured: bool
    client_id_preview: str | None = None
    ready_to_connect: bool
    message: str


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
    if platform == "linkedin":
        return settings.linkedin_redirect_uri
    return f"{settings.backend_url}/api/v1/integrations/{platform}/callback"


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


def _provider_settings_response(platform: str) -> ProviderSettingsResponse:
    cfg = PLATFORM_CONFIG.get(platform)
    if not cfg:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    connect_mode = "oauth" if cfg.get("auth_url") else "browser_or_api_key"
    client_id = getattr(settings, f"{platform}_client_id", None)
    client_secret = getattr(settings, f"{platform}_client_secret", None)
    ready_to_connect = not cfg.get("auth_url") or bool(client_id and client_secret)

    return ProviderSettingsResponse(
        platform=platform,
        provider_name=_provider_name(platform),
        connect_mode=connect_mode,
        redirect_uri=_provider_redirect_uri(platform),
        required_env_vars=(
            [f"{platform.upper()}_CLIENT_ID", f"{platform.upper()}_CLIENT_SECRET"]
            + ([f"{platform.upper()}_REDIRECT_URI"] if platform == "linkedin" else [])
            if cfg.get("auth_url")
            else []
        ),
        scopes=cfg.get("scopes", []),
        client_id_configured=bool(client_id),
        client_secret_configured=bool(client_secret),
        client_id_preview=_preview_secret(client_id),
        ready_to_connect=ready_to_connect,
        message=(
            "Provider is ready to connect."
            if ready_to_connect
            else "This integration is not configured yet. Add the client ID, client secret, and register the fixed callback URL in the provider portal."
        ),
    )


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
) -> dict:
    cfg = PLATFORM_CONFIG.get(platform)
    if not cfg or not cfg.get("token_url"):
        raise HTTPException(status_code=400, detail=f"Platform {platform} does not support OAuth callback")

    client_id = getattr(settings, f"{platform}_client_id", None)
    client_secret = getattr(settings, f"{platform}_client_secret", None)
    if not client_id or not client_secret:
        raise HTTPException(status_code=400, detail=f"{platform} is not configured.")

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(cfg["token_url"], data=payload, headers=headers)
        response.raise_for_status()
        return response.json()


async def _fetch_linkedin_account(access_token: str) -> tuple[str | None, str | None, dict]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        profile_response = await client.get("https://api.linkedin.com/v2/me", headers=headers)
        profile_response.raise_for_status()
        profile = profile_response.json()

    account_id = profile.get("id")
    first_name = profile.get("localizedFirstName") or ""
    last_name = profile.get("localizedLastName") or ""
    account_name = " ".join(part for part in [first_name, last_name] if part).strip() or None
    return account_id, account_name, profile


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
        client_id = getattr(settings, f"{item['platform']}_client_id", None)
        client_secret = getattr(settings, f"{item['platform']}_client_secret", None)
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
                "required_env_vars": (
                    [f"{item['platform'].upper()}_CLIENT_ID", f"{item['platform'].upper()}_CLIENT_SECRET"]
                    + ([f"{item['platform'].upper()}_REDIRECT_URI"] if item["platform"] == "linkedin" else [])
                    if cfg.get("auth_url")
                    else []
                ),
                "scopes": cfg.get("scopes", []),
                "connection_error": item.get("connection_error")
                or (None if ready_to_connect else "This integration is not configured yet. Add client credentials in Settings."),
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


@router.post("/{platform}/connect")
async def connect_platform(
    platform: str,
    payload: OAuthConnectPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    business = await _resolve_business_for_user(db, business_id=payload.business_id, current_user=current_user)
    cfg = PLATFORM_CONFIG.get(platform)
    if not cfg:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")

    if not cfg.get("auth_url"):
        return {
            "platform": platform,
            "type": "api_key",
            "message": f"Connect {platform} by providing your API key or credentials.",
            "instructions": _get_api_key_instructions(platform),
        }

    provider_settings = _provider_settings_response(platform)
    if not provider_settings.ready_to_connect:
        return {
            "platform": platform,
            "type": "setup_required",
            "message": provider_settings.message,
            "provider_name": provider_settings.provider_name,
            "redirect_uri": provider_settings.redirect_uri,
            "required_env_vars": provider_settings.required_env_vars,
            "scopes": provider_settings.scopes,
            "ready_to_connect": False,
        }

    state_token, _state_payload = await OAuthStateService().issue(
        provider=platform,
        user_id=str(current_user.id),
        business_id=str(business.id),
        workspace_id=str(business.workspace_id) if business.workspace_id else None,
    )
    scopes = quote_plus(" ".join(cfg["scopes"]))
    auth_url = (
        f"{cfg['auth_url']}?"
        f"response_type=code&"
        f"client_id={quote_plus(str(getattr(settings, f'{platform}_client_id')))}&"
        f"redirect_uri={quote_plus(_provider_redirect_uri(platform) or '')}&"
        f"scope={scopes}&"
        f"state={quote_plus(state_token)}"
    )
    return {
        "platform": platform,
        "type": "oauth",
        "auth_url": auth_url,
        "message": f"Redirect the browser to LinkedIn to connect {provider_settings.provider_name}.",
    }


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
        token_data = await _exchange_oauth_code(platform=platform, code=code, redirect_uri=redirect_uri or "")

        expires_at = None
        if token_data.get("expires_in"):
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=int(token_data["expires_in"]))).isoformat()

        account_id = None
        account_name = None
        provider_payload: dict = {"token": token_data}
        if platform == "linkedin" and token_data.get("access_token"):
            try:
                account_id, account_name, profile = await _fetch_linkedin_account(token_data["access_token"])
                provider_payload["profile"] = profile
            except Exception as profile_exc:
                logger.warning("LinkedIn profile lookup failed: %s", profile_exc)

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
    if not token:
        return {"status": "not_connected", "platform": platform}
    await svc.revoke(token)
    return {"status": "disconnected", "platform": platform}


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


@router.get("/providers/{platform}/settings", response_model=ProviderSettingsResponse)
async def get_provider_settings(
    platform: str,
    current_user: User = Depends(get_current_user),
) -> ProviderSettingsResponse:
    return _provider_settings_response(platform)


@router.post("/providers/{platform}/settings", response_model=ProviderSettingsResponse)
async def save_provider_settings(
    platform: str,
    payload: ProviderSettingsPayload,
    current_user: User = Depends(get_current_user),
) -> ProviderSettingsResponse:
    cfg = PLATFORM_CONFIG.get(platform)
    if not cfg:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")
    if not cfg.get("auth_url"):
        raise HTTPException(status_code=400, detail=f"{platform} does not require OAuth client credentials.")

    normalized_client_id = (payload.client_id or "").strip()
    normalized_client_secret = (payload.client_secret or "").strip()
    if not normalized_client_id or not normalized_client_secret:
        raise HTTPException(status_code=400, detail="Both client ID and client secret are required.")

    env_updates = {
        f"{platform.upper()}_CLIENT_ID": normalized_client_id,
        f"{platform.upper()}_CLIENT_SECRET": normalized_client_secret,
    }
    if platform == "linkedin":
        env_updates["LINKEDIN_REDIRECT_URI"] = _provider_redirect_uri(platform) or ""

    _write_env_values(BACKEND_ENV_PATH, env_updates)
    setattr(settings, f"{platform}_client_id", normalized_client_id)
    setattr(settings, f"{platform}_client_secret", normalized_client_secret)
    if platform == "linkedin":
        settings.linkedin_redirect_uri = _provider_redirect_uri(platform) or settings.linkedin_redirect_uri

    response = _provider_settings_response(platform)
    response.message = "Provider credentials saved to backend/.env and loaded into the running app."
    return response


def _get_api_key_instructions(platform: str) -> str:
    instructions = {
        "sendgrid": "Create an API key at https://app.sendgrid.com/settings/api_keys with Mail Send permission.",
        "wordpress": "Create an Application Password at your WordPress site: Users > Profile > Application Passwords. Use format username:app_password as the API key.",
        "mailchimp": "Get your API key at https://mailchimp.com/help/about-api-keys/.",
    }
    return instructions.get(platform, f"Provide your {platform} API key or credentials.")


def _preview_secret(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip()
    if len(cleaned) <= 8:
        return "*" * len(cleaned)
    return f"{cleaned[:4]}{'*' * max(4, len(cleaned) - 8)}{cleaned[-4:]}"


def _write_env_values(path: Path, updates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    new_lines: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            new_lines.append(line)
            continue
        key, _, _value = line.partition("=")
        env_key = key.strip()
        if env_key in remaining:
            new_lines.append(f"{env_key}={remaining.pop(env_key)}")
        else:
            new_lines.append(line)

    for key, value in remaining.items():
        new_lines.append(f"{key}={value}")

    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
