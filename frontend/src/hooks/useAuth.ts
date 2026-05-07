/**
 * Hook de autenticación para acceder fácilmente a la funcionalidad de autenticación
 */
import { useUserStore, useUser, useIsLoading, useError, useIsAuthenticated } from '@/stores/useUserStore';

export function useAuth() {
  const user = useUser();
  const isLoading = useIsLoading();
  const error = useError();
  const isAuthenticated = useIsAuthenticated();

  const { login, logout, register, fetchUser, cleanError } = useUserStore();

  return {
    // Estado
    user,
    isLoading,
    error,
    isAuthenticated,

    // Acciones
    login,
    logout,
    register,
    fetchUser,
    cleanError,
  };
}

/**
 * Hook para exigir autenticación
 * Redirige a la página de inicio de sesión si no hay autenticación
 */
export function useRequireAuth(redirectUrl: string = '/login') {
  const isAuthenticated = useIsAuthenticated();
  const user = useUser();

  if (typeof window !== 'undefined' && !isAuthenticated) {
    window.location.href = redirectUrl;
  }

  return { user, isAuthenticated };
}
