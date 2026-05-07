/**
 * Utilidades de gestión de tokens para autenticación JWT
 */
import type { AuthTokens } from '@/types/user';

const TOKEN_KEYS = {
  ACCESS: 'access_token',
  REFRESH: 'refresh_token',
} as const;

/**
 * Guarda los tokens de autenticación en localStorage
 */
export function setTokens(tokens: AuthTokens): void {
  try {
    localStorage.setItem(TOKEN_KEYS.ACCESS, tokens.access);
    localStorage.setItem(TOKEN_KEYS.REFRESH, tokens.refresh);
  } catch (error) {
    console.error('Failed to store tokens:', error);
  }
}

/**
 * Obtiene el token de acceso desde localStorage
 */
export function getAccessToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEYS.ACCESS);
  } catch (error) {
    console.error('Failed to get access token:', error);
    return null;
  }
}

/**
 * Obtiene el token de refresco desde localStorage
 */
export function getRefreshToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEYS.REFRESH);
  } catch (error) {
    console.error('Failed to get refresh token:', error);
    return null;
  }
}

/**
 * Elimina todos los tokens de autenticación de localStorage
 */
export function clearTokens(): void {
  try {
    localStorage.removeItem(TOKEN_KEYS.ACCESS);
    localStorage.removeItem(TOKEN_KEYS.REFRESH);
  } catch (error) {
    console.error('Failed to clear tokens:', error);
  }
}

/**
 * Comprueba si el usuario está autenticado verificando existencia y validez del token
 */
export function isAuthenticated(): boolean {
  const token = getAccessToken();
  if (!token) return false;

  // Comprueba si el token ha caducado (sin el margen de refresco de 60 s)
  const expiration = getTokenExpiration(token);
  if (!expiration) return false;

  return Date.now() < expiration;
}

/**
 * Decodifica el token JWT para obtener la hora de caducidad
 */
export function getTokenExpiration(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp ? payload.exp * 1000 : null;
  } catch (error) {
    console.error('Failed to decode token:', error);
    return null;
  }
}

/**
 * Comprueba si el token de acceso ha caducado
 */
export function isTokenExpired(token: string): boolean {
  const expiration = getTokenExpiration(token);
  if (!expiration) return true;

  // Añade un margen de 60 segundos para refrescar antes de la caducidad real
  return Date.now() >= expiration - 60000;
}

/**
 * Comprueba si el token de acceso actual necesita refresco
 */
export function needsTokenRefresh(): boolean {
  const accessToken = getAccessToken();
  if (!accessToken) return false;

  return isTokenExpired(accessToken);
}
