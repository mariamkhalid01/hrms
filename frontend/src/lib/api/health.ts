import { ApiError, createApiClient } from './client';
import { apiConfig } from './config';

export interface HealthResponse {
  status: 'ok';
  service: string;
  version: string;
  environment: string;
}

export function decodeHealth(value: unknown): HealthResponse {
  if (typeof value !== 'object' || value === null) throw new ApiError('The service returned an invalid health response.', { code: 'INVALID_RESPONSE' });
  const response = value as Record<string, unknown>;
  if (response.status !== 'ok' || response.service !== 'hr-process-mining-api' || !['version', 'environment'].every(key => typeof response[key] === 'string' && response[key].length > 0)) {
    throw new ApiError('The service returned an invalid health response.', { code: 'INVALID_RESPONSE' });
  }
  return response as unknown as HealthResponse;
}

const client = createApiClient(apiConfig);
export const getHealth = (signal?: AbortSignal) => client.request('/health', { signal }, decodeHealth);
