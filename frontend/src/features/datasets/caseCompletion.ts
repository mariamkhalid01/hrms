import type { AnalysisJobRequest, CaseState, CaseStatusInterpretation } from '../../lib/api/analysis';

export interface CaseCompletionDraft { attribute: string; completed: string; incomplete: string; cancelled: string }
export const emptyCaseCompletion = (): CaseCompletionDraft => ({ attribute: '', completed: '', incomplete: '', cancelled: '' });

export function interpretCaseCompletion(draft: CaseCompletionDraft): { interpretation?: CaseStatusInterpretation; error?: string } {
  if (!draft.attribute) return {};
  const values = Object.create(null) as Record<string, CaseState>;
  const known = new Set<string>();
  for (const state of ['completed', 'incomplete', 'cancelled'] as const) {
    for (const raw of draft[state].split(/\r?\n/)) {
      const value = raw.trim();
      if (!value) continue;
      const key = value.toLowerCase();
      if (known.has(key)) return { error: `“${value}” appears more than once. Assign each source value to one case outcome only.` };
      known.add(key); values[value] = state;
    }
  }
  if (known.size === 0) return { error: 'Enter at least one case outcome value, or choose “Not configured” to leave completion unknown.' };
  if (known.size > 100) return { error: 'Use at most 100 distinct case outcome values.' };
  return { interpretation: { case_status_attribute: draft.attribute, case_status_values: values } };
}

export function analysisJobRequest(validationId: string, acknowledged: boolean, draft: CaseCompletionDraft): AnalysisJobRequest {
  const { interpretation, error } = interpretCaseCompletion(draft);
  if (error) throw new Error(error);
  return {
    validation_id: validationId,
    acknowledge_warnings: acknowledged,
    ...(interpretation ? { analytics: { discovery: interpretation } } : {}),
  };
}
