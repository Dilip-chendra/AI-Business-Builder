from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_integration import IntegrationActionLog


class IntegrationAuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def _as_uuid(value: UUID | str | None) -> UUID | None:
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

    async def record(
        self,
        *,
        user_id: UUID | str,
        business_id: UUID | str | None,
        provider: str,
        action: str,
        status: str,
        message: str | None = None,
        metadata: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> IntegrationActionLog:
        log = IntegrationActionLog(
            user_id=self._as_uuid(user_id),
            business_id=self._as_uuid(business_id),
            provider=provider,
            action=action,
            status=status,
            message=message,
            metadata_json=metadata or {},
        )
        self.db.add(log)
        if commit:
            await self.db.commit()
            await self.db.refresh(log)
        return log
