from uuid import UUID

from pydantic import BaseModel, Field


class AnalyticsEventCreate(BaseModel):
    business_id: UUID
    product_id: UUID | None = None
    event_type: str = Field(min_length=2, max_length=80)
    source: str | None = Field(default=None, max_length=120)
    value_cents: int = Field(default=0, ge=0)
    metadata_json: dict = Field(default_factory=dict)


class ProductPerformanceRead(BaseModel):
    product_id: UUID | None
    events: int
    revenue_cents: int


class AnalyticsSummaryRead(BaseModel):
    business_id: UUID
    visitors: int
    clicks: int
    conversions: int
    revenue_cents: int
    conversion_rate: float
    product_performance: list[ProductPerformanceRead]


class UsagePointRead(BaseModel):
    date: str
    ai_requests: int
    campaigns_generated: int


class AnalyticsDashboardRead(BaseModel):
    business_id: UUID
    ai_requests: int
    campaigns_generated: int
    success_rate: float
    usage_over_time: list[UsagePointRead]
