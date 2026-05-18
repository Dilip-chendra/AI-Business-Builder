"""AI Code Editor API — file system + AI editing + diff generation.

GET  /code-editor/files          — list workspace files
GET  /code-editor/file           — read a file
POST /code-editor/file           — save a file
POST /code-editor/new-file       — create a new empty file
POST /code-editor/ai-edit        — AI modifies code based on instruction
GET  /code-editor/stream-edit    — SSE streaming AI code edit
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.cache import cache
from app.models.business import Business
from app.models.user import User
from app.services.code_version_service import CodeVersionService
from app.services.project_sync_service import ProjectSyncService
from app.services.usage_service import UsageService

router = APIRouter()
logger = logging.getLogger(__name__)


# ── Workspace helpers ─────────────────────────────────────────────────────────

def _get_workspace(business_id: str | None = None) -> Path:
    """Return the workspace path, namespaced by business_id if provided."""
    if business_id:
        # Sanitize business_id — only allow UUID-like strings
        if not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', business_id):
            raise HTTPException(status_code=400, detail="Invalid business_id")
        ws = Path(f"workspace/{business_id}")
    else:
        ws = Path("workspace")
    ws.mkdir(parents=True, exist_ok=True)
    return ws


def _safe_path(filename: str, business_id: str | None = None) -> Path:
    """Resolve path safely within workspace — prevent directory traversal."""
    ws = _get_workspace(business_id)
    safe = (ws / filename).resolve()
    if not str(safe).startswith(str(ws.resolve())):
        raise HTTPException(status_code=400, detail="Invalid file path")
    return safe


def _require_business_id(business_id: str | None) -> str:
    if not business_id:
        raise HTTPException(
            status_code=400,
            detail="A business must be selected before using the code editor.",
        )
    return business_id


async def _load_business(db: AsyncSession, business_id: str, current_user: User) -> Business:
    business = await db.get(Business, UUID(business_id))
    if not business or str(business.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Business not found")
    return business


# ── File system endpoints ─────────────────────────────────────────────────────

@router.get("/files")
async def list_files(
    business_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List all files in the workspace."""
    if not business_id:
        return []
    business = await _load_business(db, business_id, current_user)
    ProjectSyncService(business).ensure_scaffold()
    ws = _get_workspace(business_id)
    files = []
    for path in sorted(ws.rglob("*")):
        if path.is_file() and not path.name.startswith("."):
            rel = path.relative_to(ws)
            ext = path.suffix.lstrip(".")
            lang_map = {
                "tsx": "typescript", "ts": "typescript", "jsx": "javascript",
                "js": "javascript", "py": "python", "css": "css",
                "html": "html", "json": "json", "md": "markdown",
            }
            files.append({
                "path": str(rel).replace("\\", "/"),
                "name": path.name,
                "size": path.stat().st_size,
                "language": lang_map.get(ext, "plaintext"),
            })
    return files


@router.get("/file")
async def read_file(
    path: str = Query(...),
    business_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Read a file from the workspace."""
    await _load_business(db, _require_business_id(business_id), current_user)
    safe = _safe_path(path, _require_business_id(business_id))
    if not safe.exists():
        raise HTTPException(status_code=404, detail="File not found")
    try:
        content = safe.read_text(encoding="utf-8")
        return {"path": path, "content": content}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class SaveFileRequest(BaseModel):
    path: str
    content: str
    business_id: str | None = None


@router.post("/file")
async def save_file(
    payload: SaveFileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Save a file to the workspace."""
    await _load_business(db, _require_business_id(payload.business_id), current_user)
    safe = _safe_path(payload.path, _require_business_id(payload.business_id))
    safe.parent.mkdir(parents=True, exist_ok=True)
    try:
        safe.write_text(payload.content, encoding="utf-8")
        if payload.path in {"studio/business-profile.json", "data/business.json"} and payload.business_id:
            business = await _load_business(db, payload.business_id, current_user)
            data = json.loads(payload.content)
            for field in ("headline", "subheading", "cta_text", "description", "product_pitch", "seo_title", "seo_description", "page_content"):
                if field in data:
                    setattr(business, field, data[field])
            db.add(business)
            await db.commit()
            await db.refresh(business)
            ProjectSyncService(business).sync_business_profile()
            await cache.delete(f"business:{business.id}:{current_user.id}")
            await cache.delete(f"landing:{business.id}")
        await CodeVersionService(db).create_version(
            user_id=str(current_user.id),
            file_path=payload.path,
            content=payload.content,
            source="manual_save",
            business_id=payload.business_id,
        )
        logger.info("File saved: %s by user %s", payload.path, current_user.id)
        return {"status": "saved", "path": payload.path}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


class NewFileRequest(BaseModel):
    path: str  # filename only
    business_id: str | None = None


@router.post("/new-file")
async def create_new_file(
    payload: NewFileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a new empty file in the workspace."""
    # Validate: no ".." or leading "/" or "\"
    if ".." in payload.path or payload.path.startswith("/") or payload.path.startswith("\\"):
        raise HTTPException(status_code=400, detail="Invalid filename: path traversal not allowed")
    if not payload.path.strip():
        raise HTTPException(status_code=400, detail="Filename cannot be empty")
    await _load_business(db, _require_business_id(payload.business_id), current_user)
    safe = _safe_path(payload.path, _require_business_id(payload.business_id))
    safe.parent.mkdir(parents=True, exist_ok=True)
    if safe.exists():
        raise HTTPException(status_code=409, detail="File already exists")
    safe.write_text("", encoding="utf-8")
    ext = safe.suffix.lstrip(".")
    lang_map = {
        "tsx": "typescript", "ts": "typescript", "jsx": "javascript",
        "js": "javascript", "py": "python", "css": "css",
        "html": "html", "json": "json", "md": "markdown",
    }
    return {
        "path": payload.path,
        "name": safe.name,
        "size": 0,
        "language": lang_map.get(ext, "plaintext"),
    }


# ── AI editing endpoints ──────────────────────────────────────────────────────

class AIEditRequest(BaseModel):
    code: str
    instruction: str
    language: str = "typescript"
    business_id: str | None = None


class CodeSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    workspace_id: str


@router.post("/ai-edit")
async def ai_edit_code(
    payload: AIEditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """AI modifies code based on a natural language instruction.

    Returns: { updated_code, explanation, diff_summary }
    """
    from app.services.ai_service import AIService

    ai = AIService()
    usage_svc = UsageService(db)
    await usage_svc.check_limit(current_user.id, "code_edit")
    if payload.business_id:
        await _load_business(db, payload.business_id, current_user)

    # Use text mode — we want code output, not JSON
    prompt = (
        f"You are a senior software engineer. Modify the code below based on the instruction.\n\n"
        f"STRICT RULES:\n"
        f"- Return ONLY the updated code\n"
        f"- Do NOT include any explanation, markdown, or code fences\n"
        f"- Do NOT add ```{payload.language} or ``` wrappers\n"
        f"- Preserve the existing code structure and formatting\n"
        f"- Make only the changes needed for the instruction\n"
        f"- Keep the code production-ready\n\n"
        f"Language: {payload.language}\n\n"
        f"Instruction: {payload.instruction}\n\n"
        f"Current code:\n{payload.code}"
    )

    try:
        updated = await ai.generate_text(prompt, task_type="coding")
        # Strip any accidental markdown fences
        updated = re.sub(r"^```\w*\n?", "", updated.strip())
        updated = re.sub(r"\n?```$", "", updated.strip())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Generate a brief explanation
    explain_prompt = (
        f"In one sentence, describe what changed in this code edit.\n"
        f"Instruction was: {payload.instruction}\n"
        f"Be specific and concise. No markdown."
    )
    try:
        explanation = await ai.generate_text(explain_prompt, task_type="quick_task")
        explanation = explanation.strip()
        # If AI returned JSON or empty, use a sensible default
        if not explanation or explanation.startswith("{") or explanation.startswith("["):
            explanation = f"Applied: {payload.instruction}"
    except Exception:
        explanation = f"Applied: {payload.instruction}"

    await usage_svc.increment_usage(
        current_user.id,
        "code_edit",
        source="code_editor_ai_edit",
        metadata_json={"instruction": payload.instruction[:200]},
    )
    await usage_svc.increment_usage(
        current_user.id,
        "ai_request",
        source="code_editor_ai_edit",
        metadata_json={"instruction": payload.instruction[:200]},
    )

    return {
        "updated_code": updated,
        "explanation": explanation,
        "original_lines": len(payload.code.splitlines()),
        "updated_lines": len(updated.splitlines()),
    }


@router.post("/search")
async def search_workspace(
    payload: CodeSearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    business = await _load_business(db, payload.workspace_id, current_user)
    sync_service = ProjectSyncService(business)
    sync_service.ensure_scaffold()
    return sync_service.search(payload.query, top_k=max(1, min(payload.top_k, 10)))


class CodeVersionRead(BaseModel):
    id: str
    file_path: str
    source: str
    instruction: str | None
    version_number: int
    created_at: str | None


class RevertVersionRequest(BaseModel):
    version_id: str
    business_id: str | None = None


class DeleteVersionRequest(BaseModel):
    version_id: str


@router.get("/versions")
async def list_code_versions(
    path: str = Query(...),
    business_id: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CodeVersionRead]:
    versions = await CodeVersionService(db).list_versions(str(current_user.id), file_path=path)
    return [
        CodeVersionRead(
            id=str(v.id),
            file_path=v.file_path,
            source=v.source,
            instruction=v.instruction,
            version_number=v.version_number,
            created_at=v.created_at.isoformat() if v.created_at else None,
        )
        for v in versions
    ]


@router.get("/history")
async def list_business_history(
    business_id: str = Query(...),
    limit: int = Query(default=100, ge=1, le=250),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    versions = await CodeVersionService(db).list_versions_for_business(
        str(current_user.id),
        business_id=business_id,
        limit=limit,
    )
    return [
        {
            "id": str(v.id),
            "file_path": v.file_path,
            "source": v.source,
            "instruction": v.instruction,
            "version_number": v.version_number,
            "content_preview": (v.content[:320] + "...") if len(v.content) > 320 else v.content,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "updated_at": v.updated_at.isoformat() if v.updated_at else None,
        }
        for v in versions
    ]


@router.post("/revert")
async def revert_to_version(
    payload: RevertVersionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = CodeVersionService(db)
    version = await svc.get_version(payload.version_id)
    if not version or str(version.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Version not found")

    if version.file_path == "studio/business-profile.json":
        business_id = _require_business_id(payload.business_id)
        business = await _load_business(db, business_id, current_user)
        try:
            data = json.loads(version.content)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Saved studio version is invalid JSON: {exc}") from exc
        for field in ("headline", "subheading", "cta_text", "description", "product_pitch", "seo_title", "seo_description", "page_content"):
            if field in data:
                setattr(business, field, data[field])
        db.add(business)
        await db.commit()
        await db.refresh(business)
        ProjectSyncService(business).sync_business_profile()
        await cache.delete(f"business:{business.id}:{current_user.id}")
        await cache.delete(f"landing:{business.id}")
        restored = await svc.create_version(
            user_id=str(current_user.id),
            business_id=business_id,
            file_path=version.file_path,
            content=version.content,
            source="revert",
            instruction=f"Reverted studio state to version {version.version_number}",
        )
        return {
            "status": "reverted",
            "path": version.file_path,
            "restored_version_id": str(restored.id),
            "restored_version_number": restored.version_number,
        }

    safe = _safe_path(version.file_path, _require_business_id(payload.business_id))
    safe.parent.mkdir(parents=True, exist_ok=True)
    safe.write_text(version.content, encoding="utf-8")

    restored = await svc.create_version(
        user_id=str(current_user.id),
        file_path=version.file_path,
        content=version.content,
        source="revert",
        instruction=f"Reverted to version {version.version_number}",
        business_id=payload.business_id,
    )
    return {
        "status": "reverted",
        "path": version.file_path,
        "restored_version_id": str(restored.id),
        "restored_version_number": restored.version_number,
    }


@router.delete("/version")
async def delete_version(
    payload: DeleteVersionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    svc = CodeVersionService(db)
    version = await svc.get_version(payload.version_id)
    if not version or str(version.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Version not found")
    await svc.delete_version(version)
    return {"status": "deleted", "version_id": payload.version_id}


@router.get("/stream-edit")
async def stream_ai_edit(
    instruction: str = Query(...),
    language: str = Query(default="typescript"),
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream AI code editing token by token (Cursor-like typing effect).

    Note: Groq doesn't support true token streaming via httpx easily,
    so we simulate it by chunking the response.
    """
    from app.core.security import decode_access_token
    from jose import JWTError
    from app.services.ai_service import AIService

    usage_svc = UsageService(db)
    try:
        token_payload = decode_access_token(token)
        user_id = UUID(token_payload["sub"])
        await usage_svc.check_limit(user_id, "code_edit")
    except (JWTError, KeyError):
        async def _err():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Invalid token'})}\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream")
    except HTTPException as exc:
        async def _limit_err():
            yield f"data: {json.dumps({'type': 'error', 'message': exc.detail})}\n\n"
        return StreamingResponse(_limit_err(), media_type="text/event-stream")

    async def _stream():
        yield f"data: {json.dumps({'type': 'start', 'message': 'AI is thinking...'})}\n\n"

        ai = AIService()
        prompt = (
            f"You are a senior software engineer. Modify code based on this instruction.\n"
            f"Return ONLY the updated code. No markdown, no explanation.\n\n"
            f"Language: {language}\nInstruction: {instruction}"
        )

        try:
            result = await ai.generate_text(prompt, task_type="coding")
            result = re.sub(r"^```\w*\n?", "", result.strip())
            result = re.sub(r"\n?```$", "", result.strip())

            # Simulate streaming by sending chunks
            chunk_size = 50
            for i in range(0, len(result), chunk_size):
                chunk = result[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"
                import asyncio
                await asyncio.sleep(0.02)  # typing effect delay

            await usage_svc.increment_usage(
                user_id,
                "code_edit",
                source="code_editor_stream_edit",
                metadata_json={"instruction": instruction[:200]},
            )
            await usage_svc.increment_usage(
                user_id,
                "ai_request",
                source="code_editor_stream_edit",
                metadata_json={"instruction": instruction[:200]},
            )
            yield f"data: {json.dumps({'type': 'complete', 'full_code': result})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
