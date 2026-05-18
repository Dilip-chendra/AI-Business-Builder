"""Brand System Service — per-business brand identity CRUD and prompt injection."""
from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brand_system import BrandSystem

logger = logging.getLogger(__name__)


class BrandSystemService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, business_id: str) -> BrandSystem | None:
        result = await self.db.execute(
            select(BrandSystem).where(BrandSystem.business_id == str(business_id))
        )
        return result.scalar_one_or_none()

    async def upsert(self, business_id: str, data: dict) -> BrandSystem:
        existing = await self.get(business_id)
        if existing:
            for field in ["primary_color", "secondary_color", "tone_of_voice",
                          "target_audience", "industry", "website_url", "logo_description"]:
                if field in data:
                    setattr(existing, field, data[field])
            if "competitors" in data:
                existing.competitors = (
                    json.dumps(data["competitors"])
                    if isinstance(data["competitors"], list)
                    else data["competitors"]
                )
            await self.db.commit()
            await self.db.refresh(existing)
            return existing

        brand = BrandSystem(
            business_id=str(business_id),
            primary_color=data.get("primary_color", "#6366f1"),
            secondary_color=data.get("secondary_color", "#8b5cf6"),
            tone_of_voice=data.get("tone_of_voice", "professional"),
            target_audience=data.get("target_audience", ""),
            industry=data.get("industry", ""),
            competitors=json.dumps(data.get("competitors", [])),
            website_url=data.get("website_url"),
            logo_description=data.get("logo_description"),
        )
        self.db.add(brand)
        await self.db.commit()
        await self.db.refresh(brand)
        logger.info("Brand system created  business_id=%s", business_id)
        return brand

    def inject_into_prompt(self, prompt: str, brand: BrandSystem) -> str:
        """Prepend brand context to a generation prompt."""
        parts: list[str] = []
        if brand.tone_of_voice:
            parts.append(f"Brand tone: {brand.tone_of_voice}")
        if brand.target_audience:
            parts.append(f"Target audience: {brand.target_audience}")
        if brand.industry:
            parts.append(f"Industry: {brand.industry}")
        if brand.primary_color:
            parts.append(f"Primary brand color: {brand.primary_color}")
        competitors = json.loads(brand.competitors or "[]")
        if competitors:
            parts.append(f"Competitors: {', '.join(competitors[:3])}")
        if not parts:
            return prompt
        context = "\n".join(parts)
        return f"Brand context:\n{context}\n\n{prompt}"
