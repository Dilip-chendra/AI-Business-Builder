"""Embedding Service — chunk, embed, index, and search workspace code for RAG.

Uses a simple TF-IDF-style cosine similarity over term frequency vectors
so there is no external embedding API dependency. For production, swap
_embed() to call an embedding API (OpenAI, Cohere, etc.).
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
from collections import Counter
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.code_embedding import CodeEmbedding

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 40   # lines per chunk
_VOCAB_SIZE = 256  # fixed-length embedding vector


def _tokenize(text: str) -> list[str]:
    """Split code into lowercase tokens."""
    return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())


def _embed(text: str) -> list[float]:
    """Produce a fixed-length TF vector from text tokens.

    Each dimension corresponds to a hash bucket mod VOCAB_SIZE.
    Normalised to unit length for cosine similarity.
    """
    tokens = _tokenize(text)
    counts: Counter[int] = Counter()
    for tok in tokens:
        bucket = int(hashlib.md5(tok.encode()).hexdigest(), 16) % _VOCAB_SIZE
        counts[bucket] += 1
    vec = [float(counts.get(i, 0)) for i in range(_VOCAB_SIZE)]
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _vec_to_csv(vec: list[float]) -> str:
    return ",".join(f"{v:.6f}" for v in vec)


def _csv_to_vec(csv: str) -> list[float]:
    if not csv:
        return [0.0] * _VOCAB_SIZE
    return [float(x) for x in csv.split(",")]


class EmbeddingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def chunk_file(self, file_path: str, content: str) -> list[dict]:
        """Split a file into overlapping line chunks."""
        lines = content.splitlines()
        chunks = []
        for i in range(0, max(1, len(lines)), _CHUNK_SIZE):
            chunk_lines = lines[i: i + _CHUNK_SIZE]
            chunks.append({
                "file_path": file_path,
                "chunk_index": i // _CHUNK_SIZE,
                "content": "\n".join(chunk_lines),
            })
        return chunks

    async def index_workspace(self, workspace_id: str, workspace_path: str = "workspace") -> dict:
        """Index all files in the workspace directory."""
        ws = Path(workspace_path)
        if not ws.exists():
            return {"indexed": 0, "files": 0}

        # Delete existing embeddings for this workspace
        await self.db.execute(
            delete(CodeEmbedding).where(CodeEmbedding.workspace_id == workspace_id)
        )

        indexed = 0
        files_processed = 0
        for path in sorted(ws.rglob("*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                rel = str(path.relative_to(ws)).replace("\\", "/")
                chunks = self.chunk_file(rel, content)
                for chunk in chunks:
                    vec = _embed(chunk["content"])
                    emb = CodeEmbedding(
                        workspace_id=workspace_id,
                        file_path=chunk["file_path"],
                        chunk_index=chunk["chunk_index"],
                        content=chunk["content"],
                        embedding_csv=_vec_to_csv(vec),
                    )
                    self.db.add(emb)
                    indexed += 1
                files_processed += 1
            except Exception as exc:
                logger.warning("Failed to index %s: %s", path, exc)

        await self.db.commit()
        logger.info("Indexed workspace=%s files=%d chunks=%d", workspace_id, files_processed, indexed)
        return {"indexed": indexed, "files": files_processed}

    async def search(self, workspace_id: str, query: str, top_k: int = 5) -> list[dict]:
        """Return top-K most relevant code chunks for a query."""
        query_vec = _embed(query)

        result = await self.db.execute(
            select(CodeEmbedding).where(CodeEmbedding.workspace_id == workspace_id)
        )
        embeddings = result.scalars().all()

        if not embeddings:
            return []

        scored = []
        for emb in embeddings:
            vec = _csv_to_vec(emb.embedding_csv)
            score = _cosine(query_vec, vec)
            scored.append((score, emb))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "file_path": emb.file_path,
                "chunk_index": emb.chunk_index,
                "content": emb.content,
                "score": round(score, 4),
            }
            for score, emb in scored[:top_k]
        ]
