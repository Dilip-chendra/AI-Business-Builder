"""Embedding / RAG routes for AI Code Editor codebase search.

POST /code-editor/search  — semantic search over indexed workspace
POST /code-editor/index   — trigger workspace re-indexing
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.embedding_service import EmbeddingService

router = APIRouter()
logger = logging.getLogger(__name__)

# Default workspace ID for single-tenant dev mode
_DEFAULT_WORKSPACE = "default"


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)
    workspace_id: str = Field(default=_DEFAULT_WORKSPACE)


class IndexRequest(BaseModel):
    workspace_id: str = Field(default=_DEFAULT_WORKSPACE)
    workspace_path: str = Field(default="workspace")


@router.post("/search")
async def search_codebase(
    payload: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Semantic search over the indexed workspace.

    Returns top-K relevant code chunks for the given query.
    Used by the AI Code Editor to inject codebase context into AI prompts.
    """
    svc = EmbeddingService(db)
    results = await svc.search(
        workspace_id=payload.workspace_id,
        query=payload.query,
        top_k=payload.top_k,
    )
    return results


@router.post("/index")
async def index_workspace(
    payload: IndexRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Trigger re-indexing of the workspace for RAG search.

    Deletes existing embeddings and re-indexes all files.
    """
    svc = EmbeddingService(db)
    stats = await svc.index_workspace(
        workspace_id=payload.workspace_id,
        workspace_path=payload.workspace_path,
    )
    logger.info(
        "Workspace indexed  user=%s  workspace=%s  files=%d  chunks=%d",
        current_user.id, payload.workspace_id, stats["files"], stats["indexed"],
    )
    return {"status": "indexed", **stats}
