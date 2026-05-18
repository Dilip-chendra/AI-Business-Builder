"""Code Embedding model — vector chunks for RAG-based codebase search."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class CodeEmbedding(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "code_embeddings"

    workspace_id: Mapped[str] = mapped_column(
        String(36), index=True, nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Embedding stored as comma-separated floats (portable, no binary blob issues on SQLite)
    embedding_csv: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "workspace_id": self.workspace_id,
            "file_path": self.file_path,
            "chunk_index": self.chunk_index,
            "content": self.content[:200],
        }
