"""Image Generation Service - Hugging Face Inference image generation."""
from __future__ import annotations

import base64
import logging
import os
import uuid
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_UPLOADS_DIR = Path("uploads/generated")
_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
_DEFAULT_HF_IMAGE_MODELS = [
    "stabilityai/stable-diffusion-xl-base-1.0",
    "runwayml/stable-diffusion-v1-5",
    "prompthero/openjourney",
    "segmind/SSD-1B",
]


class ImageGenerationError(RuntimeError):
    """Raised when Hugging Face image generation fails."""


class ImageGenerationService:
    """Generate campaign images via Hugging Face text-to-image models."""

    def __init__(self) -> None:
        self.last_provider = "huggingface"
        self.last_model_used: str | None = None
        self.last_models_attempted: list[str] = []

    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        brand: object | None = None,
    ) -> str:
        """Generate an image and save it to uploads/generated/."""
        from app.core.config import settings

        hf_api_key = getattr(settings, "hf_api_key", None) or os.getenv("HUGGINGFACE_API_KEY")
        if not hf_api_key:
            raise ImageGenerationError("Hugging Face image generation is not configured. Add HUGGINGFACE_API_KEY to backend/.env.")

        full_prompt = self._build_brand_prompt(prompt, brand) if brand else prompt
        model_candidates = self._model_candidates(settings)
        if not model_candidates:
            raise ImageGenerationError("Hugging Face image model is not configured. Add HUGGINGFACE_IMAGE_MODEL to backend/.env.")

        errors: list[str] = []
        self.last_models_attempted = []
        for model in model_candidates:
            self.last_models_attempted.append(model)
            try:
                path = await self._huggingface(full_prompt, model=model, api_key=hf_api_key)
                self.last_model_used = model
                logger.info("Image generated via Hugging Face model=%s size=%s", model, size)
                return path
            except Exception as exc:
                message = self._safe_error(exc)
                errors.append(f"{model}: {message}")
                logger.warning("Hugging Face image generation failed model=%s error=%s", model, message)

        raise ImageGenerationError(
            "Hugging Face image generation failed for all configured/free models. "
            f"Models attempted: {', '.join(model_candidates)}. Last errors: {' | '.join(errors[-3:])}"
        )

    def _model_candidates(self, settings: object) -> list[str]:
        configured_many = os.getenv("HUGGINGFACE_IMAGE_MODELS", "")
        configured_one = os.getenv("HUGGINGFACE_IMAGE_MODEL") or getattr(settings, "hf_image_model", None)
        candidates: list[str] = []
        for raw in [configured_one, *configured_many.split(","), *_DEFAULT_HF_IMAGE_MODELS]:
            model = str(raw or "").strip()
            if model and model not in candidates:
                candidates.append(model)
        return candidates

    def _build_brand_prompt(self, base_prompt: str, brand: object) -> str:
        parts = [base_prompt]
        if hasattr(brand, "primary_color") and brand.primary_color:
            parts.append(f"Use brand color {brand.primary_color} as the primary accent.")
        if hasattr(brand, "tone_of_voice") and brand.tone_of_voice:
            parts.append(f"Visual style: {brand.tone_of_voice}.")
        if hasattr(brand, "logo_description") and brand.logo_description:
            parts.append(f"Include brand element: {brand.logo_description}.")
        return " ".join(parts)

    async def _huggingface(self, prompt: str, *, model: str, api_key: str) -> str:
        url = f"https://api-inference.huggingface.co/models/{model}"
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Accept": "image/png",
                },
                json={
                    "inputs": prompt[:2000],
                    "parameters": {"num_inference_steps": 24, "guidance_scale": 7.5},
                    "options": {"wait_for_model": True},
                },
            )
            resp.raise_for_status()
            if not resp.headers.get("content-type", "").startswith("image"):
                raise ImageGenerationError(resp.text[:500] or "Hugging Face did not return image bytes.")
            return self._save_bytes(resp.content)

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        text = str(exc).strip() or exc.__class__.__name__
        if "getaddrinfo failed" in text:
            return "Network/DNS could not reach api-inference.huggingface.co from this machine."
        return text[:500]

    def _save_b64(self, b64_data: str) -> str:
        image_bytes = base64.b64decode(b64_data)
        return self._save_bytes(image_bytes)

    def _save_bytes(self, image_bytes: bytes) -> str:
        filename = f"{uuid.uuid4().hex}.png"
        filepath = _UPLOADS_DIR / filename
        filepath.write_bytes(image_bytes)
        return f"uploads/generated/{filename}"
