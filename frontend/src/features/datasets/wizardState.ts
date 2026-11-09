import { canonicalFields, type ColumnMapping, type DatasetLimits, type DatasetPreview, type MappingRequest, type ReadyDataset, type ValidationReport } from '../../lib/api/datasets';
import { emptyCaseCompletion, interpretCaseCompletion, type CaseCompletionDraft } from './caseCompletion';

export const fieldLabels = {
  case_id: 'Case identifier', activity: 'Activity', timestamp: 'Event timestamp', process_type: 'Process type',
  event_id: 'Event identifier', resource_id: 'Resource identifier', resource_name: 'Resource name', resource_role: 'Resource role',
  department: 'Department', activity_start: 'Activity start', activity_end: 'Activity end', cost: 'Cost', outcome: 'Outcome',
  status: 'Status', event_order: 'Event order',
} satisfies Record<keyof ColumnMapping, string>;
export const requiredFields: (keyof ColumnMapping)[] = ['case_id', 'activity', 'timestamp'];
export const steps = ['Upload', 'Preview', 'Map columns', 'Validate', 'Confirm', 'Process'] as const;

export function initialMapping(suggestions: Partial<ColumnMapping>): ColumnMapping {
  return Object.fromEntries(canonicalFields.map(field => [field, suggestions[field] ?? null])) as ColumnMapping;
}
export function fileProblem(file: Pick<File, 'name' | 'size'>, limits: DatasetLimits): string | null {
  if (!/\.csv$/i.test(file.name)) return 'Choose a file with a .csv extension.';
  if (file.size === 0) return 'This file is empty. Choose a CSV with a header and event records.';
  if (file.size > limits.max_upload_bytes) return `This file exceeds the ${(limits.max_upload_bytes / 1024 / 1024).toLocaleString()} MiB upload limit.`;
  return null;
}
export interface WizardState {
  step: number; preview: DatasetPreview | null; request: MappingRequest;
  report: ValidationReport | null; warningsAcknowledged: boolean; ready: ReadyDataset | null;
  caseCompletion: CaseCompletionDraft;
}
export function initialWizardState(): WizardState {
  return { step: 0, preview: null, request: { mapping: initialMapping({}), timezone: 'UTC', timestamp_format: null, day_first: false }, report: null, warningsAcknowledged: false, ready: null, caseCompletion: emptyCaseCompletion() };
}
export type WizardAction =
  | { type: 'uploaded'; preview: DatasetPreview }
  | { type: 'request'; request: MappingRequest }
  | { type: 'caseCompletion'; value: CaseCompletionDraft }
  | { type: 'validating' }
  | { type: 'validated'; report: ValidationReport }
  | { type: 'acknowledge'; value: boolean }
  | { type: 'step'; step: number }
  | { type: 'ready'; ready: ReadyDataset }
  | { type: 'reset' };
export function canConfirm(state: WizardState): boolean {
  return state.report?.valid === true && !interpretCaseCompletion(state.caseCompletion).error && (state.report.summary.warning_count === 0 || state.warningsAcknowledged);
}
export function canVisit(state: WizardState, step: number): boolean {
  // Finalized datasets are immutable in this wizard. A new upload gets a new ID.
  if (state.ready) return step === 5;
  if (step === 0) return true;
  if (step <= 2) return !!state.preview;
  if (step === 3) return !!state.report;
  if (step === 4) return state.report?.valid === true;
  return !!state.ready;
}
export function wizardReducer(state: WizardState, action: WizardAction): WizardState {
  switch (action.type) {
    case 'uploaded': return { ...initialWizardState(), preview: action.preview, step: 1, request: { ...initialWizardState().request, mapping: initialMapping(action.preview.suggested_mapping) } };
    case 'request': return { ...state, request: action.request, report: null, ready: null, warningsAcknowledged: false, step: 2 };
    case 'caseCompletion': return { ...state, caseCompletion: { ...action.value }, report: null, ready: null, warningsAcknowledged: false, step: 2 };
    case 'validating': return { ...state, report: null, ready: null, warningsAcknowledged: false, step: 3 };
    case 'validated': return { ...state, report: action.report, step: 3, warningsAcknowledged: false, ready: null };
    case 'acknowledge': return { ...state, warningsAcknowledged: action.value };
    case 'step': return { ...state, step: action.step };
    case 'ready': return { ...state, ready: action.ready, step: 5 };
    case 'reset': return initialWizardState();
  }
}
