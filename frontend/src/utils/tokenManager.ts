/**
 * Token management utilities for JWT authentication
 */

import type { AuthTokens } from '@/types/user';

const TOKEN_KEYS = {
  ACCESS: 'access_token',
  REFRESH: 'refresh_token',
} as const;

/**
 * Store authentication tokens in localStorage
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
 * Get the access token from localStorage
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
 * Get the refresh token from localStorage
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
 * Remove all authentication tokens from localStorage
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
 * Check if user is authenticated by verifying token existence
 */
export function isAuthenticated(): boolean {
  return !!getAccessToken();
}

/**
 * Decode JWT token to get expiration time
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
 * Check if the access token is expired
 */
export function isTokenExpired(token: string): boolean {
  const expiration = getTokenExpiration(token);
  if (!expiration) return true;

  // Add 60 second buffer to refresh before actual expiration
  return Date.now() >= expiration - 60000;
}

/**
 * Check if the current access token needs refresh
 */
export function needsTokenRefresh(): boolean {
  const accessToken = getAccessToken();
  if (!accessToken) return false;

  return isTokenExpired(accessToken);
}
