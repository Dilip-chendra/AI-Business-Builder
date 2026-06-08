"""File upload service using Supabase Storage.

Falls back to a local file store when Supabase is not configured so the
feature works in development without cloud credentials.
"""
from __future__ import annotations

import logging
import mimetypes
import os
import uuid
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)

# Local fallback directory
_LOCAL_UPLOAD_DIR = Path("uploads")


class UploadService:
    """Upload files to Supabase Storage or local disk."""

    async def upload_product_image(
        self,
        file_bytes: bytes,
        filename: str,
        content_type: str | None = None,
    ) -> str:
        """Upload an image and return its public URL."""
        ext = Path(filename).suffix or ".jpg"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        content_type = content_type or mimetypes.guess_type(filename)[0] or "image/jpeg"

        if settings.supabase_url and settings.supabase_service_key:
            return await self._upload_supabase(file_bytes, unique_name, content_type)
        return await self._upload_local(file_bytes, unique_name)

    async def _upload_supabase(self, data: bytes, name: str, content_type: str) -> str:
        """Upload to Supabase Storage and return the public URL."""
        import httpx  # already in requirements

        bucket = settings.supabase_storage_bucket
        url = f"{settings.supabase_url}/storage/v1/object/{bucket}/{name}"
        headers = {
            "Authorization": f"Bearer {settings.supabase_service_key}",
            "Content-Type": content_type,
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, content=data, headers=headers)
            response.raise_for_status()

        public_url = f"{settings.supabase_url}/storage/v1/object/public/{bucket}/{name}"
        logger.info("Uploaded to Supabase Storage: %s", public_url)
        return public_url

    async def _upload_local(self, data: bytes, name: str) -> str:
        """Save to local disk and return a relative URL."""
        _LOCAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = _LOCAL_UPLOAD_DIR / name
        dest.write_bytes(data)
        url = f"{settings.backend_url}/uploads/{name}"
        logger.info("Saved file locally: %s", url)
        return url
