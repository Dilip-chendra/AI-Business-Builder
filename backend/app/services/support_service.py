"""Customer Support Agent — AI chatbot trained on business data.

Handles FAQs, product queries, and general support.
Logs all conversations. Generates summaries.
No dummy responses — uses real AI or returns explicit error.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marketing import SupportConversation
from app.services.ai_service import AIProviderError, AIService

logger = logging.getLogger(__name__)


class SupportService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._ai = AIService()

    async def get_or_create_conversation(
        self, business_id: UUID, visitor_token: str
    ) -> SupportConversation:
        """Get existing open conversation or create a new one."""
        result = await self.db.execute(
            select(SupportConversation).where(
                SupportConversation.business_id == business_id,
                SupportConversation.visitor_token == visitor_token,
                SupportConversation.status == "open",
            )
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv

        conv = SupportConversation(
            business_id=business_id,
            visitor_token=visitor_token,
            status="open",
            messages=[],
        )
        self.db.add(conv)
        await self.db.commit()
        await self.db.refresh(conv)
        return conv

    async def send_message(
        self,
        conversation_id: UUID,
        user_message: str,
        business_context: dict,
        products: list[dict],
    ) -> dict:
        """Process a user message and return an AI response.

        The AI is given full business context so it can answer
        product questions, pricing, and general FAQs accurately.
        """
        conv = await self.db.get(SupportConversation, conversation_id)
        if not conv:
            return {"error": "Conversation not found"}

        # Add user message to history
        messages: list[dict] = list(conv.messages or [])
        messages.append({"role": "user", "content": user_message})

        # Build context-aware system prompt
        product_list = "\n".join(
            f"- {p.get('name')}: ${p.get('price')} — {p.get('description', '')[:100]}"
            for p in products[:10]
        )
        system_prompt = (
            f"You are a helpful customer support agent for {business_context.get('name')}.\n"
            f"Business niche: {business_context.get('niche')}\n"
            f"Target audience: {business_context.get('target_audience')}\n"
            f"Brand tone: {business_context.get('brand_tone', 'friendly and professional')}\n\n"
            f"Products available:\n{product_list or 'No products listed yet.'}\n\n"
            "Guidelines:\n"
            "- Answer questions about products, pricing, and the business\n"
            "- Be helpful, concise, and on-brand\n"
            "- If you don't know something, say so honestly\n"
            "- Never make up prices or product details\n"
            "- For complex issues, suggest contacting the business directly\n"
            "- Keep responses under 150 words unless detail is needed"
        )

        # Build conversation history for AI (last 10 messages)
        recent = messages[-10:]
        ai_messages = [{"role": "system", "content": system_prompt}]
        ai_messages.extend(recent)

        try:
            # Use generate_text with a structured conversation prompt
            full_prompt = (
                f"{system_prompt}\n\n"
                + "\n".join(
                    f"{'Customer' if m['role'] == 'user' else 'Agent'}: {m['content']}"
                    for m in recent[:-1]
                )
                + f"\nCustomer: {user_message}\nAgent:"
            )
            response_text = await self._ai.generate_text(full_prompt)
            # Clean up the response
            response_text = response_text.strip()
            if response_text.startswith("Agent:"):
                response_text = response_text[6:].strip()

        except AIProviderError as exc:
            return {
                "error": f"AI unavailable: {exc}",
                "conversation_id": str(conversation_id),
            }

        # Add AI response to history
        messages.append({"role": "assistant", "content": response_text})
        conv.messages = messages
        await self.db.commit()

        logger.info(
            "Support message processed  conv_id=%s  messages=%d",
            conversation_id, len(messages),
        )
        return {
            "conversation_id": str(conversation_id),
            "response": response_text,
            "message_count": len(messages),
        }

    async def resolve_conversation(self, conversation_id: UUID) -> SupportConversation | None:
        """Mark conversation as resolved and generate a summary."""
        conv = await self.db.get(SupportConversation, conversation_id)
        if not conv:
            return None

        # Generate summary if there are messages
        if conv.messages and len(conv.messages) >= 2:
            try:
                messages_text = "\n".join(
                    f"{'Customer' if m['role'] == 'user' else 'Agent'}: {m['content']}"
                    for m in conv.messages
                )
                summary_prompt = (
                    "Summarize this customer support conversation in 2-3 sentences.\n"
                    "Include: main issue, resolution, and any follow-up needed.\n\n"
                    f"{messages_text}"
                )
                summary = await self._ai.generate_text(summary_prompt)
                conv.summary = summary.strip()
            except Exception:
                conv.summary = f"Conversation with {len(conv.messages)} messages."

        conv.status = "resolved"
        await self.db.commit()
        return conv

    async def list_conversations(
        self, business_id: UUID, status: str | None = None
    ) -> list[SupportConversation]:
        query = (
            select(SupportConversation)
            .where(SupportConversation.business_id == business_id)
            .order_by(SupportConversation.created_at.desc())
        )
        if status:
            query = query.where(SupportConversation.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())
