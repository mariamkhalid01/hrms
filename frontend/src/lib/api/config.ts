export const apiConfig = {
  baseUrl: (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, ''),
  timeoutMs: 10_000,
} as const;
