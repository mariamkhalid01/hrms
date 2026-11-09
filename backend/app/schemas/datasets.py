"""JSON-only contracts for upload, mapping, validation, and preparation."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class UploadConfig(BaseModel):
    max_upload_bytes: int
    max_rows: int
    max_columns: int
    preview_rows: int


class ColumnSummary(BaseModel):
    name: str
    inferred_type: str
    missing_count: int
    missing_percent: float
    unique_count: int


class PreviewRow(BaseModel):
    row_number: int
    values: dict[str, str | None]


class DatasetPreview(BaseModel):
    id: str
    filename: str
    size_bytes: int
    row_count: int
    column_count: int
    columns: list[ColumnSummary]
    preview: list[PreviewRow]
    suggested_mapping: dict[str, str | None]
    delimiter: str
    encoding: str
    status: Literal["uploaded", "validated", "ready"]
    created_at: str


class MappingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mapping: dict[str, str | None]
    timezone: str = Field(default="UTC", min_length=1, max_length=100)
    timestamp_format: str | None = Field(default=None, max_length=200)
    day_first: bool = False


class ValidationSummary(BaseModel):
    event_count: int
    case_count: int
    process_count: int
    error_count: int
    warning_count: int
    info_count: int


class ValidationIssue(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    resolution: str
    field: str | None = None
    count: int
    row_numbers: list[int]
    sample_values: list[str]


class ValidationReport(BaseModel):
    validation_id: str
    dataset_id: str
    valid: bool
    summary: ValidationSummary
    issues: list[ValidationIssue]
    normalized_preview: list[dict[str, Any]]
    timezone: str
    source_timezone: str


class ProcessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    validation_id: str = Field(min_length=1, max_length=100)
    acknowledge_warnings: bool = False


class ProcessSummary(BaseModel):
    name: str
    event_count: int
    case_count: int


class NormalizationSummary(BaseModel):
    timezone: Literal["UTC"]
    source_timezone: str
    sorted_by: list[str]
    preserved_source: bool


class ReadyDataset(BaseModel):
    dataset_id: str
    status: Literal["ready"]
    filename: str
    event_count: int
    case_count: int
    process_count: int
    processes: list[ProcessSummary]
    processed_at: str
    normalization: NormalizationSummary
