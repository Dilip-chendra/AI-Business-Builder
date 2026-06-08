"""Authentication service — signup, login, token refresh."""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.security as _security  # import module so monkeypatching works in tests
from app.core.security import create_access_token
from app.models.user import User

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def signup(self, email: str, password: str, full_name: str | None = None) -> User:
        """Create a new user.  Raises ``ValueError`` if email already exists."""
        existing = await self._get_by_email(email)
        if existing:
            raise ValueError("Email already registered")
        user = User(
            email=email.lower().strip(),
            hashed_password=_security.hash_password(password),
            full_name=full_name,
            is_active=True,
            is_verified=False,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        from app.services.context_service import ContextService

        await ContextService(self.db).ensure_initial_context(user)
        logger.info("New user registered  id=%s  email=%s", user.id, user.email)
        return user

    async def login(self, email: str, password: str) -> tuple[User, str]:
        """Authenticate and return (user, access_token).

        Raises ``ValueError`` on bad credentials.
        """
        user = await self._get_by_email(email)
        if not user or not user.hashed_password:
            raise ValueError("Invalid email or password")
        if not _security.verify_password(password, user.hashed_password):
            raise ValueError("Invalid email or password")
        if not user.is_active:
            raise ValueError("Account is disabled")
        token = create_access_token(str(user.id), extra={"email": user.email})
        logger.info("User logged in  id=%s", user.id)
        return user, token

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self.db.get(User, user_id)

    async def _get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.email == email.lower().strip())
        )
        return result.scalar_one_or_none()
