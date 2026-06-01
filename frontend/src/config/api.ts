type RuntimeEnv = {
  BACKEND_API_URL?: string;
  PUBLIC_API_URL?: string;
  MODE?: string;
  DEV?: boolean;
};

export function resolveApiBaseUrl(env: RuntimeEnv): string {
  const backend = env.BACKEND_API_URL?.trim();
  if (backend) return backend;

  const publicUrl = env.PUBLIC_API_URL?.trim();
  if (publicUrl) return publicUrl;

  const isDev = env.DEV === true || env.MODE === 'development';
  const devLocalApi = 'http://localhost:8000' + '/api';
  return isDev ? devLocalApi : '/api';
}

const API_URL = resolveApiBaseUrl(import.meta.env as RuntimeEnv);

export const API_BASE_URL = API_URL;
export default API_URL;
