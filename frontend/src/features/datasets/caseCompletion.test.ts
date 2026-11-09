import { describe, expect, it } from 'vitest';
import { analysisJobRequest, emptyCaseCompletion, interpretCaseCompletion } from './caseCompletion';

describe('explicit case outcome interpretation', () => {
  it('omits discovery settings unless the analyst selects a case outcome column', () => {
    expect(analysisJobRequest('revision-1', true, emptyCaseCompletion())).toEqual({ validation_id: 'revision-1', acknowledge_warnings: true });
    expect(interpretCaseCompletion({ ...emptyCaseCompletion(), completed: 'Done' })).toEqual({});
  });

  it('sends the chosen source attribute and exact source values through the job contract', () => {
    const draft = { attribute: 'Request outcome at cutoff', completed: 'Closed\nDeclined', incomplete: 'Pending', cancelled: 'Withdrawn' };
    expect(analysisJobRequest('revision-2', false, draft)).toEqual({
      validation_id: 'revision-2', acknowledge_warnings: false,
      analytics: { discovery: { case_status_attribute: 'Request outcome at cutoff', case_status_values: { Closed: 'completed', Declined: 'completed', Pending: 'incomplete', Withdrawn: 'cancelled' } } },
    });
  });

  it('rejects duplicate assignments across groups and within a group ignoring whitespace and case', () => {
    expect(interpretCaseCompletion({ ...emptyCaseCompletion(), attribute: 'Outcome', completed: 'Closed', incomplete: ' closed ' }).error).toContain('more than once');
    expect(interpretCaseCompletion({ ...emptyCaseCompletion(), attribute: 'Outcome', completed: 'Done\nDONE' }).error).toContain('more than once');
  });

  it('does not send an incomplete or oversized value mapping to the server', () => {
    expect(interpretCaseCompletion({ ...emptyCaseCompletion(), attribute: 'Outcome' }).error).toContain('at least one');
    expect(() => analysisJobRequest('revision-3', true, { ...emptyCaseCompletion(), attribute: 'Outcome' })).toThrow('at least one');
    expect(interpretCaseCompletion({ ...emptyCaseCompletion(), attribute: 'Outcome', completed: Array.from({ length: 101 }, (_, index) => `State ${index}`).join('\n') }).error).toContain('100');
  });

  it('preserves zero, commas and arbitrary string keys as literal source outcomes', () => {
    const result = analysisJobRequest('revision-4', true, { ...emptyCaseCompletion(), attribute: 'State', completed: '0\nClosed, unsuccessful\n__proto__' });
    expect(JSON.parse(JSON.stringify(result)).analytics.discovery.case_status_values).toEqual({ '0': 'completed', 'Closed, unsuccessful': 'completed', ['__proto__']: 'completed' });
  });

  it('creates an independent job snapshot so later draft edits cannot change a submitted mapping', () => {
    const draft = { ...emptyCaseCompletion(), attribute: 'Lifecycle', completed: 'Done' };
    const submitted = analysisJobRequest('revision-5', true, draft);
    draft.completed = 'Closed'; draft.attribute = 'Another column';
    expect(submitted.analytics?.discovery).toEqual({ case_status_attribute: 'Lifecycle', case_status_values: { Done: 'completed' } });
  });
});
