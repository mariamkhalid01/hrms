"""Performance and evidence contracts; all durations are UTC elapsed seconds."""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

from app.schemas.discovery import DiscoveryRequest, Distribution


class Thresholds(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    minimum_samples: int = Field(default=5, ge=3, le=1000)
    minimum_affected_cases: int = Field(default=2, ge=1, le=1000)
    iqr_multiplier: float = Field(default=1.5, ge=0.5, le=10)
    minimum_relative_increase: float = Field(default=2, ge=1, le=10)
    processing_seconds: float | None = Field(default=None, ge=0)
    waiting_seconds: float | None = Field(default=None, ge=0)
    case_duration_seconds: float | None = Field(default=None, ge=0)
    handovers_per_case: float | None = Field(default=None, ge=0)
    repeated_case_percentage: float = Field(default=20, ge=0, le=100)
    variant_repetition_percentage: float = Field(default=20, ge=0, le=100)
    processing_seconds_by_activity: dict[str, float] = Field(default_factory=dict, max_length=200)
    waiting_seconds_by_transition: dict[str, float] = Field(default_factory=dict, max_length=500)

    @field_validator("processing_seconds_by_activity", "waiting_seconds_by_transition")
    @classmethod
    def finite_nonnegative(cls, values):
        if any(not key or not math.isfinite(value) or value < 0 for key, value in values.items()):
            raise ValueError("Thresholds require nonempty keys and finite nonnegative values.")
        return values


class AnalyticsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    discovery: DiscoveryRequest | None = None
    thresholds: Thresholds = Field(default_factory=Thresholds)
    process_overrides: dict[str, Thresholds] = Field(default_factory=dict, max_length=200)

    @field_serializer("process_overrides")
    def serialize_overrides(self, values):
        # Preserve explicit overrides and cache identity through JSON round trips.
        return {name: value.model_dump(exclude_unset=True) for name, value in values.items()}


class WaitingMetrics(BaseModel):
    measured_wait_seconds: Distribution
    approximate_wait_seconds: Distribution
    signed_interval_gap_seconds: Distribution
    interval_pair_count: int
    approximation_count: int
    overlap_count: int


class ActivityPerformance(BaseModel):
    id: str
    label: str
    frequency: int
    case_frequency: int
    repeated_case_count: int
    repeated_case_percentage: float
    extra_occurrences: int
    processing_seconds: Distribution
    processing_coverage_percentage: float
    incoming_wait: WaitingMetrics


class TransitionPerformance(BaseModel):
    id: str
    source: str
    target: str
    source_label: str
    target_label: str
    frequency: int
    case_frequency: int
    waiting: WaitingMetrics
    resource_comparable_pairs: int | None
    resource_handovers: int | None
    department_comparable_pairs: int | None
    department_handovers: int | None


class CompletionMetrics(BaseModel):
    status_counts: dict[str, int]
    known_status_cases: int
    status_coverage_percentage: float
    completion_rate_percentage: float | None
    known_status_completion_rate_percentage: float | None


class AssignmentMetric(BaseModel):
    id: str
    label: str
    names: list[str]
    roles: list[str]
    event_count: int
    case_count: int
    activity_count: int
    event_share_percentage: float
    total_processing_seconds: float | None
    processing_seconds: Distribution
    processing_coverage_percentage: float
    repeated_case_assignments: int
    same_activity_repeat_assignments: int


class HandoverMetric(BaseModel):
    source: str
    target: str
    count: int
    affected_case_count: int


class AssignmentAnalysis(BaseModel):
    field: str
    known_event_count: int
    missing_event_count: int
    coverage_percentage: float
    comparable_adjacent_pairs: int
    changed_assignment_pairs: int
    same_assignment_pairs: int
    handover_rate_percentage: float | None
    handovers_per_fully_observed_case: Distribution
    fully_observed_case_count: int
    members: list[AssignmentMetric]
    handovers: list[HandoverMetric]


class VariantPerformance(BaseModel):
    id: str
    activity_sequence: list[str]
    case_count: int
    percentage: float
    case_duration_seconds: Distribution
    repeated_activity_count: int
    extra_event_percentage: float
    case_status_counts: dict[str, int]


class ProcessPerformance(BaseModel):
    id: str
    name: str
    total_cases: int
    total_events: int
    case_duration_seconds: Distribution
    completed_case_duration_seconds: Distribution
    full_interval_case_duration_seconds: Distribution
    completion: CompletionMetrics
    processing_seconds: Distribution
    waiting: WaitingMetrics
    variant_count: int
    repeated_case_count: int
    repeated_case_percentage: float
    activities: list[ActivityPerformance]
    transitions: list[TransitionPerformance]
    resources: AssignmentAnalysis | None
    departments: AssignmentAnalysis | None
    effective_thresholds: Thresholds
    finding_count: int = 0
    findings_by_category: dict[str, int] = Field(default_factory=dict)
    warnings: list[str]


FindingCategory = Literal[
    "long_processing",
    "long_waiting",
    "repeated_activity",
    "rework_path",
    "delayed_cases",
    "slow_variant",
    "frequent_handovers",
    "workload_imbalance",
]


class FindingEntity(BaseModel):
    kind: Literal["activity", "transition", "process", "variant", "resource", "department"]
    id: str
    label: str
    source: str | None = None
    target: str | None = None


class Baseline(BaseModel):
    method: Literal["business_threshold", "robust_upper_fence", "configured_screening_rule"]
    cohort: str
    sample_count: int
    comparison_value: float | None
    threshold: float
    q1: float | None = None
    q3: float | None = None


class EvidenceSample(BaseModel):
    case_id: str
    source_rows: list[int]
    value: float
    unit: Literal["seconds", "percentage", "count"]


class FindingEvidence(BaseModel):
    explanation: str
    eligible_observation_count: int
    affected_observation_count: int
    eligible_case_count: int
    examples: list[EvidenceSample]
    caveats: list[str]


class FindingImpact(BaseModel):
    description: str
    observed_excess_seconds: float | None = None
    savings_estimated: Literal[False] = False


class Finding(BaseModel):
    id: str
    process_id: str
    process_type: str
    entity: FindingEntity
    category: FindingCategory
    measured_metric: str
    unit: Literal["seconds", "percentage", "count"]
    measurement: Literal["measured", "approximation", "observed_span"]
    observed_value: float
    baseline: Baseline
    affected_case_count: int
    severity: Literal["low", "medium", "high"]
    evidence: FindingEvidence
    potential_impact: FindingImpact
    cause_status: Literal["not_established"] = "not_established"


class AnalyticsResult(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: str
    analysis_id: str
    discovery_analysis_id: str
    validation_id: str
    normalized_sha256: str
    created_at: str
    duration_ms: float
    configuration: AnalyticsRequest
    total_cases: int
    total_events: int
    case_duration_seconds: Distribution | None = None
    process_count: int
    finding_count: int
    processes: list[ProcessPerformance]
    semantics: dict[str, str]


class FindingsPage(BaseModel):
    analysis_id: str
    total: int
    offset: int
    limit: int
    items: list[Finding]


class PerformanceVariantsPage(BaseModel):
    analysis_id: str
    process_id: str
    total: int
    offset: int
    limit: int
    items: list[VariantPerformance]
