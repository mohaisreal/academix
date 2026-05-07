// Variable de entorno del servidor para uso en SSR/tiempo de construcción (BACKEND_API_URL)
// Variable de entorno del cliente para scripts inline (PUBLIC_API_URL)
// Usa localhost como respaldo para desarrollo local.
const API_URL =
  import.meta.env.BACKEND_API_URL ||
  import.meta.env.PUBLIC_API_URL ||
  'http://localhost:8000/api';

export const API_BASE_URL = API_URL;
export default API_URL;
