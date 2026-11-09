import { afterEach, describe, expect, it, vi } from 'vitest';
import { decodeJob, pollDelay, queryString } from './analysis';
import { formatDuration, formatNumber, formatPercent } from '../../features/analysis/formatting';

afterEach(() => vi.useRealTimers());

describe('real analysis contracts', () => {
  it('encodes filters without silently dropping a zero offset', () => {
    const query = queryString({ search: 'case / 1 & 2', offset: 0, process_id: undefined, category: '' });
    expect(new URLSearchParams(query).get('search')).toBe('case / 1 & 2');
    expect(new URLSearchParams(query).get('offset')).toBe('0');
    expect(new URLSearchParams(query).has('process_id')).toBe(false);
  });

  it('rejects invented progress states and missing stage labels', () => {
    expect(() => decodeJob({ id: 'job', dataset_id: 'dataset', status: 'half-done', stages: [] })).toThrow();
    expect(() => decodeJob({ id: 'job', dataset_id: 'dataset', status: 'running', stages: [{ key: 'discovering', status: 'running' }] })).toThrow();
    const payload = { id: 'job', dataset_id: 'dataset', status: 'running', stages: [{ key: 'discovering', label: 'Discovering process models', status: 'running' }] };
    expect(decodeJob(payload).stages[0]?.status).toBe('running');
  });

  it('stops polling promptly when dataset selection changes', async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const result = expect(pollDelay(controller.signal)).rejects.toMatchObject({ code: 'ABORTED' });
    controller.abort();
    await result;
    expect(vi.getTimerCount()).toBe(0);
  });

  it('does not convert unavailable measurements into zero', () => {
    expect(formatDuration(null)).toBe('Unavailable');
    expect(formatDuration(0)).toBe('0 s');
    expect(formatDuration(3600)).toBe('1 h');
    expect(formatDuration(-60)).toBe('-1 min');
    expect(formatNumber(undefined)).toBe('Unavailable');
    expect(formatPercent(null)).toBe('Unknown');
    expect(formatPercent(0)).toBe('0%');
  });
});
