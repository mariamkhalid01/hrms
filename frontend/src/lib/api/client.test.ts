import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, createApiClient } from './client';
import { decodeHealth } from './health';

afterEach(() => vi.useRealTimers());

describe('API transport', () => {
  it('uses the configured API prefix and returns validated health data', async () => {
    const health = { status: 'ok', service: 'hr-process-mining-api', version: '0.1.0', environment: 'development' };
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(health), { status: 200 }));
    const api = createApiClient({ baseUrl: '/api/v1/', fetcher });
    expect(await api.request('/health', {}, decodeHealth)).toEqual(health);
    expect(fetcher.mock.calls[0]?.[0]).toBe('/api/v1/health');
    expect(new Headers(fetcher.mock.calls[0]?.[1]?.headers).get('Accept')).toBe('application/json');
  });

  it('preserves structured server errors and request identifiers', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ error: { code: 'INVALID_LOG', message: 'The event log is missing a case identifier.', details: { column: 'case_id' }, request_id: 'req-123' } }), { status: 422 }));
    const api = createApiClient({ baseUrl: '/api/v1', fetcher });
    await expect(api.request('/validation')).rejects.toMatchObject({ name: 'ApiError', code: 'INVALID_LOG', status: 422, requestId: 'req-123', details: { column: 'case_id' } });
  });

  it('does not expose an HTML proxy error to the user', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response('<html>internal proxy stack</html>', { status: 502 }));
    const api = createApiClient({ baseUrl: '/api/v1', fetcher });
    await expect(api.request('/health')).rejects.toMatchObject({ code: 'HTTP_ERROR', status: 502, message: 'The service could not complete the request.' });
  });

  it('normalizes a connection failure', async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new TypeError('fetch failed'));
    const api = createApiClient({ baseUrl: '/api/v1', fetcher });
    await expect(api.request('/health')).rejects.toMatchObject({ code: 'NETWORK_ERROR' });
  });

  it('times out and aborts a slow response', async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn<typeof fetch>().mockImplementation((_url, options) => new Promise((_resolve, reject) => options?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))));
    const api = createApiClient({ baseUrl: '/api/v1', timeoutMs: 100, fetcher });
    const result = expect(api.request('/health')).rejects.toMatchObject({ code: 'TIMEOUT' });
    await vi.advanceTimersByTimeAsync(100);
    await result;
    expect(fetcher.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
  });

  it('distinguishes user cancellation from service timeout', async () => {
    const fetcher = vi.fn<typeof fetch>().mockImplementation((_url, options) => new Promise((_resolve, reject) => options?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')))));
    const api = createApiClient({ baseUrl: '/api/v1', fetcher });
    const controller = new AbortController();
    const result = expect(api.request('/health', { signal: controller.signal })).rejects.toMatchObject({ code: 'ABORTED' });
    controller.abort();
    await result;
  });

  it('rejects malformed successful health responses', () => {
    expect(() => decodeHealth({ status: 'ok' })).toThrow(ApiError);
    expect(() => decodeHealth({ status: 'failed', service: 'service', version: '1', environment: 'test' })).toThrow(ApiError);
  });
});
