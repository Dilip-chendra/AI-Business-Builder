import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.user import User
from app.schemas.business import BusinessCreate, BusinessGenerateRequest
from app.services.ai_service import AIService
from app.services.context_service import ContextService

logger = logging.getLogger(__name__)


class BusinessService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _resolve_context(self, user_id: UUID | None, workspace_id: UUID | None, project_id: UUID | None) -> tuple[UUID | None, UUID | None]:
        if user_id is None:
            return workspace_id, project_id
        user = await self.db.get(User, user_id)
        if not user:
            return workspace_id, project_id
        snapshot = await ContextService(self.db).ensure_initial_context(user)
        resolved_workspace = workspace_id or (UUID(snapshot.workspace_id) if snapshot.workspace_id else None)
        resolved_project = project_id or (UUID(snapshot.project_id) if snapshot.project_id else None)
        return resolved_workspace, resolved_project

    async def generate_and_store(
        self, payload: BusinessGenerateRequest, user_id: UUID | None = None
    ) -> Business:
        logger.info("Generating business  interests=%r  user_id=%s", payload.interests, user_id)
        generated = await AIService().generate_business(payload)
        workspace_id, project_id = await self._resolve_context(user_id, payload.workspace_id, payload.project_id)

        # Separate the core DB fields from the rich page content
        core_fields = {
            "name", "niche", "description", "target_audience",
            "monetization_model", "brand_tone", "headline", "subheading",
            "product_pitch", "cta_text", "seo_title", "seo_description",
        }
        rich_fields = {
            "pain_points", "benefits", "features", "social_proof",
            "faq", "pricing_tiers", "urgency_text", "trust_badges", "color_scheme",
            "lead_capture", "quote_request",
        }
        full_payload = generated.model_dump()
        core_data = {k: v for k, v in full_payload.items() if k in core_fields}
        page_content = {k: v for k, v in full_payload.items() if k in rich_fields}
        if user_id and workspace_id and payload.project_id is None:
            project = await ContextService(self.db).workspace_service.create_project(
                str(workspace_id),
                f"{core_data.get('name') or 'Business'} Project",
                "business",
            )
            project_id = project.id

        business = Business(
            **core_data,
            raw_ai_payload=full_payload,
            page_content=page_content,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        self.db.add(business)
        await self.db.commit()
        await self.db.refresh(business)
        if user_id:
            user = await self.db.get(User, user_id)
            if user:
                user.active_business_id = business.id
                if workspace_id:
                    user.active_workspace_id = workspace_id
                if project_id:
                    user.active_project_id = project_id
                self.db.add(user)
                await self.db.commit()
        logger.info("Business created  id=%s  name=%r  user_id=%s", business.id, business.name, user_id)
        return business

    async def create(
        self, payload: BusinessCreate, user_id: UUID | None = None
    ) -> Business:
        workspace_id, project_id = await self._resolve_context(user_id, payload.workspace_id, payload.project_id)
        payload_data = payload.model_dump(exclude={"workspace_id", "project_id"})
        if user_id and workspace_id and payload.project_id is None:
            project = await ContextService(self.db).workspace_service.create_project(
                str(workspace_id),
                f"{payload_data.get('name') or 'Business'} Project",
                "business",
            )
            project_id = project.id
        business = Business(
            **payload_data,
            raw_ai_payload=payload_data,
            user_id=user_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        self.db.add(business)
        await self.db.commit()
        await self.db.refresh(business)
        if user_id:
            user = await self.db.get(User, user_id)
            if user:
                user.active_business_id = business.id
                if workspace_id:
                    user.active_workspace_id = workspace_id
                if project_id:
                    user.active_project_id = project_id
                self.db.add(user)
                await self.db.commit()
        logger.info("Business manually created  id=%s  name=%r  user_id=%s", business.id, business.name, user_id)
        return business

    async def list(self, user_id: UUID | None = None, workspace_id: UUID | None = None, project_id: UUID | None = None) -> list[Business]:
        query = select(Business).order_by(Business.created_at.desc())
        if user_id is not None:
            query = query.where(Business.user_id == user_id)
        if workspace_id is not None:
            query = query.where(Business.workspace_id == workspace_id)
        if project_id is not None:
            query = query.where(Business.project_id == project_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get(self, business_id: UUID, user_id: UUID | None = None) -> Business | None:
        business = await self.db.get(Business, business_id)
        if business is None:
            return None
        if user_id is not None and str(business.user_id) != str(user_id):
            return None
        return business
