"""Versioned, JSON-only mining contracts. No PM4Py objects cross this boundary."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CaseState = Literal["completed", "incomplete", "cancelled", "unknown"]


class DiscoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    algorithm: Literal["auto", "dfg", "inductive"] = "auto"
    noise_threshold: float = Field(default=0, ge=0, lt=1)
    case_status_attribute: str | None = Field(default=None, min_length=1, max_length=200)
    # Explicit interpretation of a CASE-level source attribute, not event status.
    case_status_values: dict[str, CaseState] = Field(default_factory=dict, max_length=100)

    @model_validator(mode="after")
    def status_configuration(self):
        if bool(self.case_status_attribute) != bool(self.case_status_values):
            raise ValueError("Provide both a case-status attribute and its value mapping.")
        keys = [value.strip().casefold() for value in self.case_status_values]
        if not all(keys) or len(keys) != len(set(keys)):
            raise ValueError("Case-status values must be nonempty and unique ignoring case.")
        if self.algorithm == "dfg" and self.noise_threshold:
            raise ValueError("Noise filtering applies only to Inductive Miner.")
        return self


class Distribution(BaseModel):
    count: int
    mean: float | None
    median: float | None
    minimum: float | None
    maximum: float | None


class Activity(BaseModel):
    id: str
    label: str
    frequency: int
    case_frequency: int
    repeated_case_count: int
    start_frequency: int
    end_frequency: int
    service_time_seconds: Distribution


class Transition(BaseModel):
    id: str
    source: str
    target: str
    frequency: int
    case_frequency: int
    is_self_loop: bool
    in_graph_cycle: bool
    elapsed_time_seconds: Distribution
    inter_activity_gap_seconds: Distribution
    overlap_count: int


class Boundary(BaseModel):
    activity_id: str
    frequency: int


class PathChoice(BaseModel):
    target: str
    frequency: int
    outgoing_percentage: float


class AlternativePaths(BaseModel):
    source: str
    choices: list[PathChoice]


class LoopGroup(BaseModel):
    activity_ids: list[str]
    transition_ids: list[str]


class FlowNode(BaseModel):
    id: str
    type: Literal["default"] = "default"
    position: dict[str, float]
    data: Activity


class FlowEdge(BaseModel):
    id: str
    source: str
    target: str
    type: Literal["smoothstep"] = "smoothstep"
    label: str
    data: Transition


class FlowModel(BaseModel):
    nodes: list[FlowNode]
    edges: list[FlowEdge]


class ProcessTreeNode(BaseModel):
    id: str
    operator: str | None
    label: str | None
    silent: bool
    children: list["ProcessTreeNode"]


class PetriPlace(BaseModel):
    id: str
    initial_tokens: int
    final_tokens: int


class PetriTransition(BaseModel):
    id: str
    label: str | None
    activity_id: str | None
    silent: bool


class PetriArc(BaseModel):
    id: str
    source: str
    target: str
    weight: int


class PetriModel(BaseModel):
    places: list[PetriPlace]
    transitions: list[PetriTransition]
    arcs: list[PetriArc]


class InductiveModel(BaseModel):
    status: Literal["discovered", "skipped", "failed"]
    reason: str | None
    input_case_count: int
    excluded_case_count: int
    noise_threshold: float
    process_tree: ProcessTreeNode | None = None
    petri_net: PetriModel | None = None


class Variant(BaseModel):
    id: str
    activity_sequence: list[str]
    activity_ids: list[str]
    case_count: int
    percentage: float
    average_case_duration_seconds: float
    median_case_duration_seconds: float
    observed_duration_seconds: Distribution
    completed_duration_seconds: Distribution
    case_status_counts: dict[str, int]


class ProcessMetadata(BaseModel):
    boundary_semantics: str
    duration_semantics: str
    ordering: list[str]
    duplicate_policy: str
    case_status_attribute: str | None
    case_status_counts: dict[str, int]
    conflicting_status_case_count: int
    unrecognized_status_case_count: int
    repeated_case_count: int
    warnings: list[str]


class ProcessModel(BaseModel):
    id: str
    name: str
    event_count: int
    case_count: int
    variant_count: int
    activities: list[Activity]
    transitions: list[Transition]
    start_activities: list[Boundary]
    end_activities: list[Boundary]
    alternative_paths: list[AlternativePaths]
    loops: list[LoopGroup]
    react_flow: FlowModel
    inductive: InductiveModel
    metadata: ProcessMetadata


class DiscoveryResult(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    dataset_id: str
    analysis_id: str
    validation_id: str
    normalized_sha256: str
    created_at: str
    duration_ms: float
    pm4py_version: str
    configuration: DiscoveryRequest
    process_count: int
    event_count: int
    case_count: int
    processes: list[ProcessModel]


class VariantPage(BaseModel):
    analysis_id: str
    process_id: str
    total: int
    offset: int
    limit: int
    items: list[Variant]
