type RuntimeEnv = {
  BACKEND_API_URL?: string;
  PUBLIC_API_URL?: string;
  MODE?: string;
  DEV?: boolean;
};

function normalizeApiUrl(url: string): string {
  return url.replace(/\/$/, '');
}

export function resolveApiBaseUrl(env: RuntimeEnv): string {
  const publicUrl = env.PUBLIC_API_URL?.trim();
  if (publicUrl) return normalizeApiUrl(publicUrl);

  const backend = env.BACKEND_API_URL?.trim();
  if (backend) return normalizeApiUrl(backend);

  return '/api';
}

export function resolveWebSocketBaseUrl(env: RuntimeEnv): string {
  const apiBaseUrl = resolveApiBaseUrl(env);
  if (apiBaseUrl.startsWith('http://') || apiBaseUrl.startsWith('https://')) {
    return apiBaseUrl.replace(/\/api$/, '').replace(/^http:/, 'ws:').replace(/^https:/, 'wss:');
  }
  const isDev = env.DEV === true || env.MODE === 'development';
  if (isDev) return 'ws://localhost:8000';

  if (typeof window !== 'undefined') {
    return window.location.protocol === 'https:' ? `wss://${window.location.host}` : `ws://${window.location.host}`;
  }

  return 'ws://localhost';
}

const API_URL = resolveApiBaseUrl(import.meta.env as RuntimeEnv);

export const API_BASE_URL = API_URL;
export default API_URL;
