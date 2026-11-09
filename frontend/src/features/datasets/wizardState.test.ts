import { describe, expect, it } from 'vitest';
import type { DatasetLimits, DatasetPreview, ReadyDataset, ValidationReport } from '../../lib/api/datasets';
import { canConfirm, canVisit, fileProblem, initialMapping, initialWizardState, wizardReducer } from './wizardState';

const limits: DatasetLimits = { max_upload_bytes: 1024, max_rows: 250000, max_columns: 200, preview_rows: 20 };
const preview: DatasetPreview = { id: 'upload-a', filename: 'test.csv', size_bytes: 200, row_count: 2, column_count: 3, columns: [], preview: [], suggested_mapping: initialMapping({ case_id: 'Request', activity: 'Task', timestamp: 'Completed' }), delimiter: ',', encoding: 'utf-8', status: 'uploaded', created_at: '2026-11-09T10:00:00Z' };
const report: ValidationReport = { validation_id: 'revision-a', dataset_id: 'upload-a', valid: true, summary: { event_count: 2, case_count: 1, process_count: 1, error_count: 0, warning_count: 1, info_count: 1 }, issues: [], normalized_preview: [], timezone: 'UTC', source_timezone: 'UTC' };

describe('upload preflight', () => {
  it('rejects a non-CSV, empty file and oversize file before upload', () => {
    expect(fileProblem({ name: 'test.xlsx', size: 10 }, limits)).toContain('.csv');
    expect(fileProblem({ name: 'test.csv', size: 0 }, limits)).toContain('empty');
    expect(fileProblem({ name: 'test.csv', size: 1025 }, limits)).toContain('limit');
    expect(fileProblem({ name: 'TEST.CSV', size: 1024 }, limits)).toBeNull();
  });
});
describe('wizard validation invariants', () => {
  it('starts empty without any selected or suggested data', () => {
    const state = initialWizardState();
    expect(state.preview).toBeNull(); expect(state.report).toBeNull(); expect(state.ready).toBeNull();
    expect(canVisit(state, 1)).toBe(false); expect(canConfirm(state)).toBe(false);
  });
  it('keeps the file and mapping when moving backward', () => {
    const state = wizardReducer(initialWizardState(), { type: 'uploaded', preview });
    const backward = wizardReducer(state, { type: 'step', step: 0 });
    expect(backward.preview).toBe(preview);
    expect(backward.request.mapping.case_id).toBe('Request');
    expect(canVisit(backward, 1)).toBe(true);
  });
  it('requires explicit warning acknowledgement and a valid report', () => {
    let state = wizardReducer(initialWizardState(), { type: 'uploaded', preview });
    state = wizardReducer(state, { type: 'validated', report });
    expect(canConfirm(state)).toBe(false);
    state = wizardReducer(state, { type: 'acknowledge', value: true });
    expect(canConfirm(state)).toBe(true);
    state = wizardReducer(state, { type: 'validated', report: { ...report, valid: false } });
    expect(canConfirm(state)).toBe(false);
  });
  it('invalidates the revision and acknowledgement after mapping or timestamp edits', () => {
    let state = wizardReducer(initialWizardState(), { type: 'uploaded', preview });
    state = wizardReducer(state, { type: 'validated', report });
    state = wizardReducer(state, { type: 'acknowledge', value: true });
    state = wizardReducer(state, { type: 'request', request: { ...state.request, timezone: 'Africa/Cairo' } });
    expect(state.preview).toBe(preview); expect(state.report).toBeNull(); expect(state.warningsAcknowledged).toBe(false);
    expect(state.step).toBe(2); expect(canConfirm(state)).toBe(false); expect(canVisit(state, 4)).toBe(false);
  });
  it('resets validation state when a different file is uploaded', () => {
    let state = wizardReducer(initialWizardState(), { type: 'uploaded', preview });
    state = wizardReducer(state, { type: 'validated', report });
    state = wizardReducer(state, { type: 'uploaded', preview: { ...preview, id: 'upload-b', filename: 'another.csv' } });
    expect(state.report).toBeNull(); expect(state.preview?.id).toBe('upload-b'); expect(state.step).toBe(1);
  });
  it('removes a previous valid revision when revalidation starts, even if the request later fails', () => {
    let state = wizardReducer(initialWizardState(), { type: 'uploaded', preview });
    state = wizardReducer(state, { type: 'validated', report });
    state = wizardReducer(state, { type: 'acknowledge', value: true });
    expect(canConfirm(state)).toBe(true);
    const request = state.request;
    state = wizardReducer(state, { type: 'validating' });
    // A failed request dispatches no success action, so the stale revision stays unavailable.
    expect(state.preview).toBe(preview); expect(state.request).toBe(request);
    expect(state.report).toBeNull(); expect(state.ready).toBeNull(); expect(state.warningsAcknowledged).toBe(false);
    expect(state.step).toBe(3); expect(canConfirm(state)).toBe(false); expect(canVisit(state, 4)).toBe(false);
  });
  it('locks earlier steps after final processing so the selected dataset cannot be invalidated', () => {
    const ready: ReadyDataset = { dataset_id: preview.id, status: 'ready', filename: preview.filename, event_count: 2, case_count: 1, process_count: 1, processes: [{ name: 'Single process', event_count: 2, case_count: 1 }], processed_at: '2026-11-09T11:00:00Z', normalization: { timezone: 'UTC', source_timezone: 'UTC', sorted_by: ['case_key', 'timestamp'], preserved_source: true } };
    let state = wizardReducer(initialWizardState(), { type: 'uploaded', preview });
    state = wizardReducer(state, { type: 'ready', ready });
    for (const step of [0, 1, 2, 3, 4]) expect(canVisit(state, step)).toBe(false);
    expect(canVisit(state, 5)).toBe(true);
    const freshDraft = wizardReducer(state, { type: 'reset' });
    expect(freshDraft.preview).toBeNull(); expect(freshDraft.ready).toBeNull();
    expect(canVisit(freshDraft, 0)).toBe(true); expect(canVisit(freshDraft, 1)).toBe(false);
  });
  it('requires fresh confirmation after changing case outcome interpretation and keeps it for processing retry', () => {
    let state = wizardReducer(initialWizardState(), { type: 'uploaded', preview });
    state = wizardReducer(state, { type: 'validated', report });
    state = wizardReducer(state, { type: 'acknowledge', value: true });
    state = wizardReducer(state, { type: 'caseCompletion', value: { attribute: 'Lifecycle', completed: 'Done', incomplete: 'Open', cancelled: 'Abandoned' } });
    expect(state.report).toBeNull(); expect(state.warningsAcknowledged).toBe(false); expect(canConfirm(state)).toBe(false);
    state = wizardReducer(state, { type: 'validated', report });
    state = wizardReducer(state, { type: 'acknowledge', value: true });
    state = wizardReducer(state, { type: 'step', step: 5 });
    expect(canConfirm(state)).toBe(true); expect(state.caseCompletion.attribute).toBe('Lifecycle');
    expect(state.caseCompletion.completed).toBe('Done');
    state = wizardReducer(state, { type: 'uploaded', preview: { ...preview, id: 'upload-b' } });
    expect(state.caseCompletion.attribute).toBe(''); expect(state.caseCompletion.completed).toBe('');
  });
});
