from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BusinessGenerateRequest(BaseModel):
    interests: str = Field(min_length=2, max_length=500)
    niche_preferences: str | None = Field(default=None, max_length=300)
    target_audience: str | None = Field(default=None, max_length=300)
    goals: str | None = Field(default=None, max_length=500)
    workspace_id: UUID | None = None
    project_id: UUID | None = None


class BusinessCreate(BaseModel):
    workspace_id: UUID | None = None
    project_id: UUID | None = None
    name: str = Field(min_length=2, max_length=120)
    niche: str = Field(min_length=2, max_length=140)
    description: str = Field(min_length=10)
    target_audience: str = Field(min_length=2, max_length=220)
    monetization_model: str = Field(min_length=2, max_length=160)
    brand_tone: str = "clear and trustworthy"
    headline: str
    subheading: str
    product_pitch: str
    cta_text: str = "Start now"
    seo_title: str
    seo_description: str


class BusinessRead(BusinessCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None = None
    workspace_id: UUID | None = None
    project_id: UUID | None = None
    raw_ai_payload: dict = {}
    page_content: dict = {}
    product_count: int = 0
    created_at: datetime
    updated_at: datetime
