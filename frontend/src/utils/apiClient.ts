/**
 * API client with automatic JWT token handling
 */

import API_URL from '@/config/api';
import { getAccessToken, getRefreshToken, setTokens, clearTokens, needsTokenRefresh } from './tokenManager';
import type { ApiError, AuthTokens } from '@/types/user';

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
  skipRefresh?: boolean;
}

/**
 * Custom error class for API errors
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
 * Refresh the access token using the refresh token
 */
async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    clearTokens();
    return null;
  }

  try {
    const response = await fetch(`${API_URL}/auth/token/refresh/`, {
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
        refresh: refreshToken,
      });
      return data.access;
    }

    return null;
  } catch (error) {
    console.error('Token refresh failed:', error);
    clearTokens();
    return null;
  }
}

/**
 * Parse error response from API
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
    errorData = { message: 'An unknown error occurred' };
  }

  return {
    message: errorData.message || errorData.detail || 'An error occurred',
    errors: errorData.errors || errorData,
    status: response.status,
  };
}

/**
 * Make an authenticated API request
 */
export async function apiRequest<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { skipAuth, skipRefresh, ...fetchOptions } = options;

  // Prepare headers
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...fetchOptions.headers,
  };

  // Add authorization header if not skipped
  if (!skipAuth) {
    // Check if token needs refresh
    if (!skipRefresh && needsTokenRefresh()) {
      const newToken = await refreshAccessToken();
      if (!newToken) {
        throw new ApiErrorClass('Session expired. Please log in again.', 401);
      }
    }

    const accessToken = getAccessToken();
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`;
    }
  }

  // Make the request
  try {
    const response = await fetch(`${API_URL}${endpoint}`, {
      ...fetchOptions,
      headers,
    });

    // Handle 401 Unauthorized - try to refresh token once
    if (response.status === 401 && !skipAuth && !skipRefresh) {
      const newToken = await refreshAccessToken();

      if (newToken) {
        // Retry the request with new token
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
        throw new ApiErrorClass('Session expired. Please log in again.', 401);
      }
    }

    // Handle other error responses
    if (!response.ok) {
      const error = await parseErrorResponse(response);
      throw new ApiErrorClass(error.message, response.status, error.errors);
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    // Parse and return JSON response
    return await response.json();
  } catch (error) {
    // Re-throw ApiErrorClass instances
    if (error instanceof ApiErrorClass) {
      throw error;
    }

    // Handle network errors
    if (error instanceof TypeError) {
      throw new ApiErrorClass('Network error. Please check your connection.');
    }

    // Handle other errors
    throw new ApiErrorClass(
      error instanceof Error ? error.message : 'An unexpected error occurred'
    );
  }
}

/**
 * Convenience methods for common HTTP methods
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
