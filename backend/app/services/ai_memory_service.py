"""AI Memory Service — brand context CRUD and prompt injection."""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_memory import AIMemory

logger = logging.getLogger(__name__)


class AIMemoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_context(self, business_id: str, user_id: str) -> AIMemory | None:
        """Return the AIMemory record for a business, or None if not found."""
        result = await self.db.execute(
            select(AIMemory).where(AIMemory.business_id == str(business_id))
        )
        return result.scalar_one_or_none()

    async def save_context(self, business_id: str, user_id: str, data: dict) -> AIMemory:
        """Create or update the AIMemory record for a business."""
        existing = await self.get_context(business_id, user_id)
        if existing:
            existing.brand_name = data.get("brand_name", existing.brand_name)
            existing.tone_of_voice = data.get("tone_of_voice", existing.tone_of_voice)
            existing.target_audience = data.get("target_audience", existing.target_audience)
            kd = data.get("key_differentiators")
            if kd is not None:
                existing.key_differentiators = (
                    json.dumps(kd) if isinstance(kd, list) else str(kd)
                )
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        mem = AIMemory(
            business_id=str(business_id),
            user_id=str(user_id),
            brand_name=data.get("brand_name", ""),
            tone_of_voice=data.get("tone_of_voice", ""),
            target_audience=data.get("target_audience", ""),
            key_differentiators=json.dumps(data.get("key_differentiators", [])),
            approved_examples="[]",
        )
        self.db.add(mem)
        await self.db.commit()
        await self.db.refresh(mem)
        logger.info("AI memory created  business_id=%s", business_id)
        return mem

    async def append_example(self, business_id: str, content: str) -> None:
        """Append an approved content example to the memory store."""
        result = await self.db.execute(
            select(AIMemory).where(AIMemory.business_id == str(business_id))
        )
        mem = result.scalar_one_or_none()
        if not mem:
            return
        examples: list[str] = json.loads(mem.approved_examples or "[]")
        examples.append(content[:500])
        examples = examples[-20:]  # keep last 20 examples
        mem.approved_examples = json.dumps(examples)
        await self.db.commit()

    def inject_into_prompt(self, prompt: str, mem: AIMemory) -> str:
        """Prepend brand context to a prompt. Idempotent for same inputs."""
        parts: list[str] = []
        if mem.brand_name:
            parts.append(f"Brand: {mem.brand_name}")
        if mem.tone_of_voice:
            parts.append(f"Tone of voice: {mem.tone_of_voice}")
        if mem.target_audience:
            parts.append(f"Target audience: {mem.target_audience}")
        kd: list[str] = json.loads(mem.key_differentiators or "[]")
        if kd:
            parts.append(f"Key differentiators: {', '.join(kd)}")
        if not parts:
            return prompt
        context = "\n".join(parts)
        return f"Brand context:\n{context}\n\n{prompt}"
