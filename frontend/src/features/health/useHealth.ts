import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../../lib/api/client';
import { getHealth, type HealthResponse } from '../../lib/api/health';

type HealthState =
  | { status: 'checking' }
  | { status: 'connected'; data: HealthResponse; checkedAt: Date }
  | { status: 'unavailable'; error: ApiError };

export function useHealth() {
  const [state, setState] = useState<HealthState>({ status: 'checking' });
  const current = useRef<AbortController | null>(null);
  const refresh = useCallback(async () => {
    current.current?.abort();
    const controller = new AbortController();
    current.current = controller;
    setState({ status: 'checking' });
    try {
      const data = await getHealth(controller.signal);
      if (!controller.signal.aborted) setState({ status: 'connected', data, checkedAt: new Date() });
    } catch (error) {
      if (!controller.signal.aborted) setState({ status: 'unavailable', error: error instanceof ApiError ? error : new ApiError('The service is unavailable.', { code: 'UNKNOWN_ERROR' }) });
    }
  }, []);
  useEffect(() => {
    void refresh();
    return () => current.current?.abort();
  }, [refresh]);
  return { state, refresh };
}
