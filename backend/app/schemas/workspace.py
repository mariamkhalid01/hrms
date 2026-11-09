"""Real execution stages, evidence-linked recommendations, and paginated case inspection."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.analytics import AnalyticsRequest, FindingEntity


class AnalysisJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validation_id: str | None = None
    acknowledge_warnings: bool = False
    analytics: AnalyticsRequest | None = None


class JobStage(BaseModel):
    key: str
    label: str
    status: Literal["pending", "running", "completed", "failed", "skipped"] = "pending"
    detail: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class JobError(BaseModel):
    code: str
    message: str


class AnalysisJob(BaseModel):
    id: str
    dataset_id: str
    status: Literal["queued", "running", "completed", "failed"]
    current_stage: str | None = None
    stages: list[JobStage]
    created_at: str
    updated_at: str
    error: JobError | None = None
    discovery_analysis_id: str | None = None
    analytics_analysis_id: str | None = None


class Recommendation(BaseModel):
    id: str
    process_id: str
    process_type: str
    title: str
    category: str
    priority: Literal["low", "medium", "high"]
    entity: FindingEntity
    finding_ids: list[str]
    evidence_summary: str
    actions: list[str]
    measurement_plan: list[str]
    caveats: list[str]
    affected_case_count: int
    expected_improvement: None = None


class RecommendationPage(BaseModel):
    analysis_id: str
    total: int
    offset: int
    limit: int
    items: list[Recommendation]


class CaseSummary(BaseModel):
    id: str
    case_id: str
    process_id: str
    process_type: str
    variant_id: str
    event_count: int
    observed_duration_seconds: float
    status: str


class CasePage(BaseModel):
    analysis_id: str
    total: int
    offset: int
    limit: int
    items: list[CaseSummary]


class CaseDetail(BaseModel):
    analysis_id: str
    case: CaseSummary
    total_events: int
    offset: int
    limit: int
    events: list[dict[str, Any]]
