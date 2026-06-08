"""Service layer for code version history."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.code_version import CodeVersion


class CodeVersionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_version(
        self,
        user_id: str,
        file_path: str,
        content: str,
        source: str = "manual",
        instruction: str | None = None,
        business_id: str | None = None,
    ) -> CodeVersion:
        max_ver_result = await self.db.execute(
            select(func.max(CodeVersion.version_number)).where(
                CodeVersion.user_id == str(user_id),
                CodeVersion.file_path == file_path,
            )
        )
        next_version = (max_ver_result.scalar() or 0) + 1

        version = CodeVersion(
            user_id=str(user_id),
            business_id=str(business_id) if business_id else None,
            file_path=file_path,
            content=content,
            source=source,
            instruction=instruction,
            version_number=next_version,
            diff_summary={"chars": len(content), "lines": len(content.splitlines())},
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def list_versions(self, user_id: str, file_path: str, limit: int = 30) -> list[CodeVersion]:
        result = await self.db.execute(
            select(CodeVersion)
            .where(CodeVersion.user_id == str(user_id), CodeVersion.file_path == file_path)
            .order_by(CodeVersion.version_number.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_versions_for_business(
        self,
        user_id: str,
        business_id: str,
        limit: int = 100,
    ) -> list[CodeVersion]:
        result = await self.db.execute(
            select(CodeVersion)
            .where(
                CodeVersion.user_id == str(user_id),
                CodeVersion.business_id == str(business_id),
            )
            .order_by(CodeVersion.created_at.desc(), CodeVersion.version_number.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_version(self, version_id: str) -> CodeVersion | None:
        return await self.db.get(CodeVersion, version_id)

    async def delete_version(self, version: CodeVersion) -> None:
        await self.db.delete(version)
        await self.db.commit()
