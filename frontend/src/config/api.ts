// Server-side env var for SSR/build-time use (BACKEND_API_URL)
// Client-side env var for inline scripts (PUBLIC_API_URL)
// Falls back to localhost for local development.
const API_URL =
  import.meta.env.BACKEND_API_URL ||
  import.meta.env.PUBLIC_API_URL ||
  'http://localhost:8000/api';

export const API_BASE_URL = API_URL;
export default API_URL;
