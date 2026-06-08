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
import difflib
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


def _normalize_ai_code_output(raw: str, *, original: str, source_path: str, language: str) -> str:
    """Extract complete code from common LLM response shapes and reject prose-only output."""
    text = (raw or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="AI edit returned an empty response.")

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            for key in ("updated_code", "code", "content", "file"):
                value = parsed.get(key)
                if isinstance(value, str) and value.strip():
                    text = value.strip()
                    break
    except Exception:
        pass

    fences = re.findall(r"```(?:[a-zA-Z0-9_+-]+)?\s*\n([\s\S]*?)```", text)
    if fences:
        text = max((item.strip() for item in fences), key=len)
    else:
        text = re.sub(r"^```\w*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()

    lower = text.lower().lstrip()
    prose_prefixes = (
        "here is",
        "here's",
        "sure,",
        "i updated",
        "the updated code",
        "explanation:",
    )
    if any(lower.startswith(prefix) for prefix in prose_prefixes):
        raise HTTPException(
            status_code=422,
            detail="AI edit returned explanation text instead of a complete updated file.",
        )
    if "```" in text:
        raise HTTPException(status_code=422, detail="AI edit still contains markdown fences after cleanup.")
    if not text or text == original:
        raise HTTPException(status_code=422, detail="AI edit did not produce a concrete file change.")

    _validate_complete_code_edit(text, original=original, source_path=source_path, language=language)
    return text


def _validate_complete_code_edit(updated: str, *, original: str, source_path: str, language: str) -> None:
    """Prevent partial snippets or prose from being persisted as production files."""
    path = source_path.lower()
    lang = language.lower()
    first_line = updated.strip().splitlines()[0].strip().lower() if updated.strip() else ""
    if first_line.startswith(("//", "#")) and len(updated.splitlines()) < max(4, len(original.splitlines()) // 3):
        raise HTTPException(status_code=422, detail="AI edit returned a partial snippet, not the complete file.")
    if path.endswith((".tsx", ".jsx")) or lang in {"typescript", "javascript", "tsx", "jsx"}:
        original_has_export = "export " in original
        if original_has_export and "export " not in updated:
            raise HTTPException(status_code=422, detail="AI edit removed the component export; refusing to save an incomplete file.")
        if path.endswith((".tsx", ".jsx")) and "<" in original and ">" in original and not re.search(r"<[A-Za-z][\w.:-]*", updated):
            raise HTTPException(status_code=422, detail="AI edit does not look like a complete React/TSX file.")
    if path.endswith(".json"):
        try:
            json.loads(updated)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail=f"AI edit produced invalid JSON: {exc}") from exc


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
    business = await _load_business(db, _require_business_id(business_id), current_user)
    ProjectSyncService(business).ensure_scaffold()
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
    path: str | None = None


class GenerateTestsRequest(BaseModel):
    path: str
    code: str
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

    Returns: { updated_code, explanation, diff_summary, saved, version_id }
    """
    from app.services.ai_service import AIService

    ai = AIService()
    usage_svc = UsageService(db)
    await usage_svc.check_limit(current_user.id, "code_edit")
    await usage_svc.check_limit(current_user.id, "ai_request")
    source_path = payload.path.strip() if payload.path else "unsaved buffer"
    current_code = payload.code
    safe_file: Path | None = None
    if payload.business_id:
        business = await _load_business(db, payload.business_id, current_user)
        ProjectSyncService(business).ensure_scaffold()
        if payload.path:
            safe_file = _safe_path(payload.path, payload.business_id)
            if not safe_file.exists():
                raise HTTPException(status_code=404, detail="Selected file not found")
            disk_code = safe_file.read_text(encoding="utf-8")
            # Prefer the user's current editor buffer when it contains unsaved changes.
            current_code = payload.code if payload.code and payload.code != disk_code else disk_code

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
        f"Workspace file path: {source_path}\n"
        f"Language: {payload.language}\n\n"
        f"Instruction: {payload.instruction}\n\n"
        f"Current code:\n{current_code}"
    )

    try:
        raw_updated = await ai.generate_text(prompt, task_type="code_edit_fast")
        updated = _normalize_ai_code_output(
            raw_updated,
            original=current_code,
            source_path=source_path,
            language=payload.language,
        )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
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

    saved = False
    version_id = None
    version_number = None
    unified_diff = "\n".join(
        difflib.unified_diff(
            current_code.splitlines(),
            updated.splitlines(),
            fromfile=f"{source_path}:before",
            tofile=f"{source_path}:after",
            lineterm="",
        )
    )
    if safe_file is not None and payload.business_id and payload.path:
        safe_file.write_text(updated, encoding="utf-8")
        business = await _load_business(db, payload.business_id, current_user)
        if payload.path in {"studio/business-profile.json", "data/business.json"}:
            data = json.loads(updated)
            for field in ("headline", "subheading", "cta_text", "description", "product_pitch", "seo_title", "seo_description", "page_content"):
                if field in data:
                    setattr(business, field, data[field])
            db.add(business)
            await db.commit()
            await db.refresh(business)
            ProjectSyncService(business).sync_business_profile()
        await cache.delete(f"business:{business.id}:{current_user.id}")
        await cache.delete(f"landing:{business.id}")
        version = await CodeVersionService(db).create_version(
            user_id=str(current_user.id),
            business_id=str(business.id),
            file_path=payload.path,
            content=updated,
            source="code_editor_ai_edit",
            instruction=payload.instruction,
        )
        version_id = str(version.id)
        version_number = version.version_number
        saved = True
        logger.info(
            "AI Code Editor patch applied user_id=%s business_id=%s path=%s version_id=%s",
            current_user.id,
            business.id,
            payload.path,
            version_id,
        )

    await usage_svc.increment_usage(
        current_user.id,
        "code_edit",
        source="code_editor_ai_edit",
        metadata_json={"instruction": payload.instruction[:200], "path": source_path},
    )
    await usage_svc.increment_usage(
        current_user.id,
        "ai_request",
        source="code_editor_ai_edit",
        metadata_json={"instruction": payload.instruction[:200], "path": source_path},
    )

    return {
        "updated_code": updated,
        "explanation": explanation,
        "path": source_path,
        "saved": saved,
        "version_id": version_id,
        "version_number": version_number,
        "changed_files": [source_path] if saved else [],
        "diff_summary": unified_diff,
        "original_lines": len(current_code.splitlines()),
        "updated_lines": len(updated.splitlines()),
    }


def _test_path_for(source_path: str) -> str:
    clean = source_path.replace("\\", "/").strip("/")
    path = Path(clean)
    suffix = path.suffix or ".ts"
    stem = path.stem
    if clean.startswith("app/"):
        return str(Path("__tests__") / path.with_suffix(f".test{suffix}")).replace("\\", "/")
    if clean.startswith("components/"):
        return str(Path("__tests__") / path.with_suffix(f".test{suffix}")).replace("\\", "/")
    return str(path.with_name(f"{stem}.test{suffix}")).replace("\\", "/")


@router.post("/generate-tests")
async def generate_tests(
    payload: GenerateTestsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate and persist a real test file for the selected workspace file."""
    from app.services.ai_service import AIService

    business_id = _require_business_id(payload.business_id)
    await _load_business(db, business_id, current_user)
    source_file = _safe_path(payload.path, business_id)
    if not source_file.exists():
        raise HTTPException(status_code=404, detail="Source file not found")

    test_path = _test_path_for(payload.path)
    test_file = _safe_path(test_path, business_id)
    source_import = os.path.relpath(source_file.with_suffix(""), start=test_file.parent).replace("\\", "/")
    if not source_import.startswith("."):
        source_import = f"./{source_import}"

    usage_svc = UsageService(db)
    await usage_svc.check_limit(current_user.id, "code_edit")
    await usage_svc.check_limit(current_user.id, "ai_request")

    prompt = (
        "You are a senior test engineer. Generate a production-ready test file for the source code below.\n\n"
        "STRICT RULES:\n"
        "- Return ONLY the test file code.\n"
        "- Do not include markdown, commentary, or code fences.\n"
        "- Use the most likely local stack for this workspace: React Testing Library/Jest style for TSX/JSX, unit tests for TS/JS, pytest for Python.\n"
        "- Mock external APIs and browser globals where needed.\n"
        "- Include useful assertions that verify behavior, not snapshots only.\n\n"
        f"Source path: {payload.path}\n"
        f"Test path to create: {test_path}\n"
        f"Relative import path from the test file to the source module: {source_import}\n"
        f"Language: {payload.language}\n\n"
        f"Source code:\n{payload.code}"
    )

    try:
        tests = await AIService().generate_text(prompt, task_type="coding")
        tests = re.sub(r"^```\w*\n?", "", tests.strip())
        tests = re.sub(r"\n?```$", "", tests.strip())
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text(tests, encoding="utf-8")
    version = await CodeVersionService(db).create_version(
        user_id=str(current_user.id),
        file_path=test_path,
        content=tests,
        source="ai_tests",
        instruction=f"Generated tests for {payload.path}",
        business_id=business_id,
    )
    await usage_svc.increment_usage(
        current_user.id,
        "code_edit",
        business_id=UUID(business_id),
        source="code_editor_generate_tests",
        metadata_json={"source_path": payload.path, "test_path": test_path},
    )
    await usage_svc.increment_usage(
        current_user.id,
        "ai_request",
        business_id=UUID(business_id),
        source="code_editor_generate_tests",
        metadata_json={"source_path": payload.path},
    )

    return {
        "status": "created",
        "source_path": payload.path,
        "path": test_path,
        "content": tests,
        "version_id": str(version.id),
        "version_number": version.version_number,
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
    path: str | None = Query(default=None),
    business_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Stream an operational AI code edit with explicit execution phases."""
    from app.core.security import decode_access_token
    from jose import JWTError
    from app.services.ai_service import AIService

    usage_svc = UsageService(db)
    source_code = ""
    try:
        token_payload = decode_access_token(token)
        user_id = UUID(token_payload["sub"])
        current_user = await db.get(User, user_id)
        if not current_user:
            raise JWTError("User not found")
        await usage_svc.check_limit(user_id, "code_edit")
        await usage_svc.check_limit(user_id, "ai_request")
        if business_id:
            business = await _load_business(db, business_id, current_user)
            ProjectSyncService(business).ensure_scaffold()
        if path and business_id:
            source_file = _safe_path(path, business_id)
            if not source_file.exists():
                raise HTTPException(status_code=404, detail="Source file not found")
            source_code = source_file.read_text(encoding="utf-8")
        if not source_code:
            raise HTTPException(status_code=400, detail="Select a real workspace file before streaming an AI edit.")
    except (JWTError, KeyError):
        async def _err():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Invalid token'})}\n\n"
        return StreamingResponse(_err(), media_type="text/event-stream")
    except HTTPException as exc:
        async def _limit_err():
            yield f"data: {json.dumps({'type': 'error', 'message': exc.detail})}\n\n"
        return StreamingResponse(_limit_err(), media_type="text/event-stream")

    async def _stream():
        source_label = path or "selected file"
        yield f"data: {json.dumps({'type': 'phase', 'phase': 'context', 'message': f'Loaded {source_label} from the workspace.'})}\n\n"
        yield f"data: {json.dumps({'type': 'phase', 'phase': 'generating', 'message': 'AI is generating a real code edit.'})}\n\n"

        ai = AIService()
        prompt = (
            f"You are a senior software engineer. Modify code based on this instruction.\n"
            f"Return ONLY the complete updated code. No markdown, no explanation.\n\n"
            f"Language: {language}\n"
            f"File path: {path or 'selected file'}\n"
            f"Instruction: {instruction}\n\n"
            f"Current code:\n{source_code}"
        )

        try:
            raw_result = await ai.generate_text(prompt, task_type="coding")
            result = _normalize_ai_code_output(
                raw_result,
                original=source_code,
                source_path=path or "selected file",
                language=language,
            )

            yield f"data: {json.dumps({'type': 'phase', 'phase': 'streaming', 'message': 'Streaming updated file content for review.'})}\n\n"
            chunk_size = 50
            for i in range(0, len(result), chunk_size):
                chunk = result[i:i + chunk_size]
                yield f"data: {json.dumps({'type': 'chunk', 'data': chunk})}\n\n"
                import asyncio
                await asyncio.sleep(0.02)

            await usage_svc.increment_usage(
                user_id,
                "code_edit",
                source="code_editor_stream_edit",
                metadata_json={"instruction": instruction[:200], "path": path or "selected file"},
            )
            await usage_svc.increment_usage(
                user_id,
                "ai_request",
                source="code_editor_stream_edit",
                metadata_json={"instruction": instruction[:200], "path": path or "selected file"},
            )
            yield f"data: {json.dumps({'type': 'complete', 'full_code': result, 'path': path})}\n\n"

        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
