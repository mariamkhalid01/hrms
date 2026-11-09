import { createApiClient } from './client';
import { apiConfig } from './config';

export const canonicalFields = [
  'case_id', 'activity', 'timestamp', 'process_type', 'event_id', 'resource_id',
  'resource_name', 'resource_role', 'department', 'activity_start', 'activity_end',
  'cost', 'outcome', 'status', 'event_order',
] as const;
export type CanonicalField = typeof canonicalFields[number];
export type ColumnMapping = Record<CanonicalField, string | null>;
export interface DatasetLimits { max_upload_bytes: number; max_rows: number; max_columns: number; preview_rows: number }
export interface DatasetColumn { name: string; inferred_type: string; missing_count: number; missing_percent: number; unique_count: number }
export interface DatasetPreview {
  id: string; filename: string; size_bytes: number; row_count: number; column_count: number;
  columns: DatasetColumn[]; preview: { row_number: number; values: Record<string, string | null> }[];
  suggested_mapping: ColumnMapping; delimiter: string; encoding: string;
  status: 'uploaded' | 'validated' | 'ready'; created_at: string;
}
export interface MappingRequest { mapping: ColumnMapping; timezone: string; timestamp_format: string | null; day_first: boolean }
export interface ValidationIssue {
  code: string; severity: 'error' | 'warning' | 'info'; message: string; resolution: string;
  field: string | null; count: number; row_numbers: number[]; sample_values: string[];
}
export interface ValidationReport {
  validation_id: string; dataset_id: string; valid: boolean;
  summary: { event_count: number; case_count: number; process_count: number; error_count: number; warning_count: number; info_count: number };
  issues: ValidationIssue[]; normalized_preview: Record<string, unknown>[];
  timezone: string; source_timezone: string;
}
export interface ReadyDataset {
  dataset_id: string; status: 'ready'; filename: string; event_count: number; case_count: number; process_count: number;
  processes: { name: string; event_count: number; case_count: number }[]; processed_at: string;
  normalization: { timezone: string; source_timezone: string; sorted_by: string[]; preserved_source: boolean };
}

const client = createApiClient({ ...apiConfig, timeoutMs: 120_000 });
export const getDatasetLimits = (signal?: AbortSignal) => client.request<DatasetLimits>('/datasets/config', { signal });
export function uploadDataset(file: File, signal?: AbortSignal) {
  const body = new FormData(); body.append('file', file);
  return client.request<DatasetPreview>('/datasets/upload', { method: 'POST', body, signal });
}
export function validateDataset(id: string, request: MappingRequest, signal?: AbortSignal) {
  return client.request<ValidationReport>(`/datasets/${encodeURIComponent(id)}/validate`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request), signal,
  });
}
export function processDataset(id: string, validationId: string, acknowledgeWarnings: boolean, signal?: AbortSignal) {
  return client.request<ReadyDataset>(`/datasets/${encodeURIComponent(id)}/process`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ validation_id: validationId, acknowledge_warnings: acknowledgeWarnings }), signal,
  });
}
