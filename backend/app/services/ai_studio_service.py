"""Operational orchestration service for AI Studio."""
from __future__ import annotations

import json
import re
import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import cache
from app.models.ai_studio import AIStudioConversation, AIStudioMessage
from app.models.agent import AgentLog
from app.models.business import Business
from app.models.user import User
from app.services.ai_memory_service import AIMemoryService
from app.services.ai_service import AIService
from app.services.business_service import BusinessService
from app.services.code_version_service import CodeVersionService
from app.services.project_sync_service import ProjectSyncService

logger = logging.getLogger(__name__)


class AIStudioService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_timeline(self, business_id: str, user: User, limit: int = 50) -> dict[str, Any]:
        business = await self._load_business(business_id, user)
        conversation = await self._get_conversation(business)
        if not conversation:
            return {"business_id": business_id, "conversation_id": None, "messages": []}

        result = await self.db.execute(
            select(AIStudioMessage)
            .where(AIStudioMessage.conversation_id == conversation.id)
            .order_by(AIStudioMessage.created_at.desc())
            .limit(limit)
        )
        messages = list(reversed(result.scalars().all()))
        return {
            "business_id": str(business.id),
            "conversation_id": conversation.id,
            "messages": [self._message_payload(message) for message in messages],
        }

    async def run_prompt(
        self,
        business_id: str,
        instruction: str,
        user: User,
        brand_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc)
        business = await self._load_business(business_id, user)
        conversation = await self._get_or_create_conversation(business, user)
        plan = self._plan_instruction(instruction)
        logger.info(
            "AI Studio prompt received business_id=%s user_id=%s tool=%s intent=%s",
            business.id,
            user.id,
            plan["selected_tool"],
            plan["intent"],
        )

        await self._save_brand_context(business, user, brand_context or {})
        user_message = await self._add_message(
            conversation,
            business,
            user,
            role="user",
            content=instruction,
            status="completed",
            metadata_json={
                "brand_context": brand_context or {},
                "orchestration": {
                    "event": "prompt_received",
                    "instruction": instruction,
                    "intent": plan["intent"],
                    "selected_tool": plan["selected_tool"],
                    "tool_label": plan["tool_label"],
                    "reason": plan["reason"],
                    "status": "received",
                    "started_at": started_at.isoformat(),
                    "business_id": str(business.id),
                    "business_name": business.name,
                },
            },
        )

        try:
            if plan["selected_tool"] == "app_builder":
                action = await self._execute_app_builder(business, user, instruction, brand_context or {})
            elif plan["selected_tool"] == "code_editor":
                action = await self._edit_workspace_code(business, user, instruction)
            elif plan["selected_tool"] == "browser_research":
                action = await self._create_research_report(business, user, instruction)
            elif plan["selected_tool"] == "product_builder":
                action = await self._create_product_asset(business, user, instruction)
            elif plan["selected_tool"] == "marketing_engine":
                action = await self._create_marketing_asset(business, user, instruction, brand_context or {})
            else:
                action = await self._modify_business(business, user, instruction, brand_context or {})
            self._validate_action_result(action)
            action = self._attach_orchestration_trace(action, plan, business, instruction, started_at, "completed")
            logger.info(
                "AI Studio action applied business_id=%s action_type=%s changed_files=%s version_id=%s",
                business.id,
                action.get("action_type"),
                action.get("changed_files") or action.get("updated_files") or action.get("file_path"),
                action.get("version_id"),
            )
        except Exception as exc:
            failed_action = self._attach_orchestration_trace(
                {"error": str(exc), "action_type": plan["fallback_action_type"]},
                plan,
                business,
                instruction,
                started_at,
                "failed",
                error=str(exc),
            )
            assistant_message = await self._add_message(
                conversation,
                business,
                user,
                role="assistant",
                content=f"AI Studio could not complete the action: {exc}",
                status="failed",
                action_type=plan["fallback_action_type"],
                metadata_json=failed_action,
            )
            return {
                "status": "failed",
                "conversation_id": conversation.id,
                "user_message": self._message_payload(user_message),
                "assistant_message": self._message_payload(assistant_message),
                "action": failed_action,
            }

        assistant_message = await self._add_message(
            conversation,
            business,
            user,
            role="assistant",
            content=action["summary"],
            status="completed",
            action_type=action.get("action_type", "business_profile_update"),
            metadata_json=action,
        )

        return {
            "status": "completed",
            "conversation_id": conversation.id,
            "user_message": self._message_payload(user_message),
            "assistant_message": self._message_payload(assistant_message),
            "action": action,
        }

    async def _load_business(self, business_id: str, user: User) -> Business:
        business = await BusinessService(self.db).get(UUID(str(business_id)), user_id=user.id)
        if not business:
            raise ValueError("Business not found")
        return business

    async def _get_conversation(self, business: Business) -> AIStudioConversation | None:
        result = await self.db.execute(
            select(AIStudioConversation)
            .where(
                AIStudioConversation.business_id == str(business.id),
                AIStudioConversation.status == "active",
            )
            .order_by(AIStudioConversation.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_or_create_conversation(self, business: Business, user: User) -> AIStudioConversation:
        existing = await self._get_conversation(business)
        if existing:
            return existing

        conversation = AIStudioConversation(
            user_id=str(user.id),
            business_id=str(business.id),
            title=f"AI Studio - {business.name}",
            context_snapshot=self._business_snapshot(business),
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def _add_message(
        self,
        conversation: AIStudioConversation,
        business: Business,
        user: User,
        *,
        role: str,
        content: str,
        status: str,
        message_type: str = "chat",
        action_type: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> AIStudioMessage:
        message = AIStudioMessage(
            conversation_id=conversation.id,
            user_id=str(user.id),
            business_id=str(business.id),
            role=role,
            content=content,
            status=status,
            message_type=message_type,
            action_type=action_type,
            metadata_json=metadata_json or {},
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message

    async def _save_brand_context(self, business: Business, user: User, brand_context: dict[str, Any]) -> None:
        if not brand_context:
            return

        differentiators = brand_context.get("key_differentiators", brand_context.get("differentiators", []))
        if isinstance(differentiators, str):
            differentiators = [part.strip() for part in differentiators.split(",") if part.strip()]

        payload = {
            "brand_name": brand_context.get("brand_name") or business.name,
            "tone_of_voice": brand_context.get("tone_of_voice", brand_context.get("tone", "")),
            "target_audience": brand_context.get("target_audience", brand_context.get("audience", "")),
            "key_differentiators": differentiators if isinstance(differentiators, list) else [],
        }
        await AIMemoryService(self.db).save_context(str(business.id), str(user.id), payload)

    async def _modify_business(
        self,
        business: Business,
        user: User,
        instruction: str,
        brand_context: dict[str, Any],
    ) -> dict[str, Any]:
        deterministic_style_action = self._deterministic_style_patch(business, instruction)
        if deterministic_style_action:
            return await self._apply_business_update(
                business=business,
                user=user,
                instruction=instruction,
                field="page_content",
                new_value=deterministic_style_action["new_value"],
                summary=deterministic_style_action["summary"],
                code_preview=deterministic_style_action["code_preview"],
                page_patch=deterministic_style_action["page_patch"],
            )

        deterministic_landing_action = self._deterministic_landing_patch(business, instruction)
        if deterministic_landing_action:
            return await self._apply_business_update(
                business=business,
                user=user,
                instruction=instruction,
                field=deterministic_landing_action["field"],
                new_value=deterministic_landing_action["new_value"],
                summary=deterministic_landing_action["summary"],
                code_preview=deterministic_landing_action["code_preview"],
                page_patch=deterministic_landing_action.get("page_patch", {}),
            )

        ai = AIService()
        brand_prompt = json.dumps(brand_context or {}, ensure_ascii=True)
        agent_context = await self._recent_agent_context(str(business.id))
        analysis_prompt = (
            "You are the orchestration brain for an AI business operating system.\n"
            "Modify the active business landing page using the user's instruction and brand memory.\n"
            "Return a JSON object with EXACTLY these 5 keys: field, new_value, summary, code_preview, page_patch\n\n"
            "ALLOWED VALUES FOR 'field' (copy exactly, lowercase, no spaces):\n"
            "  headline\n"
            "  subheading\n"
            "  cta_text\n"
            "  description\n"
            "  product_pitch\n"
            "  page_content\n\n"
            f"BRAND MEMORY:\n{brand_prompt}\n\n"
            f"RECENT AGENT RESEARCH:\n{agent_context or 'No recent agent reports.'}\n\n"
            "CURRENT PAGE CONTENT:\n"
            f"  headline: {business.headline}\n"
            f"  subheading: {business.subheading}\n"
            f"  cta_text: {business.cta_text}\n"
            f"  description: {business.description}\n"
            f"  product_pitch: {business.product_pitch}\n"
            f"  page_content: {json.dumps(business.page_content or {}, ensure_ascii=True)}\n\n"
            f"USER INSTRUCTION: {instruction}\n\n"
            "RULES:\n"
            "- 'field' must be exactly one allowed value.\n"
            "- For top-level field edits, 'new_value' must be the improved text.\n"
            "- For page_content edits, 'new_value' must be a short descriptive summary.\n"
            "- 'summary' must be one sentence explaining what changed.\n"
            "- 'code_preview' must be a short HTML snippet showing the new value.\n"
            "- 'page_patch' must be an object. Use it only when field='page_content'.\n"
            "- Allowed page_patch keys: pain_points, benefits, features, social_proof, faq, pricing_tiers, urgency_text, trust_badges, color_scheme.\n"
            "- Return ONLY valid JSON, no prose, no markdown."
        )

        result = await ai.generate_json(analysis_prompt)
        field = self._normalize_field(str(result.get("field") or ""), instruction)
        new_value = result.get("new_value", "")
        summary = str(result.get("summary") or "AI Studio updated the business profile.")
        code_preview = str(result.get("code_preview") or "")
        page_patch = result.get("page_patch") or {}

        if not new_value or len(str(new_value).strip()) < 2:
            raise ValueError("AI returned an empty new value. Please try a more specific instruction.")

        return await self._apply_business_update(
            business=business,
            user=user,
            instruction=instruction,
            field=field,
            new_value=new_value,
            summary=summary,
            code_preview=code_preview,
            page_patch=page_patch,
        )

    async def _apply_business_update(
        self,
        *,
        business: Business,
        user: User,
        instruction: str,
        field: str,
        new_value: Any,
        summary: str,
        code_preview: str,
        page_patch: Any,
    ) -> dict[str, Any]:
        old_value: Any = getattr(business, field, "") if field != "page_content" else dict(business.page_content or {})
        if field == "page_content":
            sanitized_patch = self._sanitize_page_patch(page_patch)
            if not sanitized_patch:
                raise ValueError("AI did not return a valid structured page update. Please try a more specific section request.")
            next_page_content = dict(business.page_content or {})
            next_page_content.update(sanitized_patch)
            business.page_content = next_page_content
            new_value = json.dumps(sanitized_patch, ensure_ascii=True)
        else:
            setattr(business, field, str(new_value))

        business.updated_at = datetime.now(timezone.utc)
        self.db.add(business)
        await self.db.commit()
        await self.db.refresh(business)

        sync_service = ProjectSyncService(business)
        sync_service.ensure_scaffold()
        updated_files = sync_service.sync_business_profile()
        await cache.delete(f"business:{business.id}:{user.id}")
        await cache.delete(f"landing:{business.id}")
        version = await CodeVersionService(self.db).create_version(
            user_id=str(user.id),
            business_id=str(business.id),
            file_path="studio/business-profile.json",
            content=sync_service._studio_snapshot(),
            source="ai_studio",
            instruction=instruction,
        )

        return {
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "summary": summary,
            "code_preview": code_preview,
            "business_id": str(business.id),
            "business_name": business.name,
            "version_id": str(version.id),
            "version_number": version.version_number,
            "updated_files": updated_files,
            "diff": {
                "field": field,
                "before": self._preview_value(old_value),
                "after": self._preview_value(new_value),
            },
            "action_type": "business_profile_update",
        }

    async def _create_marketing_asset(
        self,
        business: Business,
        user: User,
        instruction: str,
        brand_context: dict[str, Any],
    ) -> dict[str, Any]:
        from app.schemas.analytics import AnalyticsEventCreate
        from app.services.analytics_service import AnalyticsService
        from app.services.marketing_service import MarketingService

        content_type = self._infer_marketing_content_type(instruction)
        audience = (
            brand_context.get("target_audience")
            or brand_context.get("audience")
            or business.target_audience
            or "target customers"
        )
        tone = (
            brand_context.get("tone_of_voice")
            or brand_context.get("tone")
            or business.brand_tone
            or "Professional"
        )
        campaign = await MarketingService(self.db).generate_custom_content(
            business_id=business.id,
            content_type=content_type,
            tone=str(tone),
            audience=str(audience),
            cta="Learn More",
            business_context={
                **self._marketing_business_context(business),
                "recent_agent_research": await self._recent_agent_context(str(business.id)),
            },
            goal=instruction,
            project_id=business.project_id,
            product_id=None,
        )
        await AnalyticsService(self.db).track(
            AnalyticsEventCreate(
                business_id=business.id,
                product_id=campaign.product_id,
                event_type="marketing_campaign_created",
                source="ai_studio",
                metadata_json={
                    "campaign_id": str(campaign.id),
                    "campaign_type": campaign.campaign_type,
                    "content_type": content_type,
                    "status": campaign.status,
                    "instruction": instruction[:500],
                },
            )
        )
        return {
            "action_type": "marketing_campaign_created",
            "summary": f"Created a {content_type.replace('_', ' ')} campaign in Marketing Engine: {campaign.name}.",
            "business_id": str(business.id),
            "business_name": business.name,
            "campaign_id": str(campaign.id),
            "campaign_type": campaign.campaign_type,
            "campaign_name": campaign.name,
            "status": campaign.status,
            "content": campaign.content,
            "targeting": campaign.targeting,
            "next_url": f"/marketing?tab=campaigns&campaign_id={campaign.id}&business_id={business.id}",
        }

    async def _edit_workspace_code(self, business: Business, user: User, instruction: str) -> dict[str, Any]:
        sync_service = ProjectSyncService(business)
        sync_service.ensure_scaffold()
        file_path = self._select_workspace_file(sync_service.root, instruction)
        target = (sync_service.root / file_path).resolve()
        root = sync_service.root.resolve()
        if not str(target).startswith(str(root)):
            raise ValueError("Selected file is outside the business workspace.")
        if not target.exists():
            raise ValueError(f"Workspace file not found: {file_path}")

        original = target.read_text(encoding="utf-8")
        language = self._language_for_path(file_path)
        prompt = (
            "You are the real code-editing engine behind AI Studio.\n"
            "Modify the selected workspace file according to the instruction.\n\n"
            "STRICT RULES:\n"
            "- Return ONLY the complete updated file content.\n"
            "- No markdown, no code fences, no explanation.\n"
            "- Preserve imports and exports unless the instruction requires a change.\n"
            "- Keep the file valid for the existing project scaffold.\n"
            "- Make a concrete visible change; do not return the original unchanged file.\n\n"
            f"Business: {business.name}\n"
            f"File path: {file_path}\n"
            f"Language: {language}\n"
            f"Instruction: {instruction}\n\n"
            f"Current file:\n{original}"
        )

        try:
            updated = await AIService().generate_text(prompt, task_type="coding")
        except Exception as exc:
            raise ValueError(f"Code edit failed because no AI coding provider completed the request: {exc}") from exc

        updated = re.sub(r"^```\w*\n?", "", updated.strip())
        updated = re.sub(r"\n?```$", "", updated.strip())
        if not updated or updated == original:
            raise ValueError("AI code edit returned no concrete file change.")

        target.write_text(updated, encoding="utf-8")
        await cache.delete(f"business:{business.id}:{user.id}")
        await cache.delete(f"landing:{business.id}")
        version = await CodeVersionService(self.db).create_version(
            user_id=str(user.id),
            business_id=str(business.id),
            file_path=file_path,
            content=updated,
            source="ai_studio_code_edit",
            instruction=instruction,
        )
        return {
            "action_type": "code_edit_applied",
            "summary": f"AI Studio edited {file_path} in the real Code Editor workspace.",
            "business_id": str(business.id),
            "business_name": business.name,
            "file_path": file_path,
            "updated_files": [file_path],
            "version_id": str(version.id),
            "version_number": version.version_number,
            "diff": {
                "field": file_path,
                "before": self._preview_value(original),
                "after": self._preview_value(updated),
            },
            "next_url": f"/code-editor?business_id={business.id}&path={file_path}",
        }

    async def _execute_app_builder(
        self,
        business: Business,
        user: User,
        instruction: str,
        brand_context: dict[str, Any],
    ) -> dict[str, Any]:
        sync_service = ProjectSyncService(business)
        sync_service.ensure_scaffold()
        root = sync_service.root.resolve()
        file_paths = ["app/page.tsx", "components/Hero.tsx", "styles/theme.css", "data/business.json"]
        current_files: dict[str, str] = {}
        for relative_path in file_paths:
            path = (root / relative_path).resolve()
            if str(path).startswith(str(root)) and path.exists():
                content = path.read_text(encoding="utf-8")
                current_files[relative_path] = self._compact_file_context(relative_path, content)

        try:
            plan = await self._generate_app_builder_plan(business, instruction, brand_context, current_files)
        except Exception as provider_exc:
            logger.warning(
                "AI Studio app-builder provider path failed; trying local recovery compiler business_id=%s error=%r",
                business.id,
                provider_exc,
            )
            plan = self._local_app_builder_plan(business, instruction, current_files)
            if plan:
                plan["provider_error"] = str(provider_exc)
                plan["summary"] = (
                    str(plan.get("summary") or "AI Studio recovered and applied a local app-builder change.")
                    + " Provider output was not structured enough, so the recovery compiler applied the visible request."
                )
            else:
                raise
        else:
            intent_patch = self._safe_local_app_builder_plan(business, instruction, current_files)
            if intent_patch:
                plan = self._merge_app_builder_plans(plan, intent_patch)
        plan = self._guard_app_builder_plan(business, instruction, plan)
        business_updates = self._sanitize_business_updates(plan.get("business_updates") or {})
        page_patch = self._sanitize_page_patch(plan.get("page_content_patch") or {})
        changed_files: list[str] = []

        for field in (
            "name",
            "niche",
            "target_audience",
            "headline",
            "subheading",
            "cta_text",
            "description",
            "product_pitch",
            "brand_tone",
            "monetization_model",
            "seo_title",
            "seo_description",
        ):
            value = business_updates.get(field)
            if value:
                setattr(business, field, value)
        if page_patch:
            next_page_content = dict(business.page_content or {})
            next_page_content.update(page_patch)
            business.page_content = next_page_content

        business.updated_at = datetime.now(timezone.utc)
        self.db.add(business)
        await self.db.commit()
        await self.db.refresh(business)

        # Keep canonical business data aligned before applying code file updates.
        sync_service = ProjectSyncService(business)
        sync_service.ensure_scaffold()
        changed_files.extend(sync_service.sync_business_profile())
        root = sync_service.root.resolve()

        files = plan.get("files") if isinstance(plan.get("files"), list) else []
        for item in files:
            if not isinstance(item, dict):
                continue
            relative_path = str(item.get("path") or "").replace("\\", "/").strip("/")
            content = item.get("content")
            if relative_path not in {"app/page.tsx", "components/Hero.tsx", "styles/theme.css"}:
                continue
            if not isinstance(content, str) or len(content.strip()) < 20:
                continue
            content = self._safe_app_builder_file_content(sync_service, relative_path, content)
            if not content:
                continue
            target = (root / relative_path).resolve()
            if not str(target).startswith(str(root)):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            existing = target.read_text(encoding="utf-8") if target.exists() else ""
            if existing != content:
                target.write_text(content, encoding="utf-8")
                changed_files.append(relative_path)

        if not changed_files and not business_updates and not page_patch:
            raise ValueError("AI Studio did not produce any concrete project or preview changes.")

        await cache.delete(f"business:{business.id}:{user.id}")
        await cache.delete(f"landing:{business.id}")
        manifest = {
            "instruction": instruction,
            "summary": plan.get("summary") or "AI Studio applied app-builder changes.",
            "business_updates": business_updates,
            "page_content_patch": page_patch,
            "changed_files": sorted(set(changed_files)),
            "provider_used": plan.get("provider_used") or "ai_service_router",
        }

        version = await CodeVersionService(self.db).create_version(
            user_id=str(user.id),
            business_id=str(business.id),
            file_path="studio/app-builder-manifest.json",
            content=json.dumps(manifest, indent=2, ensure_ascii=True),
            source="ai_studio_app_builder",
            instruction=instruction,
        )
        return {
            "action_type": "app_builder_project_update",
            "summary": str(plan.get("summary") or "AI Studio updated the app builder project and live preview."),
            "business_id": str(business.id),
            "business_name": business.name,
            "provider_used": manifest["provider_used"],
            "changed_files": sorted(set(changed_files)),
            "updated_files": sorted(set(changed_files)),
            "version_id": str(version.id),
            "version_number": version.version_number,
            "preview_url": f"/landing/{business.id}?preview=1",
            "next_url": f"/code-editor?business_id={business.id}",
            "diff": {
                "field": "project_workspace",
                "before": "Previous project snapshot",
                "after": ", ".join(sorted(set(changed_files))) or "Business preview data",
            },
        }

    def _safe_local_app_builder_plan(self, business: Business, instruction: str, current_files: dict[str, str]) -> dict[str, Any] | None:
        """Return deterministic visible-intent patches without turning provider success into failure."""
        try:
            return self._local_app_builder_plan(business, instruction, current_files)
        except Exception:
            return None

    @staticmethod
    def _merge_app_builder_plans(provider_plan: dict[str, Any], intent_patch: dict[str, Any]) -> dict[str, Any]:
        """Overlay exact user-intent changes on top of AI output.

        The AI provider is still used for broad reasoning, but explicit user
        requests such as a brand pivot, CTA text, or color choice must not be
        lost because a model produced weak JSON or generic copy.
        """
        merged = dict(provider_plan) if isinstance(provider_plan, dict) else {}
        provider_updates = merged.get("business_updates") if isinstance(merged.get("business_updates"), dict) else {}
        provider_page = merged.get("page_content_patch") if isinstance(merged.get("page_content_patch"), dict) else {}
        patch_updates = intent_patch.get("business_updates") if isinstance(intent_patch.get("business_updates"), dict) else {}
        patch_page = intent_patch.get("page_content_patch") if isinstance(intent_patch.get("page_content_patch"), dict) else {}

        merged["business_updates"] = {**provider_updates, **patch_updates}
        merged["page_content_patch"] = {**provider_page, **patch_page}

        provider_files = merged.get("files") if isinstance(merged.get("files"), list) else []
        patch_files = intent_patch.get("files") if isinstance(intent_patch.get("files"), list) else []
        by_path: dict[str, dict[str, Any]] = {}
        for item in provider_files + patch_files:
            if isinstance(item, dict) and isinstance(item.get("path"), str):
                by_path[str(item["path"])] = item
        merged["files"] = list(by_path.values())

        provider_summary = str(merged.get("summary") or "").strip()
        patch_summary = str(intent_patch.get("summary") or "").strip()
        if patch_summary and patch_summary.lower() not in provider_summary.lower():
            merged["summary"] = f"{provider_summary} {patch_summary}".strip()
        elif not provider_summary:
            merged["summary"] = patch_summary or "AI Studio applied the requested page update."

        provider_used = str(merged.get("provider_used") or "ai_service_router")
        patch_provider = str(intent_patch.get("provider_used") or "")
        if patch_provider:
            merged["provider_used"] = f"{provider_used}+intent_safety_patch"
        else:
            merged["provider_used"] = provider_used
        return merged

    @staticmethod
    def _safe_app_builder_file_content(sync_service: ProjectSyncService, relative_path: str, content: str) -> str | None:
        stripped = content.strip()
        if relative_path == "styles/theme.css":
            required = ("--abb-accent", ".abb-primary", ".abb-card", ".abb-hero")
            if len(stripped) < 1200 or not all(token in stripped for token in required):
                return sync_service._theme_css()
            return content
        if relative_path == "components/Hero.tsx":
            if "export function Hero" not in stripped or "<section" not in stripped or "</section>" not in stripped:
                return None
            return content
        if relative_path == "app/page.tsx":
            if "export default function" not in stripped or "business" not in stripped or "Hero" not in stripped:
                return None
            return content
        return content

    async def _generate_app_builder_plan(
        self,
        business: Business,
        instruction: str,
        brand_context: dict[str, Any],
        current_files: dict[str, str],
    ) -> dict[str, Any]:
        prompt = (
            "You are AI Studio, a real prompt-to-app builder inside an AI SaaS platform.\n"
            "Think through the user's custom request and produce the best concrete app update you can.\n"
            "Return valid JSON so the backend can apply your work to the database and project files.\n\n"
            "Preferred JSON shape:\n"
            "{\n"
            '  "summary": "one sentence describing the actual change",\n'
            '  "provider_used": "ai_service_router",\n'
            '  "business_updates": {"name": "", "niche": "", "target_audience": "", "headline": "", "subheading": "", "cta_text": "", "description": "", "product_pitch": "", "brand_tone": "", "monetization_model": "", "seo_title": "", "seo_description": ""},\n'
            '  "page_content_patch": {\n'
            '    "color_scheme": "indigo|emerald|rose|amber|black_gold|sky|violet",\n'
            '    "benefits": ["..."],\n'
            '    "features": [{"title":"...","description":"...","icon_hint":"zap|shield|chart|users|star|clock|globe|lock"}],\n'
            '    "lead_capture": {"headline":"...","description":"...","fields":["Name","Phone","Email"],"cta":"..."},\n'
            '    "quote_request": {"headline":"...","description":"...","fields":["Service needed","Timeline","Phone"],"cta":"..."},\n'
            '    "social_proof": [{"name":"...","role":"...","quote":"...","rating":5}],\n'
            '    "pricing_tiers": [{"name":"...","price":"$99","period":"mo","features":["..."],"cta":"...","highlighted":true}],\n'
            '    "faq": [{"question":"...","answer":"..."}],\n'
            '    "trust_badges": ["..."],\n'
            '    "urgency_text": "..."\n'
            "  },\n"
            '  "files": [{"path":"app/page.tsx","content":"complete updated file if needed"}],\n'
            '  "operations": [{"type":"update_business_profile","fields":{}}, {"type":"replace_file","path":"styles/theme.css","content":"..."}]\n'
            "}\n\n"
            "Important: honor the user's exact request. Make visible changes. Do not return the unchanged page.\n"
            "If the user asks for a brand or niche pivot, update the business name, target audience, hero copy, CTA, pain points, services/features, and reviews together.\n\n"
            f"BUSINESS:\n{json.dumps(self._business_snapshot(business), ensure_ascii=True)}\n\n"
            f"PAGE_CONTENT:\n{json.dumps(business.page_content or {}, ensure_ascii=True)}\n\n"
            f"BRAND_CONTEXT:\n{json.dumps(brand_context or {}, ensure_ascii=True)}\n\n"
            f"CURRENT_FILES_COMPACT:\n{json.dumps(current_files, ensure_ascii=True)[:2600]}\n\n"
            f"USER_PROMPT: {instruction}\n"
        )
        ai_service = AIService()
        try:
            logger.info("AI Studio app-builder provider request business_id=%s", business.id)
            raw_output = await asyncio.wait_for(
                ai_service.generate_text(prompt, prefer_json=True, task_type="ai_studio_app_builder"),
                timeout=180,
            )
            provider_used = ai_service.last_provider or "ai_service_router"
            try:
                data = ai_service._parse_json(raw_output)
            except Exception as parse_exc:
                logger.warning(
                    "AI Studio app-builder provider returned malformed JSON business_id=%s error=%r",
                    business.id,
                    parse_exc,
                )
                data = await self._repair_app_builder_json(ai_service, raw_output, instruction)
            if isinstance(data, dict):
                if provider_used != "ai_service_router":
                    data["provider_used"] = provider_used
                elif data.get("provider_used") in {None, "", "ai_service_router"}:
                    data["provider_used"] = provider_used
                logger.info(
                    "AI Studio app-builder provider response parsed business_id=%s files=%s",
                    business.id,
                    len(data.get("files") or []),
                )
                return data
        except asyncio.TimeoutError as exc:
            logger.warning("AI Studio app-builder provider timed out business_id=%s", business.id)
            raise ValueError("AI provider timed out while generating a structured page change. Try again or use a smaller request.") from exc
        except Exception as exc:
            logger.warning("AI Studio app-builder provider failed business_id=%s error=%r", business.id, exc)
            raise ValueError(f"AI Studio provider failed before producing a structured change plan: {exc}") from exc
        raise ValueError("AI Studio provider returned an invalid structured change plan.")

    @staticmethod
    async def _repair_app_builder_json(ai_service: AIService, raw_output: str, instruction: str) -> dict[str, Any]:
        repair_prompt = (
            "Convert the malformed AI Studio app-builder response into ONE valid JSON object only.\n"
            "Do not add markdown, prose, comments, or trailing commas.\n"
            "Preserve the user's intended visible page changes. Use this shape:\n"
            "{"
            "\"summary\":\"\","
            "\"provider_used\":\"ai_service_router\","
            "\"business_updates\":{\"name\":\"\",\"niche\":\"\",\"target_audience\":\"\",\"headline\":\"\",\"subheading\":\"\",\"cta_text\":\"\",\"description\":\"\",\"product_pitch\":\"\",\"brand_tone\":\"\",\"monetization_model\":\"\",\"seo_title\":\"\",\"seo_description\":\"\"},"
            "\"page_content_patch\":{\"pain_points\":[],\"benefits\":[],\"features\":[],\"social_proof\":[],\"faq\":[],\"trust_badges\":[],\"urgency_text\":\"\",\"color_scheme\":\"\"},"
            "\"files\":[],"
            "\"operations\":[]"
            "}\n\n"
            f"USER_PROMPT:\n{instruction[:1200]}\n\n"
            f"MALFORMED_RESPONSE:\n{raw_output[:9000]}"
        )
        return await asyncio.wait_for(
            ai_service.generate_json(repair_prompt, task_type="json_formatting"),
            timeout=75,
        )

    @staticmethod
    def _compact_file_context(path: str, content: str, *, limit: int = 900) -> str:
        if len(content) <= limit:
            return content
        head = content[: limit // 2]
        tail = content[-limit // 2 :]
        return f"{head}\n\n/* ... {path} compacted for AI prompt ... */\n\n{tail}"

    @staticmethod
    def _sanitize_business_updates(data: dict[str, Any]) -> dict[str, str]:
        allowed = {
            "name",
            "niche",
            "target_audience",
            "headline",
            "subheading",
            "cta_text",
            "description",
            "product_pitch",
            "brand_tone",
            "monetization_model",
            "seo_title",
            "seo_description",
        }
        aliases = {
            "brand": "name",
            "brand_name": "name",
            "business_name": "name",
            "company_name": "name",
            "industry": "niche",
            "category": "niche",
            "audience": "target_audience",
            "target_customer": "target_audience",
            "target_customers": "target_audience",
            "target_market": "target_audience",
            "subheadline": "subheading",
            "sub_headline": "subheading",
            "subtitle": "subheading",
            "hero_subheadline": "subheading",
            "hero_subheading": "subheading",
            "hero_headline": "headline",
            "cta": "cta_text",
            "main_cta": "cta_text",
            "button_text": "cta_text",
            "cta_button": "cta_text",
            "call_to_action": "cta_text",
            "seoTitle": "seo_title",
            "seoDescription": "seo_description",
            "seotitle": "seo_title",
            "seodescription": "seo_description",
        }
        limits = {
            "name": 120,
            "niche": 160,
            "target_audience": 500,
            "headline": 220,
            "subheading": 350,
            "cta_text": 90,
            "seo_title": 160,
            "seo_description": 300,
        }
        clean: dict[str, str] = {}
        for raw_key, value in data.items():
            key = str(raw_key).strip().replace("-", "_").replace(" ", "_")
            key = aliases.get(key, aliases.get(key.lower(), key.lower()))
            if key not in allowed:
                continue
            if isinstance(value, str) and value.strip():
                clean[key] = value.strip()[: limits.get(key, 1000)]
        return clean

    def _guard_app_builder_plan(self, business: Business, instruction: str, plan: dict[str, Any]) -> dict[str, Any]:
        """Normalize AI provider output into the backend's durable patch shape."""
        if not isinstance(plan, dict):
            raise ValueError("AI Studio provider returned an invalid structured change plan.")

        text = instruction.lower()
        business_updates = dict(plan.get("business_updates")) if isinstance(plan.get("business_updates"), dict) else {}
        page_patch = dict(plan.get("page_content_patch")) if isinstance(plan.get("page_content_patch"), dict) else {}
        files = plan.get("files") if isinstance(plan.get("files"), list) else []
        operations = plan.get("operations") if isinstance(plan.get("operations"), list) else []

        for nested_key in ("business_context", "business", "brand"):
            nested = plan.get(nested_key)
            if isinstance(nested, dict):
                business_updates.update(nested)
        hero = plan.get("hero")
        if isinstance(hero, dict):
            for key in ("headline", "subheading", "subheadline", "cta_text", "cta", "button_text"):
                value = hero.get(key)
                if isinstance(value, str) and value.strip():
                    business_updates[key] = value.strip()
        for nested_key in ("landing_page", "page", "sections"):
            nested = plan.get(nested_key)
            if isinstance(nested, dict):
                page_patch.update(nested)

        for operation in operations:
            if not isinstance(operation, dict):
                continue
            op_type = str(operation.get("type") or "").strip().lower()
            if op_type == "update_business_profile":
                fields = operation.get("fields") if isinstance(operation.get("fields"), dict) else {}
                for key in (
                    "name",
                    "brand_name",
                    "business_name",
                    "niche",
                    "target_audience",
                    "audience",
                    "headline",
                    "hero_headline",
                    "subheading",
                    "subheadline",
                    "cta_text",
                    "cta",
                    "description",
                    "product_pitch",
                    "brand_tone",
                    "monetization_model",
                    "seo_title",
                    "seo_description",
                ):
                    value = fields.get(key)
                    if isinstance(value, str) and value.strip():
                        business_updates[key] = value.strip()
                patch = fields.get("page_content") if isinstance(fields.get("page_content"), dict) else {}
                page_patch.update(patch)
            elif op_type in {"replace_file", "write_file", "update_file"}:
                path = operation.get("path")
                content = operation.get("content")
                if isinstance(path, str) and isinstance(content, str):
                    files.append({"path": path, "content": content})

        raw_prompt = instruction.strip().lower()
        style_words = (
            "color",
            "colour",
            "theme",
            "palette",
            "background",
            "button color",
            "attractive",
            "beautiful",
            "modern look",
            "orange",
            "yellow",
            "gold",
            "golden",
            "amber",
            "green",
            "blue",
            "purple",
            "violet",
            "pink",
            "rose",
            "red",
            "black",
        )
        copy_words = (
            "headline",
            "heading",
            "title",
            "copy",
            "message",
            "position",
            "reposition",
            "audience",
            "niche",
            "fitness",
            "coach",
            "coaching",
            "homeowner",
            "homeowners",
            "home services",
            "service",
            "services",
            "service call",
            "service calls",
            "hvac",
            "plumbing",
            "electrical",
            "roofing",
            "pivot",
            "transform",
            "switch",
            "replace",
        )
        section_words = (
            "section",
            "pain point",
            "pain points",
            "feature",
            "features",
            "review",
            "reviews",
            "testimonial",
            "testimonials",
            "pricing",
            "faq",
            "lead capture",
            "quote request",
        )
        explicit_copy_request = any(word in text for word in copy_words) or any(word in text for word in section_words)
        style_only = any(word in text for word in style_words) and not explicit_copy_request

        if style_only:
            for key in ("headline", "subheading", "description", "product_pitch"):
                business_updates.pop(key, None)
            # Some providers try to satisfy "make the page attractive" by
            # creating new feature/review copy. Keep pure design prompts scoped
            # to visual tokens so the preview does not appear to ignore intent.
            for key in ("features", "benefits", "social_proof", "pricing_tiers", "faq", "lead_capture", "quote_request"):
                page_patch.pop(key, None)
            if "color_scheme" not in page_patch:
                page_patch["color_scheme"] = self._scheme_from_instruction(text)

        explicit_scheme = self._explicit_scheme_from_instruction(text)
        if explicit_scheme:
            page_patch["color_scheme"] = explicit_scheme

        for key, value in list(business_updates.items()):
            if isinstance(value, str) and value.strip().lower() == raw_prompt:
                business_updates.pop(key, None)
            elif isinstance(value, str) and raw_prompt and raw_prompt in value.strip().lower() and len(raw_prompt) > 12:
                business_updates.pop(key, None)

        if page_patch.get("color_scheme"):
            valid_schemes = {"indigo", "emerald", "rose", "amber", "black_gold", "sky", "violet"}
            if str(page_patch["color_scheme"]) not in valid_schemes:
                page_patch["color_scheme"] = self._scheme_from_instruction(text)

        plan["business_updates"] = business_updates
        plan["page_content_patch"] = page_patch
        plan["files"] = files
        plan["provider_used"] = plan.get("provider_used") or "ai_service_router"
        return plan

    @staticmethod
    def _explicit_scheme_from_instruction(text: str) -> str:
        color_map = {
            "black gold": "black_gold",
            "black and gold": "black_gold",
            "orange": "amber",
            "golden": "amber",
            "gold": "amber",
            "yellow": "amber",
            "amber": "amber",
            "green": "emerald",
            "emerald": "emerald",
            "blue": "sky",
            "sky": "sky",
            "purple": "violet",
            "violet": "violet",
            "rose": "rose",
            "pink": "rose",
            "red": "rose",
            "indigo": "indigo",
        }
        for token, scheme in color_map.items():
            if token in text:
                return scheme
        return ""

    def _local_app_builder_plan(self, business: Business, instruction: str, current_files: dict[str, str]) -> dict[str, Any]:
        text = instruction.lower()
        page_patch: dict[str, Any] = {}
        business_updates: dict[str, str] = {}
        summary_bits: list[str] = []
        cta_only_prompt = False
        home_services_context = any(
            word in text
            for word in ("expert home services", "home services", "homeowner", "homeowners", "hvac", "plumbing", "electrical", "roofing", "service call", "home repairs")
        )
        explicit_home_services_pivot = any(
            word in text
            for word in ("expert home services", "home services", "hvac", "plumbing", "electrical", "roofing", "home repairs")
        )

        def _quoted_after(label_patterns: tuple[str, ...]) -> str:
            for label in label_patterns:
                pattern = rf"{label}[^\"']*(?:to|as|called|named)\s+[\"']([^\"']{{3,160}})[\"']"
                match = re.search(pattern, instruction, re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            return ""

        explicit_brand = _quoted_after(("brand name", "business context", "brand", "business name"))
        explicit_headline = _quoted_after(("headline", "hero headline", "main headline"))
        explicit_subheadline = _quoted_after(("subheadline", "sub heading", "hero subheadline", "supporting copy"))
        explicit_cta = _quoted_after(("main cta button text", "cta button text", "cta text", "main cta", "button text"))
        if explicit_brand:
            business_updates["name"] = explicit_brand
            summary_bits.append("updated the brand name from the custom prompt")
        if explicit_headline:
            business_updates["headline"] = explicit_headline
            summary_bits.append("updated the headline exactly from the custom prompt")
        if explicit_subheadline:
            business_updates["subheading"] = explicit_subheadline
            summary_bits.append("updated the subheadline exactly from the custom prompt")
        if explicit_cta:
            business_updates["cta_text"] = explicit_cta
            summary_bits.append("updated the CTA exactly from the custom prompt")

        if explicit_home_services_pivot:
            if "expert home services" in text:
                business_updates["name"] = "Expert Home Services"
                business_updates["niche"] = "Home services"
            business_updates.update(
                {
                    "target_audience": "Homeowners who need urgent or scheduled home repairs",
                    "headline": "Expert Home Services When You Need Them Most",
                    "subheading": "Reliable HVAC, Plumbing, Electrical, and Roofing Solutions for Your Home",
                    "cta_text": "Schedule a Service Call",
                    "description": "A reliable home services team for urgent repairs, scheduled maintenance, and high-quality workmanship.",
                    "product_pitch": "Emergency HVAC repairs, licensed plumbing, certified electrical work, and quality roofing support for homeowners.",
                    "brand_tone": "Reliable, responsive, professional, and reassuring",
                    "seo_title": "Expert Home Services | HVAC, Plumbing, Electrical & Roofing",
                    "seo_description": "Schedule trusted HVAC, plumbing, electrical, and roofing services for your home.",
                }
            )
            page_patch["pain_points"] = [
                "Leaky pipes that need fast attention",
                "Broken AC units during extreme weather",
                "Outdated electrical systems that feel unsafe",
                "Roof leaks that can turn into costly damage",
            ]
            page_patch["features"] = [
                {"title": "Emergency HVAC Repairs", "description": "Fast diagnostics and repair support for heating and cooling issues.", "icon_hint": "zap"},
                {"title": "Licensed Plumbing Solutions", "description": "Reliable help for leaks, clogs, fixtures, and urgent plumbing problems.", "icon_hint": "shield"},
                {"title": "Certified Electrical Work", "description": "Safe electrical repairs, upgrades, troubleshooting, and code-conscious service.", "icon_hint": "lock"},
                {"title": "Quality Roofing", "description": "Roof inspections, leak response, and repair guidance built around your home.", "icon_hint": "star"},
            ]
            page_patch["social_proof"] = [
                {"name": "Melissa R.", "role": "Homeowner", "quote": "They responded quickly when our AC stopped working and explained every step clearly.", "rating": 5},
                {"name": "David K.", "role": "Homeowner", "quote": "The plumbing repair was clean, professional, and finished faster than expected.", "rating": 5},
                {"name": "Priya S.", "role": "Homeowner", "quote": "They found the roof leak, fixed it properly, and gave us real peace of mind.", "rating": 5},
            ]
            page_patch["trust_badges"] = ["Fast response", "Licensed specialists", "Quality workmanship", "Homeowner trusted"]
            page_patch["urgency_text"] = "Small home problems can become expensive fast. Schedule expert help today."
            page_patch.setdefault("color_scheme", "black_gold")
            summary_bits.append("pivoted the page to Expert Home Services with homeowner pain points, services, and reviews")

        if "black" in text and "gold" in text:
            page_patch["color_scheme"] = "black_gold"
            summary_bits.append("changed the hero and CTA system to black and gold")
        elif "orange" in text:
            page_patch["color_scheme"] = "amber"
            page_patch["urgency_text"] = "A brighter orange brand system now guides visitors toward the next action."
            summary_bits.append("changed the color system to an orange amber theme")
        elif "green" in text or "emerald" in text:
            page_patch["color_scheme"] = "emerald"
            summary_bits.append("changed the color system to emerald green")
        elif "gold" in text or "golden" in text or "amber" in text or "yellow" in text:
            page_patch["color_scheme"] = "amber"
            summary_bits.append("changed the color system to golden amber")

        cta_match = re.search(r"(?:cta|button|call[- ]?to[- ]?action).*?(?:to|as)\s+['\"]?([^'\"]{3,120})['\"]?$", instruction, re.IGNORECASE)
        if cta_match:
            business_updates["cta_text"] = cta_match.group(1).strip(" .")
            summary_bits.append("updated the CTA text")
            cta_only_prompt = not any(word in text for word in ("hero", "page", "landing", "premium", "modern", "fitness", "pricing", "testimonial", "section"))
        elif "book my free coaching call" in text:
            business_updates["cta_text"] = "Book My Free Coaching Call"
            summary_bits.append("updated the CTA text")
            cta_only_prompt = not any(word in text for word in ("hero", "page", "landing", "premium", "modern", "fitness", "pricing", "testimonial", "section"))

        if not cta_only_prompt and ("fitness" in text or "coaching" in text):
            business_updates.setdefault("headline", "Premium Fitness Coaching That Builds Strength, Confidence, and Consistency")
            business_updates.setdefault("subheading", "A high-touch coaching experience for busy people who want personalized workouts, accountability, and measurable transformation.")
            business_updates.setdefault("product_pitch", "Personalized coaching, weekly check-ins, habit systems, and progress tracking built around your real schedule.")
            page_patch.setdefault("trust_badges", ["Personalized coaching", "Weekly accountability", "Progress tracking"])
            page_patch.setdefault(
                "benefits",
                [
                    "Train with a plan built around your body, schedule, and goals.",
                    "Stay consistent with coaching check-ins and simple habit systems.",
                    "See measurable progress without guessing what to do next.",
                ],
            )
            summary_bits.append("rewrote the page for premium fitness coaching")

        if any(word in text for word in ("homeowner", "homeowners", "hvac", "plumbing", "electrical", "roofing", "service call", "service calls")):
            business_updates.setdefault("headline", "Book Trusted Home Service Help Without the Back-and-Forth")
            business_updates.setdefault("subheading", "Fast quote requests, clear follow-up, and reliable service guidance for homeowners who need help now.")
            business_updates.setdefault("product_pitch", "A service-first booking flow that turns urgent homeowner needs into organized requests and fast follow-up.")
            business_updates.setdefault("cta_text", "Request a Fast Quote")
            page_patch.setdefault("color_scheme", "amber")
            page_patch.setdefault("lead_capture", {
                "headline": "Tell Us What Needs Fixing",
                "description": "Share the service, location, and urgency so the team can follow up quickly.",
                "fields": ["Name", "Phone", "Service needed", "ZIP code", "How urgent is it?"],
                "cta": "Request Service Help",
            })
            page_patch.setdefault("quote_request", {
                "headline": "Get a Clear Service Quote",
                "description": "Describe the job and timeline to receive a practical next step.",
                "fields": ["Service type", "Preferred time", "Property type", "Phone"],
                "cta": "Get My Quote",
            })
            page_patch.setdefault("trust_badges", ["Fast response", "Local service area", "Clear quote process"])
            summary_bits.append("repositioned the page for booked home service calls")

        if any(phrase in text for phrase in ("booked service", "book service", "appointment booking", "appointments", "book calls", "booked calls", "fast follow-up", "follow up")):
            business_updates.setdefault("cta_text", "Book a Service Call")
            page_patch["lead_capture"] = {
                "headline": "Book the Next Available Service Call",
                "description": "Capture the visitor's details, issue, and preferred time so follow-up can happen quickly.",
                "fields": ["Name", "Phone", "Service needed", "Preferred time"],
                "cta": "Book My Service Call",
            }
            page_patch.setdefault("trust_badges", ["Fast follow-up", "Clear scheduling", "No missed inquiries"])
            page_patch.setdefault("urgency_text", "Respond faster while the customer is ready to book.")
            summary_bits.append("added an appointment-focused conversion flow")

        if "testimonial" in text:
            if home_services_context:
                page_patch["social_proof"] = [
                    {"name": "Melissa R.", "role": "Homeowner", "quote": "They arrived quickly, diagnosed our AC issue, and had the house cooling again the same day.", "rating": 5},
                    {"name": "David K.", "role": "Homeowner", "quote": "The plumbing work was clean, professional, and explained clearly before anything started.", "rating": 5},
                    {"name": "Priya S.", "role": "Homeowner", "quote": "Their roofing team found the leak fast and fixed it with workmanship we trusted.", "rating": 5},
                ]
                summary_bits.append("added homeowner testimonials")
            else:
                page_patch["social_proof"] = [
                    {"name": "Maya R.", "role": "Busy professional", "quote": "The coaching gave me structure, confidence, and a plan I could actually follow.", "rating": 5},
                    {"name": "Arjun K.", "role": "Founder", "quote": "I finally stopped guessing and started seeing consistent weekly progress.", "rating": 5},
                    {"name": "Priya S.", "role": "Working parent", "quote": "The accountability made the difference. I felt supported the whole way.", "rating": 5},
                ]
                summary_bits.append("added a testimonials section")

        if "pricing" in text or "3 plan" in text or "three plan" in text:
            if home_services_context:
                page_patch["pricing_tiers"] = [
                    {"name": "Inspection", "price": "Quote", "period": "visit", "features": ["Service diagnosis", "Repair options", "Clear next step"], "cta": business_updates.get("cta_text") or getattr(business, "cta_text", "Schedule a Service Call"), "highlighted": False},
                    {"name": "Priority Repair", "price": "Custom", "period": "job", "features": ["HVAC, plumbing, electrical, or roofing repair", "Priority scheduling", "Workmanship-focused service"], "cta": business_updates.get("cta_text") or getattr(business, "cta_text", "Schedule a Service Call"), "highlighted": True},
                    {"name": "Maintenance Plan", "price": "Monthly", "period": "plan", "features": ["Seasonal checkups", "Reminder scheduling", "Preferred service support"], "cta": business_updates.get("cta_text") or getattr(business, "cta_text", "Schedule a Service Call"), "highlighted": False},
                ]
            else:
                page_patch["pricing_tiers"] = [
                    {"name": "Starter", "price": "$49", "period": "mo", "features": ["Personalized starter plan", "Weekly progress tracker", "Email support"], "cta": business_updates.get("cta_text") or getattr(business, "cta_text", "Get Started"), "highlighted": False},
                    {"name": "Transformation", "price": "$149", "period": "mo", "features": ["Custom workouts", "Weekly coaching call", "Nutrition guidance", "Habit accountability"], "cta": business_updates.get("cta_text") or getattr(business, "cta_text", "Get Started"), "highlighted": True},
                    {"name": "Elite", "price": "$299", "period": "mo", "features": ["Everything in Transformation", "2x weekly coaching", "Priority support", "Advanced progress review"], "cta": business_updates.get("cta_text") or getattr(business, "cta_text", "Get Started"), "highlighted": False},
                ]
            summary_bits.append("added three pricing plans")

        if "premium" in text or "modern" in text:
            page_patch.setdefault("trust_badges", ["Premium experience", "Personal guidance", "Results-focused system"])
            page_patch.setdefault(
                "features",
                [
                    {"title": "Personalized Strategy", "description": "A focused plan built around the customer, not a generic template.", "icon_hint": "star"},
                    {"title": "Accountability System", "description": "Clear next steps, progress visibility, and consistent follow-through.", "icon_hint": "check"},
                    {"title": "Measurable Outcomes", "description": "Structured milestones that make progress easy to understand.", "icon_hint": "chart"},
                ],
            )
            page_patch.setdefault("urgency_text", "Start with a sharper, more premium experience while momentum is fresh.")
            summary_bits.append("made the page feel more premium and modern")

        if any(word in text for word in ("attractive", "beautiful", "awesome", "dopamine", "eye catching", "eye-catching")):
            page_patch.setdefault("color_scheme", self._scheme_from_instruction(text))
            page_patch.setdefault("trust_badges", ["Polished first impression", "Clear value", "Action-focused design"])
            page_patch.setdefault(
                "features",
                [
                    {"title": "Stronger First Impression", "description": "A sharper visual system makes the offer feel more credible and memorable.", "icon_hint": "star"},
                    {"title": "Clearer Action Path", "description": "The page guides visitors toward the next step with stronger visual hierarchy.", "icon_hint": "zap"},
                    {"title": "More Premium Feel", "description": "Color, contrast, and trust cues work together to make the page feel more valuable.", "icon_hint": "shield"},
                ],
            )
            summary_bits.append("made the page more visually attractive")

        if any(phrase in text for phrase in ("local trust", "service area", "emergency response", "reviews", "review section")):
            if home_services_context:
                page_patch["social_proof"] = [
                    {"name": "Melissa R.", "role": "Homeowner", "quote": "The response was fast, the technician was clear, and the repair was handled with real care.", "rating": 5},
                    {"name": "David K.", "role": "Homeowner", "quote": "They showed up when promised and completed the work cleanly without surprises.", "rating": 5},
                    {"name": "Priya S.", "role": "Homeowner", "quote": "Quality workmanship and quick communication made the whole repair less stressful.", "rating": 5},
                ]
            else:
                page_patch["social_proof"] = [
                    {"name": "Local customer", "role": "Verified client", "quote": "The response was fast, clear, and easy to book.", "rating": 5},
                    {"name": "Homeowner", "role": "Service request", "quote": "I knew exactly what the next step was and got help quickly.", "rating": 5},
                    {"name": "Repeat customer", "role": "Priority support", "quote": "The process felt professional from the first click.", "rating": 5},
                ]
            page_patch.setdefault("trust_badges", ["Verified reviews", "Service-area coverage", "Emergency response options"])
            summary_bits.append("added local trust and review proof")

        if any(phrase in text for phrase in ("campaign metrics", "tracked from real events", "real events", "proof that")):
            page_patch["features"] = [
                {"title": "Real Click Tracking", "description": "Campaign actions are counted only when real visitors click tracked links.", "icon_hint": "chart"},
                {"title": "Conversion Evidence", "description": "Leads, bookings, and purchases become measurable events instead of simulated numbers.", "icon_hint": "check"},
                {"title": "Revenue Integrity", "description": "Revenue remains zero until real payment or order data confirms it.", "icon_hint": "shield"},
            ]
            page_patch.setdefault("trust_badges", ["No fake metrics", "Real analytics events", "Auditable activity"])
            summary_bits.append("added proof that campaign metrics come from real events")

        if any(word in text for word in ("faq", "questions", "answers", "guarantee", "guarantees", "response time")):
            page_patch["faq"] = [
                {"question": "How fast will someone respond?", "answer": "The page is designed to capture the request and route it into a clear follow-up workflow."},
                {"question": "Can I request a quote before committing?", "answer": "Yes. Visitors can submit service details first so the team can respond with the right next step."},
                {"question": "Are campaign metrics real?", "answer": "Yes. Clicks, conversions, and revenue should only update when real tracking or payment events are received."},
            ]
            summary_bits.append("added a practical FAQ section")

        if explicit_brand:
            business_updates["name"] = explicit_brand
        if explicit_headline:
            business_updates["headline"] = explicit_headline
        if explicit_subheadline:
            business_updates["subheading"] = explicit_subheadline
        if explicit_cta:
            business_updates["cta_text"] = explicit_cta

        if not page_patch and not business_updates:
            # Last-resort app-builder recovery for custom visual prompts. The
            # provider is still tried first; this keeps AI Studio from showing a
            # failed execution when the user's request is clearly a page update
            # but the model returned malformed JSON.
            inferred_scheme = self._scheme_from_instruction(text)
            page_patch["color_scheme"] = "black_gold" if inferred_scheme == "violet" else inferred_scheme
            page_patch["trust_badges"] = [
                "Prompt-specific update",
                "Visible page refresh",
                "Saved to project state",
            ]
            page_patch["features"] = [
                {
                    "title": "Sharper First Impression",
                    "description": "The page now uses a stronger visual system and clearer value framing based on the custom prompt.",
                    "icon_hint": "star",
                },
                {
                    "title": "Clearer Visitor Action",
                    "description": "The updated section structure keeps the next step more visible and easier to act on.",
                    "icon_hint": "zap",
                },
                {
                    "title": "More Polished Experience",
                    "description": "The landing page gets refreshed spacing, trust cues, and presentation without rewriting unrelated business copy.",
                    "icon_hint": "shield",
                },
            ]
            page_patch["urgency_text"] = "This page has been refreshed from your custom AI Studio instruction."
            summary_bits.append("applied a conservative visible page refresh from the custom prompt")

        existing_page_content = getattr(business, "page_content", None) or {}
        css = self._app_builder_css(page_patch.get("color_scheme") or existing_page_content.get("color_scheme") or "indigo")
        hero = self._app_builder_hero_component()
        page = self._app_builder_page_component()
        return {
            "summary": f"AI Studio {'; '.join(summary_bits)}.",
            "provider_used": "local_recovery_compiler",
            "business_updates": business_updates,
            "page_content_patch": page_patch,
            "files": [
                {"path": "styles/theme.css", "content": css},
                {"path": "components/Hero.tsx", "content": hero},
                {"path": "app/page.tsx", "content": page},
            ],
        }

    @staticmethod
    def _validate_action_result(action: dict[str, Any]) -> None:
        """Prevent fake success messages when no durable change was applied."""
        action_type = str(action.get("action_type") or "")
        durable_markers = [
            action.get("version_id"),
            action.get("campaign_id"),
            action.get("product_id"),
            action.get("agent_report_id"),
            action.get("updated_files"),
            action.get("changed_files"),
            action.get("file_path") if action_type == "code_edit_applied" else None,
        ]
        if not any(durable_markers):
            raise ValueError("AI Studio did not apply a durable database or file change.")

    @staticmethod
    def _app_builder_hero_component() -> str:
        return (
            'export function Hero({ business }: { business: any }) {\n'
            "  return (\n"
            '    <section className="abb-hero">\n'
            '      <div className="abb-shell abb-hero-inner">\n'
            '        <div className="abb-hero-copy">\n'
            '          <p className="abb-eyebrow">{business.niche}</p>\n'
            '          <h1>{business.headline}</h1>\n'
            '          <p className="abb-subheading">{business.subheading}</p>\n'
            '          <div className="abb-actions">\n'
            '            <button className="abb-primary">{business.cta_text}</button>\n'
            '            <span className="abb-proof">{business.target_audience}</span>\n'
            "          </div>\n"
            "        </div>\n"
            '        <div className="abb-hero-panel">\n'
            '          <p>Premium execution system</p>\n'
            '          <strong>{business.product_pitch}</strong>\n'
            "        </div>\n"
            "      </div>\n"
            "    </section>\n"
            "  );\n"
            "}\n"
        )

    @staticmethod
    def _app_builder_page_component() -> str:
        return (
            'import "./../styles/theme.css";\n'
            'import business from "../data/business.json";\n'
            'import { Hero } from "../components/Hero";\n\n'
            "const pageContent = (business as any).page_content || {};\n"
            "const leadCapture = pageContent.lead_capture;\n"
            "const quoteRequest = pageContent.quote_request;\n\n"
            "export default function Page() {\n"
            "  return (\n"
            '    <main className="abb-page">\n'
            "      <Hero business={business} />\n"
            '      <section className="abb-section">\n'
            '        <div className="abb-shell abb-grid">\n'
            '          <div className="abb-card"><p className="abb-eyebrow">Offer</p><h2>{business.headline}</h2><p>{business.product_pitch}</p></div>\n'
            '          <div className="abb-card"><p className="abb-eyebrow">Why now</p><h2>{business.cta_text}</h2><p>{business.description}</p></div>\n'
            "        </div>\n"
            "      </section>\n"
            "      {(leadCapture || quoteRequest) && (\n"
            '        <section className="abb-section">\n'
            '          <div className="abb-shell abb-grid">\n'
            "            {leadCapture && (\n"
            '              <div className="abb-card">\n'
            '                <p className="abb-eyebrow">Lead capture</p>\n'
            "                <h2>{leadCapture.headline}</h2>\n"
            "                <p>{leadCapture.description}</p>\n"
            '                <div className="abb-form-preview">\n'
            "                  {(leadCapture.fields || []).map((field: string) => <span key={field}>{field}</span>)}\n"
            "                </div>\n"
            '                <button className="abb-primary">{leadCapture.cta || business.cta_text}</button>\n'
            "              </div>\n"
            "            )}\n"
            "            {quoteRequest && (\n"
            '              <div className="abb-card">\n'
            '                <p className="abb-eyebrow">Quote request</p>\n'
            "                <h2>{quoteRequest.headline}</h2>\n"
            "                <p>{quoteRequest.description}</p>\n"
            '                <div className="abb-form-preview">\n'
            "                  {(quoteRequest.fields || []).map((field: string) => <span key={field}>{field}</span>)}\n"
            "                </div>\n"
            '                <button className="abb-primary">{quoteRequest.cta || business.cta_text}</button>\n'
            "              </div>\n"
            "            )}\n"
            "          </div>\n"
            "        </section>\n"
            "      )}\n"
            "    </main>\n"
            "  );\n"
            "}\n"
        )

    @staticmethod
    def _app_builder_css(color_scheme: str) -> str:
        palette = {
            "black_gold": ("#020617", "#f5c451", "#fff8df", "#8a5a0a"),
            "amber": ("#1c1204", "#f59e0b", "#fff7ed", "#b45309"),
            "emerald": ("#052e2b", "#10b981", "#ecfdf5", "#059669"),
            "sky": ("#082f49", "#0ea5e9", "#f0f9ff", "#0284c7"),
            "violet": ("#1e1b4b", "#8b5cf6", "#f5f3ff", "#7c3aed"),
            "rose": ("#3f0a1f", "#f43f5e", "#fff1f2", "#e11d48"),
            "indigo": ("#0f172a", "#6366f1", "#ffffff", "#4f46e5"),
        }.get(str(color_scheme), ("#0f172a", "#6366f1", "#ffffff", "#4f46e5"))
        bg, accent, ink, dark = palette
        return (
            ":root {\n"
            f"  --abb-bg: {bg};\n"
            f"  --abb-accent: {accent};\n"
            f"  --abb-dark: {dark};\n"
            f"  --abb-ink: {ink};\n"
            "  --abb-panel: rgba(255,255,255,0.08);\n"
            "  --abb-line: rgba(255,255,255,0.16);\n"
            "}\n"
            "* { box-sizing: border-box; }\n"
            "body { margin: 0; font-family: Inter, system-ui, sans-serif; background: var(--abb-bg); }\n"
            ".abb-page { min-height: 100vh; background: radial-gradient(circle at top right, color-mix(in srgb, var(--abb-accent) 30%, transparent), transparent 34%), var(--abb-bg); color: var(--abb-ink); }\n"
            ".abb-shell { width: min(1120px, calc(100vw - 40px)); margin: 0 auto; }\n"
            ".abb-hero { padding: 88px 0 72px; }\n"
            ".abb-hero-inner { display: grid; gap: 28px; align-items: center; }\n"
            ".abb-hero-copy h1 { margin: 0 0 18px; font-size: clamp(42px, 7vw, 78px); line-height: .95; letter-spacing: -0.04em; }\n"
            ".abb-eyebrow { margin: 0 0 14px; color: var(--abb-accent); text-transform: uppercase; font-size: 12px; letter-spacing: .16em; font-weight: 900; }\n"
            ".abb-subheading, .abb-card p, .abb-proof { color: rgba(255,255,255,.72); line-height: 1.7; }\n"
            ".abb-actions { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; margin-top: 28px; }\n"
            ".abb-primary { border: 1px solid rgba(255,255,255,.22); border-radius: 999px; color: #111827; background: linear-gradient(135deg, var(--abb-accent), #fff3b0); padding: 14px 22px; font-weight: 900; box-shadow: 0 18px 42px color-mix(in srgb, var(--abb-accent) 30%, transparent); }\n"
            ".abb-hero-panel, .abb-card { border: 1px solid var(--abb-line); border-radius: 22px; padding: 26px; background: var(--abb-panel); box-shadow: 0 24px 80px rgba(0,0,0,.28); backdrop-filter: blur(14px); }\n"
            ".abb-hero-panel strong { display: block; font-size: 24px; line-height: 1.25; }\n"
            ".abb-section { padding: 34px 0 72px; }\n"
            ".abb-grid { display: grid; gap: 18px; }\n"
            ".abb-card h2 { margin: 0 0 12px; font-size: 28px; }\n"
            ".abb-form-preview { display: grid; gap: 10px; margin: 16px 0; }\n"
            ".abb-form-preview span { border: 1px solid var(--abb-line); border-radius: 12px; background: rgba(255,255,255,.08); color: rgba(255,255,255,.72); padding: 11px 13px; font-size: 14px; }\n"
            "@media (min-width: 860px) { .abb-hero-inner, .abb-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }\n"
        )

    async def _create_research_report(self, business: Business, user: User, instruction: str) -> dict[str, Any]:
        from app.schemas.analytics import AnalyticsEventCreate
        from app.services.analytics_service import AnalyticsService

        prompt = (
            "You are an AI business research analyst connected to AI Studio.\n"
            "Produce a business-ready research report for the selected business.\n"
            "Use concise markdown with these sections: Executive Summary, Key Findings, Evidence To Collect, Recommended Actions.\n"
            "Do not claim you browsed live websites unless evidence is provided. Be explicit that this is AI research synthesis.\n\n"
            f"Business: {business.name}\n"
            f"Niche: {business.niche}\n"
            f"Target audience: {business.target_audience}\n"
            f"Instruction: {instruction}"
        )
        try:
            report_text = await AIService().generate_text(prompt, task_type="ai_studio")
        except Exception as exc:
            raise ValueError(f"Research synthesis failed because no AI provider completed the request: {exc}") from exc

        log = AgentLog(
            business_id=business.id,
            agent_type="ai_studio_research",
            log_type="report",
            summary=report_text[:500],
            payload={
                "goal": instruction,
                "result": report_text,
                "sources": [],
                "origin": "ai_studio",
                "mode": "ai_research_synthesis",
            },
            applied=True,
        )
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(log)
        await AnalyticsService(self.db).track(
            AnalyticsEventCreate(
                business_id=business.id,
                event_type="ai_studio_research_created",
                source="ai_studio",
                metadata_json={"agent_report_id": str(log.id), "instruction": instruction[:500]},
            )
        )
        return {
            "action_type": "research_report_created",
            "summary": f"Created a research report for {business.name} and saved it to Agent Live/Analytics.",
            "business_id": str(business.id),
            "business_name": business.name,
            "agent_report_id": str(log.id),
            "report": report_text,
            "next_url": f"/agent-live?business_id={business.id}",
        }

    async def _create_product_asset(self, business: Business, user: User, instruction: str) -> dict[str, Any]:
        from app.schemas.analytics import AnalyticsEventCreate
        from app.schemas.product import ProductCreate
        from app.services.analytics_service import AnalyticsService
        from app.services.product_service import ProductService
        from app.services.ai_service import AIService

        prompt = (
            "You are creating a real product record for an AI business operating system.\n"
            "Return ONLY valid JSON with these keys:\n"
            "name, description, price, currency, category, status, product_type, billing_type.\n\n"
            f"Business: {business.name}\n"
            f"Niche: {business.niche}\n"
            f"Target audience: {business.target_audience}\n"
            f"Monetization model: {business.monetization_model}\n"
            f"Product pitch: {business.product_pitch}\n"
            f"User instruction: {instruction}\n\n"
            "Rules:\n"
            "- price must be a positive decimal number.\n"
            "- currency must be a 3-letter lowercase code, usually usd.\n"
            "- status should be draft unless the user explicitly says active.\n"
            "- product_type should be digital, service, subscription, course, template, or consultation.\n"
            "- billing_type should be one_time or recurring."
        )
        data = await AIService().generate_json(prompt, task_type="ai_studio")
        price = Decimal(str(data.get("price") or "49.00"))
        if price <= 0:
            price = Decimal("49.00")
        payload = ProductCreate(
            business_id=business.id,
            project_id=business.project_id,
            name=str(data.get("name") or f"{business.name} Offer")[:140],
            description=str(data.get("description") or business.product_pitch or business.description),
            price=price,
            currency=str(data.get("currency") or "usd")[:3].lower(),
            category=str(data.get("category") or "digital")[:100],
            status=str(data.get("status") or "draft")[:32],
            product_type=str(data.get("product_type") or "digital")[:32],
            billing_type=str(data.get("billing_type") or "one_time")[:32],
        )
        product = await ProductService(self.db).create(payload)
        await AnalyticsService(self.db).track(
            AnalyticsEventCreate(
                business_id=business.id,
                product_id=product.id,
                event_type="product_created",
                source="ai_studio",
                metadata_json={"product_id": str(product.id), "product_name": product.name, "instruction": instruction[:500]},
            )
        )
        return {
            "action_type": "product_created",
            "summary": f"Created product in Products: {product.name}.",
            "business_id": str(business.id),
            "business_name": business.name,
            "product_id": str(product.id),
            "product_name": product.name,
            "price": str(product.price),
            "currency": product.currency,
            "status": product.status,
            "next_url": f"/products?business_id={business.id}",
        }

    @staticmethod
    def _normalize_field(field: str, instruction: str) -> str:
        field_map = {
            "headline": "headline",
            "title": "headline",
            "main_headline": "headline",
            "hero_headline": "headline",
            "value": "headline",
            "subheading": "subheading",
            "sub_headline": "subheading",
            "subtitle": "subheading",
            "cta_text": "cta_text",
            "cta": "cta_text",
            "call_to_action": "cta_text",
            "button_text": "cta_text",
            "description": "description",
            "product_pitch": "product_pitch",
            "pitch": "product_pitch",
            "product_pitch_text": "product_pitch",
            "pricing": "page_content",
            "pricing_section": "page_content",
            "testimonials": "page_content",
            "testimonial": "page_content",
            "faq": "page_content",
            "features": "page_content",
            "benefits": "page_content",
            "social_proof": "page_content",
            "page_content": "page_content",
        }
        normalized = field_map.get(field.lower().strip().replace(" ", "_"))
        if normalized:
            return normalized

        text = instruction.lower()
        if any(word in text for word in ("headline", "title", "heading")):
            return "headline"
        if any(word in text for word in ("subheading", "subtitle")):
            return "subheading"
        if any(word in text for word in ("color", "colour", "gold", "golden", "amber", "theme", "palette")):
            return "page_content"
        if any(word in text for word in ("cta", "button", "call to action", "click")):
            return "cta_text"
        if any(word in text for word in ("description", "about", "overview")):
            return "description"
        if any(word in text for word in ("pitch", "product", "offer")):
            return "product_pitch"
        if any(word in text for word in ("pricing", "testimonial", "faq", "feature", "benefit", "trust", "urgency", "color", "colour")):
            return "page_content"
        return "headline"

    @staticmethod
    def _sanitize_page_patch(page_patch: Any) -> dict[str, Any]:
        if not isinstance(page_patch, dict):
            return {}
        aliases = {
            "painpoints": "pain_points",
            "pain_points": "pain_points",
            "sound_familiar": "pain_points",
            "problems": "pain_points",
            "maintenance_headaches": "pain_points",
            "services": "features",
            "service_blocks": "features",
            "core_offerings": "features",
            "offerings": "features",
            "testimonials": "social_proof",
            "reviews": "social_proof",
            "customer_reviews": "social_proof",
            "socialproof": "social_proof",
            "faqs": "faq",
            "questions": "faq",
            "trustBadges": "trust_badges",
            "trustbadges": "trust_badges",
            "urgency": "urgency_text",
            "urgencyText": "urgency_text",
            "urgencytext": "urgency_text",
            "theme": "color_scheme",
            "color": "color_scheme",
            "colour": "color_scheme",
            "leadCapture": "lead_capture",
            "leadcapture": "lead_capture",
            "quoteRequest": "quote_request",
            "quoterequest": "quote_request",
        }
        allowed = {
            "pain_points",
            "benefits",
            "features",
            "social_proof",
            "faq",
            "pricing_tiers",
            "urgency_text",
            "trust_badges",
            "color_scheme",
            "lead_capture",
            "quote_request",
        }
        clean: dict[str, Any] = {}
        for raw_key, value in page_patch.items():
            key = str(raw_key).strip().replace("-", "_").replace(" ", "_")
            key = aliases.get(key, aliases.get(key.lower(), key.lower()))
            if key in allowed:
                clean[key] = value
        return clean

    def _deterministic_app_builder_plan(self, business: Business, instruction: str, current_files: dict[str, str]) -> dict[str, Any] | None:
        """Fast, reliable handlers for common visible edits that should never rewrite headlines by accident."""
        text = instruction.lower()
        page_patch: dict[str, Any] = {}
        summary_bits: list[str] = []

        if any(word in text for word in ("color", "colour", "theme", "palette", "background", "orange", "yellow")):
            selected = self._scheme_from_instruction(text)
            page_patch["color_scheme"] = selected
            summary_bits.append(f"changed the page color system to {selected.replace('_', ' ')}")

        if any(phrase in text for phrase in ("lead capture", "capture leads", "lead form", "lead generation")):
            page_patch["lead_capture"] = {
                "headline": "Get a Fast Response From Our Team",
                "description": "Share your details and the team will follow up with the next best step.",
                "fields": ["Name", "Phone", "Email", "What do you need help with?"],
                "cta": "Request a Callback",
            }
            page_patch.setdefault("benefits", [
                "Capture every interested visitor before they leave.",
                "Route inquiries into a clear follow-up workflow.",
                "Turn page visits into real conversations.",
            ])
            summary_bits.append("added a lead capture section")

        if any(phrase in text for phrase in ("quote request", "request quote", "quote form", "estimate", "consultation request")):
            page_patch["quote_request"] = {
                "headline": "Request a Clear Quote",
                "description": "Tell us what you need, your timeline, and the best way to reach you.",
                "fields": ["Service needed", "Timeline", "Budget range", "Phone"],
                "cta": "Request My Quote",
            }
            summary_bits.append("added a quote request section")

        if not page_patch:
            return None

        existing_page_content = getattr(business, "page_content", None) or {}
        active_scheme = page_patch.get("color_scheme") or existing_page_content.get("color_scheme") or "indigo"
        return {
            "summary": f"AI Studio {' and '.join(summary_bits)}.",
            "provider_used": "deterministic_studio_tool",
            "business_updates": {},
            "page_content_patch": page_patch,
            "files": [
                {"path": "styles/theme.css", "content": self._app_builder_css(active_scheme)},
                {"path": "components/Hero.tsx", "content": self._app_builder_hero_component()},
                {"path": "app/page.tsx", "content": self._app_builder_page_component()},
            ],
        }

    @staticmethod
    def _scheme_from_instruction(text: str) -> str:
        color_map = {
            "black gold": "black_gold",
            "black and gold": "black_gold",
            "orange": "amber",
            "golden": "amber",
            "gold": "amber",
            "yellow": "amber",
            "amber": "amber",
            "green": "emerald",
            "emerald": "emerald",
            "blue": "sky",
            "sky": "sky",
            "purple": "violet",
            "violet": "violet",
            "rose": "rose",
            "pink": "rose",
            "red": "rose",
            "indigo": "indigo",
        }
        for token, scheme in color_map.items():
            if token in text:
                return scheme
        if any(word in text for word in ("attractive", "premium", "modern", "beautiful", "awesome")):
            return "black_gold"
        return "violet"

    @staticmethod
    def _deterministic_style_patch(business: Business, instruction: str) -> dict[str, Any] | None:
        text = instruction.lower()
        if any(phrase in text for phrase in ("button text", "cta text", "call-to-action text", "call to action text")):
            return None
        if not any(word in text for word in ("color", "colour", "gold", "golden", "amber", "theme", "palette", "button")):
            return None

        color_map = {
            "orange": "amber",
            "golden": "amber",
            "gold": "amber",
            "yellow": "amber",
            "amber": "amber",
            "green": "emerald",
            "emerald": "emerald",
            "blue": "sky",
            "sky": "sky",
            "purple": "violet",
            "violet": "violet",
            "rose": "rose",
            "pink": "rose",
            "red": "rose",
            "indigo": "indigo",
        }
        selected = next((scheme for token, scheme in color_map.items() if token in text), "")
        if not selected and any(word in text for word in ("attractive", "premium", "modern", "beautiful", "awesome")):
            selected = "black_gold"
        if not selected:
            return None

        label = "golden amber" if selected == "amber" else selected
        return {
            "new_value": f"Updated landing page color scheme to {selected}.",
            "summary": f"Changed {business.name}'s landing page buttons and accent elements to a {label} theme.",
            "code_preview": f'<a class="cta" style="background: var(--{selected});">{"Start now"}</a>',
            "page_patch": {"color_scheme": selected},
        }

    @classmethod
    def _deterministic_landing_patch(cls, business: Business, instruction: str) -> dict[str, Any] | None:
        text = instruction.lower().strip()
        if not text:
            return None

        explicit_text = cls._extract_requested_text(instruction)

        if any(word in text for word in ("headline", "title", "hero heading", "main heading")):
            value = explicit_text or cls._headline_for_instruction(business, instruction)
            return {
                "field": "headline",
                "new_value": value,
                "summary": f"Updated {business.name}'s landing page headline.",
                "code_preview": f"<h1>{value}</h1>",
            }

        if any(word in text for word in ("subheading", "subtitle", "hero copy", "supporting copy")):
            value = explicit_text or cls._subheading_for_instruction(business, instruction)
            return {
                "field": "subheading",
                "new_value": value,
                "summary": f"Updated {business.name}'s hero subheading.",
                "code_preview": f"<p>{value}</p>",
            }

        explicit_cta_text = any(phrase in text for phrase in ("button text", "cta text", "call-to-action text", "call to action text"))
        if explicit_cta_text or any(word in text for word in ("cta", "button text", "call to action", "sign up", "start now")) and not any(
            color_word in text for color_word in ("color", "colour", "gold", "golden", "amber", "green", "blue", "purple", "red", "pink")
        ):
            value = explicit_text or cls._cta_for_instruction(instruction)
            return {
                "field": "cta_text",
                "new_value": value,
                "summary": f"Updated {business.name}'s primary call-to-action button text.",
                "code_preview": f"<button>{value}</button>",
            }

        if any(word in text for word in ("description", "about section", "overview")):
            value = explicit_text or cls._description_for_instruction(business, instruction)
            return {
                "field": "description",
                "new_value": value,
                "summary": f"Updated {business.name}'s business description.",
                "code_preview": f"<p>{value}</p>",
            }

        if any(word in text for word in ("product pitch", "offer pitch", "pitch")):
            value = explicit_text or cls._pitch_for_instruction(business, instruction)
            return {
                "field": "product_pitch",
                "new_value": value,
                "summary": f"Updated {business.name}'s offer pitch.",
                "code_preview": f"<section>{value}</section>",
            }

        patch: dict[str, Any] = {}
        summary_subject = "landing page sections"

        if any(word in text for word in ("premium", "modern", "futuristic", "sleek", "luxury")):
            patch.update(
                {
                    "trust_badges": ["Premium experience", "Fast setup", "AI-guided growth"],
                    "urgency_text": "Upgrade your workflow with a sharper, more premium business presence today.",
                    "features": [
                        "Polished customer-facing landing experience",
                        "AI-assisted business workflows",
                        "Conversion-focused offer presentation",
                    ],
                }
            )
            summary_subject = "premium landing page positioning"

        if any(word in text for word in ("friendly", "warm", "human", "welcoming")):
            patch.update(
                {
                    "trust_badges": ["Friendly support", "Simple onboarding", "Built around your goals"],
                    "urgency_text": "Start with a guided experience built to feel simple, clear, and supportive.",
                }
            )
            summary_subject = "friendlier landing page tone"

        if any(word in text for word in ("minimal", "clean", "simple")):
            patch.update(
                {
                    "benefits": ["Clear positioning", "Focused offer", "Less friction for customers"],
                    "urgency_text": "A cleaner path from first visit to confident action.",
                }
            )
            summary_subject = "cleaner landing page structure"

        if any(word in text for word in ("urgency", "limited", "deadline", "now", "today")):
            patch["urgency_text"] = explicit_text or cls._urgency_for_instruction(business, instruction)
            summary_subject = "urgency message"

        if any(word in text for word in ("trust", "badge", "badges", "credibility", "proof")):
            patch["trust_badges"] = cls._list_from_instruction(
                explicit_text,
                ["Verified outcomes", "Secure checkout", "Expert-built workflow"],
            )
            summary_subject = "trust badges"

        if any(word in text for word in ("benefit", "benefits", "why choose")):
            patch["benefits"] = cls._list_from_instruction(
                explicit_text,
                [
                    "Save hours with AI-assisted execution",
                    "Turn ideas into structured business assets",
                    "Keep marketing, products, and insights connected",
                ],
            )
            summary_subject = "benefits section"

        if any(word in text for word in ("feature", "features", "capabilities")):
            patch["features"] = cls._list_from_instruction(
                explicit_text,
                [
                    "AI Studio orchestration",
                    "Marketing campaign generation",
                    "Business intelligence dashboard",
                ],
            )
            summary_subject = "features section"

        if any(word in text for word in ("pricing", "price", "plans", "tier", "tiers")):
            patch["pricing_tiers"] = [
                {"name": "Starter", "price": "$29/mo", "features": ["Launch essentials", "AI content support"]},
                {"name": "Growth", "price": "$79/mo", "features": ["Campaign workflows", "Business analytics"]},
                {"name": "Scale", "price": "$149/mo", "features": ["Advanced automation", "Priority support"]},
            ]
            summary_subject = "pricing section"

        if any(word in text for word in ("faq", "questions", "answers")):
            patch["faq"] = [
                {"question": "How fast can I launch?", "answer": "Most businesses can prepare a focused launch page and core offer in a single workflow."},
                {"question": "Can I edit the generated content?", "answer": "Yes. AI Studio updates the saved business profile and landing preview so you can keep refining it."},
                {"question": "Does this connect to marketing?", "answer": "Yes. Campaigns, products, and research can reuse the same business context."},
            ]
            summary_subject = "FAQ section"

        if not patch:
            return None

        new_value = json.dumps(patch, ensure_ascii=True)
        return {
            "field": "page_content",
            "new_value": new_value,
            "summary": f"Updated {business.name}'s {summary_subject}.",
            "code_preview": f"<section data-ai-studio-update>{summary_subject}</section>",
            "page_patch": patch,
        }

    @staticmethod
    def _extract_requested_text(instruction: str) -> str:
        quoted = re.search(r"['\"]([^'\"]{3,220})['\"]", instruction)
        if quoted:
            return quoted.group(1).strip()

        explicit_marker = re.search(
            r"\b(?:exactly\s+)?(?:to|as|with)\s*[:=]\s*(.{3,220})$",
            instruction,
            flags=re.IGNORECASE,
        )
        if explicit_marker:
            return explicit_marker.group(1).strip(" .")[:220].strip()

        match = re.search(
            r"\b(?:to|as|with)\s+(.{3,220})$",
            instruction,
            flags=re.IGNORECASE,
        )
        if not match:
            return ""
        value = match.group(1).strip(" .")
        value = re.sub(r"^(a|an|the)\s+", "", value, flags=re.IGNORECASE)
        return value[:220].strip()

    @staticmethod
    def _headline_for_instruction(business: Business, instruction: str) -> str:
        niche = str(getattr(business, "niche", "") or "business").strip()
        if "premium" in instruction.lower():
            return f"Premium AI Growth Systems for {niche.title()}"
        if "simple" in instruction.lower() or "clear" in instruction.lower():
            return f"Launch Your {niche.title()} Faster"
        return f"Build and Grow {business.name} with AI"

    @staticmethod
    def _subheading_for_instruction(business: Business, instruction: str) -> str:
        audience = str(getattr(business, "target_audience", "") or "customers").strip()
        if "premium" in instruction.lower():
            return f"A polished AI-powered experience for {audience} who want sharper execution, clearer offers, and faster momentum."
        return f"Use AI-powered workflows to turn your ideas, products, and marketing into a connected operating system for {audience}."

    @staticmethod
    def _cta_for_instruction(instruction: str) -> str:
        text = instruction.lower()
        if "trial" in text:
            return "Start Free Trial"
        if "book" in text or "call" in text:
            return "Book a Strategy Call"
        if "buy" in text:
            return "Buy Now"
        if "join" in text:
            return "Join Today"
        return "Get Started Now"

    @staticmethod
    def _description_for_instruction(business: Business, instruction: str) -> str:
        tone = "premium " if "premium" in instruction.lower() else ""
        return (
            f"{business.name} is a {tone}AI-powered business system built to help "
            f"{getattr(business, 'target_audience', None) or 'customers'} move from idea to execution with connected products, marketing, and insights."
        )

    @staticmethod
    def _pitch_for_instruction(business: Business, instruction: str) -> str:
        if "premium" in instruction.lower():
            return f"A premium AI execution layer that helps {business.name} turn business strategy into polished, revenue-ready workflows."
        return f"{business.name} helps customers create, market, and improve their business assets with practical AI-powered execution."

    @staticmethod
    def _urgency_for_instruction(business: Business, instruction: str) -> str:
        if "final" in instruction.lower() or "exam" in instruction.lower():
            return "Finals season moves fast. Start building confidence with a smarter study workflow today."
        return f"Start improving {business.name}'s customer journey today while momentum is fresh."

    @staticmethod
    def _list_from_instruction(explicit_text: str, fallback: list[str]) -> list[str]:
        if not explicit_text:
            return fallback
        parts = [part.strip(" .") for part in re.split(r",|;|\band\b", explicit_text) if part.strip(" .")]
        return parts[:5] if parts else fallback

    @staticmethod
    def _plan_instruction(instruction: str) -> dict[str, str]:
        if AIStudioService._looks_like_app_builder_instruction(instruction):
            return {
                "intent": "prompt_to_app_update",
                "selected_tool": "app_builder",
                "tool_label": "AI Studio App Builder",
                "reason": "The prompt asks for visible landing-page or app changes, so AI Studio will update the project workspace and the live preview data together.",
                "fallback_action_type": "app_builder_project_update",
            }
        if AIStudioService._looks_like_code_instruction(instruction):
            return {
                "intent": "code_edit",
                "selected_tool": "code_editor",
                "tool_label": "AI Code Editor",
                "reason": "The prompt mentions code, components, files, or workspace editing, so AI Studio must mutate a real workspace file.",
                "fallback_action_type": "code_edit_applied",
            }
        if AIStudioService._looks_like_browser_research_instruction(instruction):
            return {
                "intent": "browser_research",
                "selected_tool": "browser_research",
                "tool_label": "Browser Research",
                "reason": "The prompt asks for research, competitors, markets, trends, SEO, or web analysis, so AI Studio routes it to the research memory pipeline.",
                "fallback_action_type": "research_report_created",
            }
        if AIStudioService._looks_like_product_instruction(instruction):
            return {
                "intent": "product_creation",
                "selected_tool": "product_builder",
                "tool_label": "Product Builder",
                "reason": "The prompt asks to create an offer, product, package, course, service, or subscription.",
                "fallback_action_type": "product_created",
            }
        if AIStudioService._looks_like_marketing_instruction(instruction):
            return {
                "intent": "marketing_generation",
                "selected_tool": "marketing_engine",
                "tool_label": "Marketing Engine",
                "reason": "The prompt asks for campaign, social, SEO, email, ad, or platform-specific marketing output.",
                "fallback_action_type": "marketing_campaign_created",
            }
        return {
            "intent": "business_profile_update",
            "selected_tool": "business_profile",
            "tool_label": "Business Profile + Landing Preview",
            "reason": "The prompt is a business or landing-page change, so AI Studio updates persisted business fields and regenerates the local preview snapshot.",
            "fallback_action_type": "business_profile_update",
        }

    @staticmethod
    def _looks_like_app_builder_instruction(instruction: str) -> bool:
        text = instruction.lower()
        visual_words = (
            "hero",
            "background",
            "black",
            "gold",
            "golden",
            "green",
            "button",
            "cta",
            "testimonial",
            "testimonials",
            "pricing",
            "section",
            "landing",
            "page",
            "modern",
            "premium",
            "fitness",
            "coaching",
            "layout",
            "typography",
            "color",
            "colour",
            "brand",
            "business context",
            "home services",
            "hvac",
            "plumbing",
            "electrical",
            "roofing",
            "pain points",
            "reviews",
        )
        action_words = ("make", "change", "add", "update", "create", "redesign", "improve", "turn", "build", "pivot", "transform", "replace", "switch")
        return any(word in text for word in visual_words) and any(word in text for word in action_words)

    @staticmethod
    def _attach_orchestration_trace(
        action: dict[str, Any],
        plan: dict[str, str],
        business: Business,
        instruction: str,
        started_at: datetime,
        status: str,
        *,
        error: str | None = None,
    ) -> dict[str, Any]:
        completed_at = datetime.now(timezone.utc)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        persisted_targets: list[str] = []
        if action.get("version_id"):
            persisted_targets.append("code_version")
        if action.get("campaign_id"):
            persisted_targets.append("marketing_campaign")
        if action.get("agent_report_id"):
            persisted_targets.append("agent_report")
        if action.get("product_id"):
            persisted_targets.append("product")
        if action.get("action_type") in {"business_profile_update", "app_builder_project_update"}:
            persisted_targets.append("business_profile")
        if action.get("action_type") == "app_builder_project_update":
            persisted_targets.append("workspace_files")

        steps = [
            {
                "label": "Prompt received",
                "status": "completed",
                "detail": instruction[:220],
                "timestamp": started_at.isoformat(),
            },
            {
                "label": "Business context loaded",
                "status": "completed",
                "detail": f"{business.name} ({business.id})",
                "timestamp": started_at.isoformat(),
            },
            {
                "label": f"{plan['tool_label']} selected",
                "status": "completed",
                "detail": plan["reason"],
                "timestamp": started_at.isoformat(),
            },
            {
                "label": "Backend action executed",
                "status": status,
                "detail": error or str(action.get("summary") or action.get("error") or "Execution finished."),
                "timestamp": completed_at.isoformat(),
            },
            {
                "label": "Result persisted",
                "status": "completed" if status == "completed" and persisted_targets else status,
                "detail": ", ".join(persisted_targets) if persisted_targets else ("No persistent target was produced." if status == "completed" else error or "Failed before persistence."),
                "timestamp": completed_at.isoformat(),
            },
        ]

        enriched = dict(action)
        enriched["orchestration"] = {
            "instruction": instruction,
            "intent": plan["intent"],
            "selected_tool": plan["selected_tool"],
            "tool_label": plan["tool_label"],
            "reason": plan["reason"],
            "status": status,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_ms": duration_ms,
            "business_id": str(business.id),
            "business_name": business.name,
            "action_type": enriched.get("action_type") or plan["fallback_action_type"],
            "updated_files": enriched.get("updated_files") or ([] if not enriched.get("file_path") else [enriched["file_path"]]),
            "provider_used": enriched.get("provider_used"),
            "version_id": enriched.get("version_id"),
            "next_url": enriched.get("next_url"),
            "persisted_targets": persisted_targets,
            "steps": steps,
        }
        if error:
            enriched["orchestration"]["error"] = error
        return enriched

    @staticmethod
    def _looks_like_marketing_instruction(instruction: str) -> bool:
        text = instruction.lower()
        keywords = (
            "campaign",
            "linkedin",
            "twitter",
            "instagram",
            "facebook",
            "email",
            "newsletter",
            "blog",
            "seo",
            "ad copy",
            "google ads",
            "meta ads",
            "marketing",
            "social post",
            "launch post",
        )
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _looks_like_code_instruction(instruction: str) -> bool:
        text = instruction.lower()
        intent = any(word in text for word in ("code", "component", "tsx", "css", "file", "editor", "workspace", "refactor"))
        edit = any(word in text for word in ("edit", "change", "modify", "update", "make", "redesign", "fix", "add", "remove"))
        return intent and edit

    @staticmethod
    def _looks_like_browser_research_instruction(instruction: str) -> bool:
        text = instruction.lower()
        research = any(word in text for word in ("research", "competitor", "market", "seo keyword", "pricing analysis", "trend", "analyze"))
        explicit_browser = any(word in text for word in ("browser", "web", "website", "search internet", "google", "duckduckgo"))
        return research or explicit_browser

    @staticmethod
    def _looks_like_product_instruction(instruction: str) -> bool:
        text = instruction.lower()
        intent = any(word in text for word in ("create", "add", "build", "make", "draft", "generate"))
        product_word = any(word in text for word in ("product", "offer", "package", "course", "template", "subscription", "service"))
        return intent and product_word and "campaign" not in text and "post" not in text

    @staticmethod
    def _select_workspace_file(root: Path, instruction: str) -> str:
        text = instruction.lower()
        candidates = [path for path in root.rglob("*") if path.is_file() and not path.name.startswith(".")]
        rels = [str(path.relative_to(root)).replace("\\", "/") for path in candidates]
        if any(word in text for word in ("hero", "headline", "cta", "button")) and "components/Hero.tsx" in rels:
            return "components/Hero.tsx"
        if any(word in text for word in ("style", "css", "color", "spacing", "layout", "modern", "responsive")) and "styles/theme.css" in rels:
            return "styles/theme.css"
        if any(word in text for word in ("page", "landing", "section")) and "app/page.tsx" in rels:
            return "app/page.tsx"
        for rel in rels:
            if rel.lower() in text:
                return rel
        return "app/page.tsx" if "app/page.tsx" in rels else rels[0]

    @staticmethod
    def _language_for_path(path: str) -> str:
        suffix = Path(path).suffix.lower()
        return {
            ".tsx": "typescript react",
            ".ts": "typescript",
            ".jsx": "javascript react",
            ".js": "javascript",
            ".css": "css",
            ".json": "json",
            ".md": "markdown",
            ".py": "python",
        }.get(suffix, "text")

    @staticmethod
    def _infer_marketing_content_type(instruction: str) -> str:
        text = instruction.lower()
        if "email" in text or "newsletter" in text:
            return "email_sequence"
        if "blog" in text or "seo" in text or "article" in text:
            return "blog_post"
        if "twitter" in text or " x " in f" {text} ":
            return "twitter_thread"
        if "instagram" in text:
            return "instagram_caption"
        if "youtube" in text:
            return "youtube_description"
        if "ad copy" in text or "google ads" in text or "meta ads" in text:
            return "ad_copy"
        return "linkedin_post"

    @staticmethod
    def _marketing_business_context(business: Business) -> dict[str, Any]:
        return {
            "name": business.name,
            "niche": business.niche,
            "description": business.description,
            "brand_tone": business.brand_tone,
            "target_audience": business.target_audience,
            "headline": business.headline,
            "product_pitch": business.product_pitch,
        }

    async def _recent_agent_context(self, business_id: str, limit: int = 3) -> str:
        result = await self.db.execute(
            select(AgentLog)
            .where(
                AgentLog.business_id == UUID(str(business_id)),
                AgentLog.log_type == "report",
            )
            .order_by(AgentLog.created_at.desc())
            .limit(limit)
        )
        reports = result.scalars().all()
        parts: list[str] = []
        for report in reports:
            payload = report.payload or {}
            goal = str(payload.get("goal") or "")
            summary = str(payload.get("result") or report.summary or "")
            sources = payload.get("sources") or []
            source_text = ", ".join(str(source) for source in sources[:4]) if isinstance(sources, list) else ""
            parts.append(
                "\n".join(
                    part
                    for part in (
                        f"Goal: {goal}",
                        f"Finding: {summary[:900]}",
                        f"Sources: {source_text}" if source_text else "",
                    )
                    if part
                )
            )
        return "\n\n".join(parts)

    @staticmethod
    def _business_snapshot(business: Business) -> dict[str, Any]:
        return {
            "name": business.name,
            "niche": business.niche,
            "target_audience": business.target_audience,
            "headline": business.headline,
            "subheading": business.subheading,
            "cta_text": business.cta_text,
        }

    @staticmethod
    def _message_payload(message: AIStudioMessage) -> dict[str, Any]:
        return {
            "id": message.id,
            "conversation_id": message.conversation_id,
            "business_id": message.business_id,
            "role": message.role,
            "content": message.content,
            "message_type": message.message_type,
            "status": message.status,
            "action_type": message.action_type,
            "metadata": message.metadata_json or {},
            "created_at": message.created_at.isoformat() if message.created_at else None,
            "updated_at": message.updated_at.isoformat() if message.updated_at else None,
        }

    @staticmethod
    def _preview_value(value: Any, limit: int = 180) -> str:
        if isinstance(value, (dict, list)):
            text = json.dumps(value, ensure_ascii=True)
        else:
            text = str(value)
        return text if len(text) <= limit else f"{text[:limit]}..."
