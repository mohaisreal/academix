/**
 * Authentication hook for easy access to auth functionality
 */

import { useUserStore, useUser, useIsLoading, useError, useIsAuthenticated } from '@/stores/useUserStore';
import type { UserRegisterData } from '@/types/user';

export function useAuth() {
  const user = useUser();
  const isLoading = useIsLoading();
  const error = useError();
  const isAuthenticated = useIsAuthenticated();

  const { login, logout, register, fetchUser, cleanError } = useUserStore();

  return {
    // State
    user,
    isLoading,
    error,
    isAuthenticated,

    // Actions
    login,
    logout,
    register,
    fetchUser,
    cleanError,
  };
}

/**
 * Hook to require authentication
 * Redirects to login page if not authenticated
 */
export function useRequireAuth(redirectUrl: string = '/login') {
  const isAuthenticated = useIsAuthenticated();
  const user = useUser();

  if (typeof window !== 'undefined' && !isAuthenticated) {
    window.location.href = redirectUrl;
  }

  return { user, isAuthenticated };
}
