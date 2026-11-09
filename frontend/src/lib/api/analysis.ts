import { ApiError, createApiClient } from './client';
import { apiConfig } from './config';
import type { ReadyDataset } from './datasets';

export interface Distribution { count: number; mean: number | null; median: number | null; minimum: number | null; maximum: number | null }
export interface Activity { id: string; label: string; frequency: number; case_frequency: number; repeated_case_count: number; start_frequency: number; end_frequency: number; service_time_seconds: Distribution }
export interface Transition { id: string; source: string; target: string; frequency: number; case_frequency: number; is_self_loop: boolean; in_graph_cycle: boolean; elapsed_time_seconds: Distribution; inter_activity_gap_seconds: Distribution; overlap_count: number }
export interface ProcessTreeNode { id: string; operator: string | null; label: string | null; silent: boolean; children: ProcessTreeNode[] }
export interface ProcessModel {
  id: string; name: string; event_count: number; case_count: number; variant_count: number;
  activities: Activity[]; transitions: Transition[];
  start_activities: { activity_id: string; frequency: number }[]; end_activities: { activity_id: string; frequency: number }[];
  alternative_paths: { source: string; choices: { target: string; frequency: number; outgoing_percentage: number }[] }[];
  loops: { activity_ids: string[]; transition_ids: string[] }[];
  react_flow: { nodes: { id: string; type: string; position: { x: number; y: number }; data: Activity }[]; edges: { id: string; source: string; target: string; label: string; data: Transition }[] };
  inductive: { status: 'discovered' | 'skipped' | 'failed'; reason: string | null; input_case_count: number; excluded_case_count: number; noise_threshold: number; process_tree: ProcessTreeNode | null };
  metadata: { boundary_semantics: string; duration_semantics: string; ordering: string[]; duplicate_policy: string; case_status_attribute: string | null; case_status_counts: Record<string, number>; repeated_case_count: number; warnings: string[] };
}
export interface DiscoveryResult { dataset_id: string; analysis_id: string; validation_id: string; created_at: string; pm4py_version: string; process_count: number; event_count: number; case_count: number; processes: ProcessModel[] }
export interface WaitingMetrics { measured_wait_seconds: Distribution; approximate_wait_seconds: Distribution; signed_interval_gap_seconds: Distribution; interval_pair_count: number; approximation_count: number; overlap_count: number }
export interface ActivityPerformance { id: string; label: string; frequency: number; case_frequency: number; repeated_case_count: number; repeated_case_percentage: number; extra_occurrences: number; processing_seconds: Distribution; processing_coverage_percentage: number; incoming_wait: WaitingMetrics }
export interface TransitionPerformance { id: string; source: string; target: string; source_label: string; target_label: string; frequency: number; case_frequency: number; waiting: WaitingMetrics; resource_comparable_pairs: number | null; resource_handovers: number | null; department_comparable_pairs: number | null; department_handovers: number | null }
export interface AssignmentMetric { id: string; label: string; names: string[]; roles: string[]; event_count: number; case_count: number; activity_count: number; event_share_percentage: number; total_processing_seconds: number | null; processing_seconds: Distribution; processing_coverage_percentage: number; repeated_case_assignments: number; same_activity_repeat_assignments: number }
export interface AssignmentAnalysis { field: string; known_event_count: number; missing_event_count: number; coverage_percentage: number; comparable_adjacent_pairs: number; changed_assignment_pairs: number; same_assignment_pairs: number; handover_rate_percentage: number | null; handovers_per_fully_observed_case: Distribution; fully_observed_case_count: number; members: AssignmentMetric[]; handovers: { source: string; target: string; count: number; affected_case_count: number }[] }
export interface ProcessPerformance {
  id: string; name: string; total_cases: number; total_events: number; case_duration_seconds: Distribution; completed_case_duration_seconds: Distribution; full_interval_case_duration_seconds: Distribution;
  completion: { status_counts: Record<string, number>; known_status_cases: number; status_coverage_percentage: number; completion_rate_percentage: number | null; known_status_completion_rate_percentage: number | null };
  processing_seconds: Distribution; waiting: WaitingMetrics; variant_count: number; repeated_case_count: number; repeated_case_percentage: number;
  activities: ActivityPerformance[]; transitions: TransitionPerformance[]; resources: AssignmentAnalysis | null; departments: AssignmentAnalysis | null;
  effective_thresholds: Record<string, unknown>; finding_count: number; findings_by_category: Record<string, number>; warnings: string[];
}
export interface AnalyticsResult { dataset_id: string; analysis_id: string; discovery_analysis_id: string; validation_id: string; created_at: string; total_cases: number; total_events: number; process_count: number; finding_count: number; case_duration_seconds: Distribution; processes: ProcessPerformance[]; semantics: Record<string, string> }
export type FindingCategory = 'long_processing' | 'long_waiting' | 'repeated_activity' | 'rework_path' | 'delayed_cases' | 'slow_variant' | 'frequent_handovers' | 'workload_imbalance';
export type Severity = 'low' | 'medium' | 'high';
export interface FindingEntity { kind: 'activity' | 'transition' | 'process' | 'variant' | 'resource' | 'department'; id: string; label: string; source?: string | null; target?: string | null }
export interface Finding {
  id: string; process_id: string; process_type: string; entity: FindingEntity; category: FindingCategory; measured_metric: string; unit: 'seconds' | 'percentage' | 'count'; measurement: 'measured' | 'approximation' | 'observed_span'; observed_value: number;
  baseline: { method: string; cohort: string; sample_count: number; comparison_value: number | null; threshold: number; q1: number | null; q3: number | null };
  affected_case_count: number; severity: Severity;
  evidence: { explanation: string; eligible_observation_count: number; affected_observation_count: number; eligible_case_count: number; examples: { case_id: string; source_rows: number[]; value: number; unit: 'seconds' | 'percentage' | 'count' }[]; caveats: string[] };
  potential_impact: { description: string; observed_excess_seconds: number | null; savings_estimated: false }; cause_status: 'not_established';
}
export interface VariantPerformance { id: string; activity_sequence: string[]; case_count: number; percentage: number; case_duration_seconds: Distribution; repeated_activity_count: number; extra_event_percentage: number; case_status_counts: Record<string, number> }
export interface Recommendation { id: string; process_id: string; process_type: string; title: string; category: FindingCategory; priority: Severity; entity: FindingEntity; finding_ids: string[]; evidence_summary: string; actions: string[]; measurement_plan: string[]; caveats: string[]; affected_case_count: number; expected_improvement: null }
export interface CaseSummary { id: string; case_id: string; process_id: string; process_type: string; variant_id: string; event_count: number; observed_duration_seconds: number; status: string }
export interface CaseEvent { case_id: string; process_type: string; activity: string; timestamp: string; event_order: number; source_row: number; resource_id: string | null; resource_name: string | null; resource_role: string | null; department: string | null; activity_start: string | null; activity_end: string | null; event_id: string | null; status: string | null; outcome: string | null; cost: number | null; attributes: Record<string, unknown> }
export interface CaseTimeline { analysis_id: string; case: CaseSummary; total_events: number; offset: number; limit: number; events: CaseEvent[] }
export interface Page<T> { analysis_id: string; process_id?: string; total: number; offset: number; limit: number; items: T[] }
export interface AnalysisStage { key: string; label: string; status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'; detail: string | null; started_at: string | null; completed_at: string | null }
export interface AnalysisJob { id: string; dataset_id: string; status: 'queued' | 'running' | 'completed' | 'failed'; current_stage: string | null; stages: AnalysisStage[]; created_at: string; updated_at: string; error: { code: string; message: string } | null; discovery_analysis_id: string | null; analytics_analysis_id: string | null }
export type CaseState = 'completed' | 'incomplete' | 'cancelled' | 'unknown';
export interface CaseStatusInterpretation { case_status_attribute: string; case_status_values: Record<string, CaseState> }
export interface AnalysisJobRequest { validation_id?: string; acknowledge_warnings?: boolean; analytics?: { discovery: CaseStatusInterpretation } }

const client = createApiClient({ ...apiConfig, timeoutMs: 120_000 });
const datasetPath = (id: string) => `/datasets/${encodeURIComponent(id)}`;
export function queryString(values: Record<string, string | number | undefined | null>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  return params.size ? `?${params}` : '';
}
function object(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object'; }
export function decodeJob(value: unknown): AnalysisJob {
  if (!object(value) || typeof value.id !== 'string' || typeof value.dataset_id !== 'string' || !['queued', 'running', 'completed', 'failed'].includes(String(value.status)) || !Array.isArray(value.stages) || !value.stages.every(stage => object(stage) && typeof stage.key === 'string' && typeof stage.label === 'string' && ['pending', 'running', 'completed', 'failed', 'skipped'].includes(String(stage.status)))) {
    throw new ApiError('The service returned an invalid analysis status.', { code: 'INVALID_RESPONSE' });
  }
  return value as unknown as AnalysisJob;
}
export const getReadyDataset = (id: string, signal?: AbortSignal) => client.request<ReadyDataset>(`${datasetPath(id)}/result`, { signal });
export const getDiscovery = (id: string, signal?: AbortSignal) => client.request<DiscoveryResult>(`${datasetPath(id)}/discovery`, { signal });
export const getAnalytics = (id: string, signal?: AbortSignal) => client.request<AnalyticsResult>(`${datasetPath(id)}/analytics`, { signal });
export const startAnalysisJob = (id: string, body: AnalysisJobRequest = {}, signal?: AbortSignal) => client.request<AnalysisJob>(`${datasetPath(id)}/analysis-jobs`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal }, decodeJob);
export const getLatestJob = (id: string, signal?: AbortSignal) => client.request<AnalysisJob>(`${datasetPath(id)}/analysis-jobs/latest`, { signal }, decodeJob);
export const getAnalysisJob = (id: string, jobId: string, signal?: AbortSignal) => client.request<AnalysisJob>(`${datasetPath(id)}/analysis-jobs/${encodeURIComponent(jobId)}`, { signal }, decodeJob);
export const getFindings = (id: string, filters: { process_id?: string; category?: string; severity?: string; entity_id?: string; offset?: number; limit?: number } = {}, signal?: AbortSignal) => client.request<Page<Finding>>(`${datasetPath(id)}/analytics/findings${queryString(filters)}`, { signal });
export const getVariants = (id: string, processId: string, filters: { offset?: number; limit?: number } = {}, signal?: AbortSignal) => client.request<Page<VariantPerformance>>(`${datasetPath(id)}/analytics/processes/${encodeURIComponent(processId)}/variants${queryString(filters)}`, { signal });
export const getRecommendations = (id: string, filters: { process_id?: string; offset?: number; limit?: number } = {}, signal?: AbortSignal) => client.request<Page<Recommendation>>(`${datasetPath(id)}/recommendations${queryString(filters)}`, { signal });
export const getCases = (id: string, filters: { process_id?: string; variant_id?: string; search?: string; offset?: number; limit?: number } = {}, signal?: AbortSignal) => client.request<Page<CaseSummary>>(`${datasetPath(id)}/cases${queryString(filters)}`, { signal });
export const getCaseTimeline = (id: string, caseId: string, filters: { offset?: number; limit?: number } = {}, signal?: AbortSignal) => client.request<CaseTimeline>(`${datasetPath(id)}/cases/${encodeURIComponent(caseId)}${queryString(filters)}`, { signal });

export function pollDelay(signal: AbortSignal, milliseconds = 600): Promise<void> {
  return new Promise((resolve, reject) => {
    const abort = () => { clearTimeout(timer); reject(new ApiError('The request was cancelled.', { code: 'ABORTED' })); };
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve(); }, milliseconds);
    if (signal.aborted) abort();
    else signal.addEventListener('abort', abort, { once: true });
  });
}
