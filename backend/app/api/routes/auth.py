"""Authentication endpoints — signup, login, me, update profile."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.email_service import EmailService

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=160)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None
    is_active: bool
    is_verified: bool
    stripe_publishable_key: str | None = None
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=160)
    email: EmailStr | None = None
    stripe_publishable_key: str | None = Field(default=None, max_length=255)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: SignupRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Register a new user and return an access token."""
    try:
        user = await AuthService(db).signup(
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    from app.core.security import create_access_token
    token = create_access_token(str(user.id), extra={"email": user.email})

    # Send welcome email in background (no-op if SMTP not configured)
    background_tasks.add_task(
        EmailService().send_welcome,
        to=user.email,
        full_name=user.full_name,
    )

    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Authenticate and return an access token."""
    try:
        _, token = await AuthService(db).login(payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> UserRead:
    """Return the currently authenticated user's profile."""
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserRead:
    """Update the current user's profile fields."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return UserRead.model_validate(current_user)


class ApiKeysUpdate(BaseModel):
    groq_api_key: str | None = None
    hf_api_key: str | None = None
    openai_api_key: str | None = None
    sendgrid_api_key: str | None = None

class ApiKeysRead(BaseModel):
    groq_api_key: str | None = None
    hf_api_key: str | None = None
    openai_api_key: str | None = None
    sendgrid_api_key: str | None = None

def _mask_key(key: str | None) -> str | None:
    if not key:
        return None
    if len(key) <= 8:
        return "****"
    return key[:4] + "*" * (len(key) - 8) + key[-4:]

from sqlalchemy import select
from app.models.user_ai_settings import UserAISettings
from cryptography.fernet import Fernet
import base64
import hashlib

def _get_fernet() -> Fernet:
    from app.core.config import settings
    # Derive a valid 32-byte url-safe base64 key from jwt_secret_key
    key_bytes = hashlib.sha256(settings.jwt_secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))

@router.get("/api-keys", response_model=ApiKeysRead)
async def get_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeysRead:
    res = await db.execute(select(UserAISettings).where(UserAISettings.user_id == str(current_user.id)))
    settings_records = res.scalars().all()
    
    keys = {}
    f = _get_fernet()
    for rec in settings_records:
        if rec.api_key_encrypted:
            try:
                decrypted = f.decrypt(rec.api_key_encrypted.encode()).decode()
                keys[f"{rec.provider}_api_key"] = _mask_key(decrypted)
            except Exception:
                pass
    return ApiKeysRead(**keys)

@router.post("/api-keys", response_model=ApiKeysRead)
async def update_api_keys(
    payload: ApiKeysUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiKeysRead:
    res = await db.execute(select(UserAISettings).where(UserAISettings.user_id == str(current_user.id)))
    settings_records = res.scalars().all()
    existing_by_provider = {rec.provider: rec for rec in settings_records}
    
    f = _get_fernet()
    
    for provider, key_val in [
        ("groq", payload.groq_api_key),
        ("hf", payload.hf_api_key),
        ("openai", payload.openai_api_key),
        ("sendgrid", payload.sendgrid_api_key)
    ]:
        if key_val and not key_val.startswith("****"):
            encrypted = f.encrypt(key_val.encode()).decode()
            if provider in existing_by_provider:
                existing_by_provider[provider].api_key_encrypted = encrypted
            else:
                new_rec = UserAISettings(user_id=str(current_user.id), provider=provider, api_key_encrypted=encrypted)
                db.add(new_rec)
    
    await db.commit()
    
    # Return masked
    return await get_api_keys(current_user, db)
