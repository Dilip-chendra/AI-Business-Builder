"""Image Generation Service — DALL-E 3 primary, Stability AI fallback."""
from __future__ import annotations

import base64
import logging
import uuid
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_UPLOADS_DIR = Path("uploads/generated")
_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


class ImageGenerationError(RuntimeError):
    """Raised when all image generation providers fail."""


class ImageGenerationService:
    """Generate images via OpenAI DALL-E 3 with Stability AI fallback."""

    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        brand: object | None = None,
    ) -> str:
        """Generate an image and save it to uploads/generated/.

        Returns the relative file path (e.g. 'uploads/generated/abc123.png').
        Raises ImageGenerationError if all providers fail.
        """
        from app.core.config import settings

        full_prompt = self._build_brand_prompt(prompt, brand) if brand else prompt

        # Try DALL-E 3 first
        if getattr(settings, "openai_api_key", None):
            try:
                path = await self._dalle3(full_prompt, size, settings.openai_api_key)
                logger.info("Image generated via DALL-E 3  size=%s", size)
                return path
            except Exception as exc:
                logger.warning("DALL-E 3 failed: %s — trying Stability AI", exc)

        # Fallback: Stability AI
        if getattr(settings, "stability_api_key", None):
            try:
                path = await self._stability(full_prompt, size, settings.stability_api_key)
                logger.info("Image generated via Stability AI  size=%s", size)
                return path
            except Exception as exc:
                logger.warning("Stability AI failed: %s", exc)

        raise ImageGenerationError(
            "No image generation provider available. "
            "Set OPENAI_API_KEY or STABILITY_API_KEY in .env."
        )

    def _build_brand_prompt(self, base_prompt: str, brand: object) -> str:
        """Inject brand attributes into the image generation prompt."""
        parts = [base_prompt]
        if hasattr(brand, "primary_color") and brand.primary_color:
            parts.append(f"Use brand color {brand.primary_color} as the primary accent.")
        if hasattr(brand, "tone_of_voice") and brand.tone_of_voice:
            parts.append(f"Visual style: {brand.tone_of_voice}.")
        if hasattr(brand, "logo_description") and brand.logo_description:
            parts.append(f"Include brand element: {brand.logo_description}.")
        return " ".join(parts)

    async def _dalle3(self, prompt: str, size: str, api_key: str) -> str:
        """Call OpenAI DALL-E 3 API and save the result."""
        # Map size to DALL-E 3 supported sizes
        size_map = {
            "1024x1024": "1024x1024",
            "1200x628": "1792x1024",   # landscape banner
            "1080x1920": "1024x1792",  # portrait story
            "1080x1080": "1024x1024",
            "300x250": "1024x1024",    # DALL-E doesn't support small sizes
        }
        dalle_size = size_map.get(size, "1024x1024")

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "dall-e-3",
                    "prompt": prompt[:4000],
                    "n": 1,
                    "size": dalle_size,
                    "response_format": "b64_json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            b64 = data["data"][0]["b64_json"]
            return self._save_b64(b64)

    async def _stability(self, prompt: str, size: str, api_key: str) -> str:
        """Call Stability AI API and save the result."""
        width, height = 1024, 1024
        if "x" in size:
            try:
                w, h = size.split("x")
                width = min(int(w), 1024)
                height = min(int(h), 1024)
                # Stability requires multiples of 64
                width = (width // 64) * 64 or 1024
                height = (height // 64) * 64 or 1024
            except Exception:
                pass

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "text_prompts": [{"text": prompt[:2000], "weight": 1.0}],
                    "cfg_scale": 7,
                    "height": height,
                    "width": width,
                    "samples": 1,
                    "steps": 30,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            b64 = data["artifacts"][0]["base64"]
            return self._save_b64(b64)

    def _save_b64(self, b64_data: str) -> str:
        """Decode base64 image data and save to disk. Returns relative path."""
        image_bytes = base64.b64decode(b64_data)
        filename = f"{uuid.uuid4().hex}.png"
        filepath = _UPLOADS_DIR / filename
        filepath.write_bytes(image_bytes)
        return f"uploads/generated/{filename}"
