/**
 * Cliente de API con gestión automática de tokens JWT
 */
import API_URL from '@/config/api';
import { getAccessToken, getRefreshToken, setTokens, clearTokens, needsTokenRefresh } from './tokenManager';
import type { ApiError, AuthTokens } from '@/types/user';

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
  skipRefresh?: boolean;
}

/**
 * Clase de error personalizada para errores de API
 */
export class ApiErrorClass extends Error {
  public status?: number;
  public errors?: Record<string, string[]>;

  constructor(message: string, status?: number, errors?: Record<string, string[]>) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errors = errors;
  }
}

/**
 * Refresca el token de acceso usando el token de refresco
 */
async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    clearTokens();
    return null;
  }

  try {
    const response = await fetch(`${API_URL}/users/token/refresh/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh: refreshToken }),
    });

    if (!response.ok) {
      clearTokens();
      return null;
    }

    const data = await response.json();

    if (data.access) {
      setTokens({
        access: data.access,
        refresh: data.refresh || refreshToken,
      });
      return data.access;
    }

    return null;
  } catch (error) {
    console.error('Falló la actualización del token:', error);
    clearTokens();
    return null;
  }
}

/**
 * Analiza la respuesta de error de la API
 */
async function parseErrorResponse(response: Response): Promise<ApiError> {
  let errorData: any = {};

  try {
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      errorData = await response.json();
    } else {
      errorData = { message: await response.text() };
    }
  } catch (e) {
    errorData = { message: 'Ocurrió un error desconocido' };
  }

  return {
    message: errorData.message || errorData.detail || errorData.error || 'Ocurrió un error',
    errors: errorData.errors || errorData,
    status: response.status,
  };
}

/**
 * Realiza una petición autenticada a la API
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { skipAuth, skipRefresh, ...fetchOptions } = options;

  // Prepara las cabeceras
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(fetchOptions.headers as Record<string, string> | undefined),
  };

  // Añade la cabecera de autorización si no se omite
  if (!skipAuth) {
    // Comprueba si el token necesita actualización
    if (!skipRefresh && needsTokenRefresh()) {
      const newToken = await refreshAccessToken();
      if (!newToken) {
        throw new ApiErrorClass('La sesión expiró. Inicia sesión de nuevo.', 401);
      }
    }

    const accessToken = getAccessToken();
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }
  }

  // Realiza la petición
  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      ...fetchOptions,
      headers,
    });

    // Gestiona 401 Unauthorized: intenta refrescar el token una vez
    if (response.status === 401 && !skipAuth && !skipRefresh) {
      const newToken = await refreshAccessToken();

      if (newToken) {
        // Reintenta la petición con el token nuevo
        headers['Authorization'] = `Bearer ${newToken}`;
        const retryResponse = await fetch(`${API_URL}${endpoint}`, {
          ...fetchOptions,
          headers,
        });

        if (!retryResponse.ok) {
          const error = await parseErrorResponse(retryResponse);
          throw new ApiErrorClass(error.message, retryResponse.status, error.errors);
        }

        return await retryResponse.json();
      } else {
        throw new ApiErrorClass('La sesión expiró. Inicia sesión de nuevo.', 401);
      }
    }

    // Gestiona otras respuestas de error
    if (!response.ok) {
      const error = await parseErrorResponse(response);
      throw new ApiErrorClass(error.message, response.status, error.errors);
    }

    // Gestiona 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    // Analiza y devuelve la respuesta JSON
    return await response.json();
  } catch (error) {
    // Relanza instancias de ApiErrorClass
    if (error instanceof ApiErrorClass) {
      throw error;
    }

    // Gestiona errores de red
    if (error instanceof TypeError) {
      throw new ApiErrorClass('Error de red. Revisa tu conexión.');
    }

    // Gestiona otros errores
    throw new ApiErrorClass(
      error instanceof Error ? error.message : 'Ocurrió un error inesperado'
    );
  }
}

/**
 * Métodos de conveniencia para métodos HTTP comunes
 */
export const api = {
  get: <T>(endpoint: string, options?: RequestOptions) =>
    apiRequest<T>(endpoint, { ...options, method: 'GET' }),

  post: <T>(endpoint: string, data?: any, options?: RequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    }),

  put: <T>(endpoint: string, data?: any, options?: RequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: 'PUT',
      body: data ? JSON.stringify(data) : undefined,
    }),

  patch: <T>(endpoint: string, data?: any, options?: RequestOptions) =>
    apiRequest<T>(endpoint, {
      ...options,
      method: 'PATCH',
      body: data ? JSON.stringify(data) : undefined,
    }),

  delete: <T>(endpoint: string, options?: RequestOptions) =>
    apiRequest<T>(endpoint, { ...options, method: 'DELETE' }),
};
