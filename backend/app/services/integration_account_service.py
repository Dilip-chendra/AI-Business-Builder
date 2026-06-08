from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.integration_account import IntegrationAccount
from app.services.oauth_manager_service import _decrypt, _encrypt


class IntegrationAccountService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        from app.core.config import settings

        self._secret = settings.encryption_key

    def _db_id(self, value: UUID | str | None) -> UUID | None:
        return self._as_uuid(value)

    def _dialect_name(self) -> str:
        bind = None
        try:
            bind = self.db.get_bind()
        except Exception:
            bind = getattr(self.db, "bind", None)
        return getattr(getattr(bind, "dialect", None), "name", "") or "sqlite"

    def _uses_uuid_text_fallback(self) -> bool:
        return self._dialect_name() != "postgresql"

    def _uuid_filter(self, column: Any, value: UUID | str | None):
        parsed = self._as_uuid(value)
        if parsed is None:
            return column.is_(None)
        if self._dialect_name() == "sqlite":
            compact = parsed.hex
            normalized_column = func.lower(func.replace(cast(column, String), "-", ""))
            return normalized_column == compact.lower()
        return column == parsed

    @staticmethod
    def _uuid_text(value: UUID | str | None) -> str | None:
        parsed = IntegrationAccountService._as_uuid(value)
        if parsed is None:
            return None
        return parsed.hex.lower()

    @classmethod
    def _same_uuidish(cls, left: UUID | str | None, right: UUID | str | None) -> bool:
        return cls._uuid_text(left) == cls._uuid_text(right)

    @staticmethod
    def _as_uuid(value: UUID | str | None) -> UUID | None:
        if value is None:
            return None
        if isinstance(value, dict):
            value = value.get("id") or value.get("business_id") or value.get("user_id")
        elif not isinstance(value, (UUID, str)) and hasattr(value, "id"):
            value = getattr(value, "id")
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

    async def get(self, *, user_id: UUID | str, business_id: UUID | str | None, platform: str) -> IntegrationAccount | None:
        if self._uses_uuid_text_fallback():
            result = await self.db.execute(
                select(IntegrationAccount).where(IntegrationAccount.platform == platform)
            )
            accounts = list(result.scalars().all())
            for account in accounts:
                if not self._same_uuidish(account.user_id, user_id):
                    continue
                if business_id is not None and not self._same_uuidish(account.business_id, business_id):
                    continue
                if business_id is None and account.business_id is not None:
                    continue
                return account
            return None

        stmt = select(IntegrationAccount).where(
            self._uuid_filter(IntegrationAccount.user_id, user_id),
            IntegrationAccount.platform == platform,
        )
        if business_id:
            stmt = stmt.where(self._uuid_filter(IntegrationAccount.business_id, business_id))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_business(self, *, user_id: UUID | str, business_id: UUID | str | None) -> list[IntegrationAccount]:
        if self._uses_uuid_text_fallback():
            result = await self.db.execute(select(IntegrationAccount).order_by(IntegrationAccount.updated_at.desc()))
            accounts = []
            for account in result.scalars().all():
                if not self._same_uuidish(account.user_id, user_id):
                    continue
                if business_id is not None and not self._same_uuidish(account.business_id, business_id):
                    continue
                accounts.append(account)
            return accounts

        stmt = (
            select(IntegrationAccount)
            .where(self._uuid_filter(IntegrationAccount.user_id, user_id))
            .order_by(IntegrationAccount.updated_at.desc())
        )
        if business_id:
            stmt = stmt.where(self._uuid_filter(IntegrationAccount.business_id, business_id))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def save(
        self,
        *,
        user_id: UUID | str,
        workspace_id: UUID | str | None,
        business_id: UUID | str | None,
        platform: str,
        login_identifier: str | None,
        password: str | None,
        phone: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> IntegrationAccount:
        normalized_user_id = self._db_id(user_id)
        normalized_workspace_id = self._db_id(workspace_id)
        normalized_business_id = self._db_id(business_id)
        account = await self.get(user_id=user_id, business_id=business_id, platform=platform)
        if account is None:
            account = IntegrationAccount(
                user_id=normalized_user_id,
                workspace_id=normalized_workspace_id,
                business_id=normalized_business_id,
                platform=platform,
            )
            self.db.add(account)

        if login_identifier is not None and "*" not in login_identifier:
            account.login_identifier_enc = _encrypt(login_identifier, self._secret)
        if password is not None:
            account.password_enc = _encrypt(password, self._secret)
        if phone is not None and "*" not in phone:
            account.phone_enc = _encrypt(phone, self._secret)
        account.workspace_id = normalized_workspace_id
        account.business_id = normalized_business_id
        account.status = "configured"
        account.last_error = None
        account.metadata_json = metadata or {}
        account.last_active_at = datetime.now(timezone.utc).isoformat()
        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def mark_test_result(self, account: IntegrationAccount, *, ok: bool, error: str | None = None) -> IntegrationAccount:
        account.last_tested_at = datetime.now(timezone.utc).isoformat()
        account.status = "connected" if ok else "error"
        account.last_error = error
        await self.db.commit()
        await self.db.refresh(account)
        return account

    async def delete(self, account: IntegrationAccount) -> None:
        await self.db.delete(account)
        await self.db.commit()

    def reveal(self, account: IntegrationAccount) -> dict[str, Any]:
        return {
            "id": str(account.id),
            "platform": account.platform,
            "status": account.status,
            "email": _decrypt(account.login_identifier_enc, self._secret) if account.login_identifier_enc else None,
            "phone": _decrypt(account.phone_enc, self._secret) if account.phone_enc else None,
            "password": _decrypt(account.password_enc, self._secret) if account.password_enc else None,
            "last_active_at": account.last_active_at,
            "last_tested_at": account.last_tested_at,
            "last_error": account.last_error,
            "metadata": account.metadata_json or {},
        }

    def summary(self, account: IntegrationAccount) -> dict[str, Any]:
        revealed = self.reveal(account)
        email = revealed["email"]
        phone = revealed["phone"]
        return {
            "id": revealed["id"],
            "platform": account.platform,
            "status": account.status,
            "identifier_preview": self._mask(email or phone or ""),
            "last_active_at": account.last_active_at,
            "last_tested_at": account.last_tested_at,
            "last_error": account.last_error,
        }

    @staticmethod
    def _mask(value: str) -> str:
        if not value:
            return ""
        if "@" in value:
            name, domain = value.split("@", 1)
            return f"{name[:2]}***@{domain}"
        return f"{value[:3]}***{value[-2:]}" if len(value) > 5 else "*" * len(value)
