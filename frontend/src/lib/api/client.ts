export class ApiError extends Error {
  readonly code: string;
  readonly status?: number;
  readonly details?: unknown;
  readonly requestId?: string;

  constructor(message: string, options: { code: string; status?: number; details?: unknown; requestId?: string }) {
    super(message);
    this.name = 'ApiError';
    this.code = options.code;
    this.status = options.status;
    this.details = options.details;
    this.requestId = options.requestId;
  }
}

function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function createApiClient(config: { baseUrl: string; timeoutMs?: number; fetcher?: typeof fetch }) {
  const baseUrl = config.baseUrl.replace(/\/$/, '');
  const fetcher = config.fetcher ?? fetch;

  async function request<T>(path: string, options: RequestInit = {}, decode?: (value: unknown) => T): Promise<T> {
    const controller = new AbortController();
    let timedOut = false;
    const abort = () => controller.abort();
    if (options.signal?.aborted) abort();
    else options.signal?.addEventListener('abort', abort, { once: true });
    const timeout = setTimeout(() => { timedOut = true; controller.abort(); }, config.timeoutMs ?? 10_000);

    try {
      const headers = new Headers(options.headers);
      if (!headers.has('Accept')) headers.set('Accept', 'application/json');
      // Do not force Content-Type: future multipart uploads need their browser-generated boundary.
      const response = await fetcher(`${baseUrl}${path}`, { ...options, headers, signal: controller.signal });
      let body: unknown;
      const text = await response.text();
      try { body = text ? JSON.parse(text) : undefined; }
      catch {
        throw new ApiError(response.ok ? 'The service returned an unreadable response.' : 'The service could not complete the request.', {
          code: response.ok ? 'INVALID_RESPONSE' : 'HTTP_ERROR', status: response.status,
          requestId: response.headers.get('x-request-id') ?? undefined,
        });
      }
      if (!response.ok) {
        const error = record(body) && record(body.error) ? body.error : undefined;
        throw new ApiError(typeof error?.message === 'string' ? error.message : 'The service could not complete the request.', {
          code: typeof error?.code === 'string' ? error.code : 'HTTP_ERROR',
          status: response.status,
          details: error?.details,
          requestId: typeof error?.request_id === 'string' ? error.request_id : response.headers.get('x-request-id') ?? undefined,
        });
      }
      return decode ? decode(body) : body as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      if (controller.signal.aborted) {
        throw new ApiError(timedOut ? 'The service took too long to respond.' : 'The request was cancelled.', { code: timedOut ? 'TIMEOUT' : 'ABORTED' });
      }
      throw new ApiError('Unable to reach the analysis service. Check your connection and try again.', { code: 'NETWORK_ERROR' });
    } finally {
      clearTimeout(timeout);
      options.signal?.removeEventListener('abort', abort);
    }
  }

  return { request };
}
