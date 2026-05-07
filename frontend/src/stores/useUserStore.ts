/**
 * User store for authentication and user state management
 * Uses Zustand with persistence for cross-session state
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api, ApiErrorClass } from '@/utils/apiClient';
import { setTokens, clearTokens, isAuthenticated as isTokenValid } from '@/utils/tokenManager';
import type {
  User,
  UserLoginData,
  UserRegisterData,
  LoginResponse,
  RegisterResponse,
  UserResponse,
} from '@/types/user';

interface UserState {
  // State
  user: User | null;
  isLoading: boolean;
  error: string | null;

  // Actions
  fetchUser: (userId: number) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  register: (userData: UserRegisterData) => Promise<void>;
  cleanError: () => void;
  setUser: (user: User | null) => void;
}

export const useUserStore = create<UserState>()(
  persist(
    (set) => ({
      // Estado inicial
      user: null,
      isLoading: false,
      error: null,

      /**
       * Obtiene el usuario por ID desde la API
       */
      fetchUser: async (userId: number) => {
        set({ isLoading: true, error: null });

        try {
          const response = await api.get<User>(`/users/${userId}/`);
          set({ user: response, isLoading: false, error: null });
        } catch (err) {
          const errorMessage =
            err instanceof ApiErrorClass
              ? err.message
              : 'No se han podido obtener los datos de usuario';

          set({
            error: errorMessage,
            isLoading: false,
            user: null,
          });

          // If unauthorized, clear everything
          if (err instanceof ApiErrorClass && err.status === 401) {
            clearTokens();
          }

          throw err;
        }
      },

      /**
       * Inicia sesión con nombre de usuario y contraseña
       * Guarda los tokens JWT y los datos de usuario si tiene éxito
       */
      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null });

        try {
          // Valida las entradas
          if (!username || !password) {
            throw new ApiErrorClass('El nombre de usuario y la contraseña son obligatorios');
          }

          const loginData: UserLoginData = { username, password };

          // Llama al endpoint de API de inicio de sesión
          const response = await api.post<LoginResponse>(
            '/users/login/',
            loginData,
            { skipAuth: true }
          );

          // Guarda los tokens
          setTokens({
            access: response.tokens.access,
            refresh: response.tokens.refresh,
          });

          // Actualiza el estado de usuario
          set({
            user: response.user,
            isLoading: false,
            error: null,
          });
        } catch (err) {
          const errorMessage =
            err instanceof ApiErrorClass
              ? err.message
              : 'Login failed. Please check your credentials.';

          set({
            error: errorMessage,
            isLoading: false,
            user: null,
          });

          // Clear any existing tokens on login failure
          clearTokens();

          throw err;
        }
      },

      /**
       * Registra un usuario nuevo
       * Inicia sesión automáticamente tras registrar correctamente al usuario
       */
      register: async (userData: UserRegisterData) => {
        set({ isLoading: true, error: null });

        try {
          // Valida los campos obligatorios
          if (!userData.email || !userData.password) {
            throw new ApiErrorClass(
              'El correo electrónico y la contraseña son obligatorios'
            );
          }

          const payload = {
            ...userData,
            password2: userData.password2 || userData.password,
          };

          // Llama al endpoint de API de registro
          await api.post<RegisterResponse>(
            '/auth/register/',
            payload,
            { skipAuth: true }
          );

          // El registro con verificación de correo no inicia sesión al usuario.
          clearTokens();
          set({
            user: null,
            isLoading: false,
            error: null,
          });
        } catch (err) {
          const errorMessage =
            err instanceof ApiErrorClass
              ? err.message
              : 'Registration failed. Please try again.';

          set({
            error: errorMessage,
            isLoading: false,
            user: null,
          });

          // Clear any tokens on registration failure
          clearTokens();

          throw err;
        }
      },

      /**
       * Logout user
       * Clears user state and JWT tokens
       */
      logout: () => {
        // Clear tokens from storage
        clearTokens();

        // Clear user state
        set({
          user: null,
          isLoading: false,
          error: null,
        });

        // Optional: Call logout endpoint to invalidate token on server
        // This is a fire-and-forget request, we don't wait for it
        try {
          api.post('/users/logout/', {}).catch(() => {
            // Ignore errors on logout endpoint
          });
        } catch {
          // Ignore errors
        }
      },

      /**
       * Clear error message
       */
      cleanError: () => {
        set({ error: null });
      },

      /**
       * Set user data manually (useful for updates)
       */
      setUser: (user: User | null) => {
        set({ user });
      },
    }),
    {
      name: 'user-storage',
      // Only persist user data, not loading/error states
      partialize: (state) => ({ user: state.user }),
    }
  )
);

/**
 * Selector hooks for specific parts of state
 * These help prevent unnecessary re-renders
 */
export const useUser = () => useUserStore((state) => state.user);
export const useIsLoading = () => useUserStore((state) => state.isLoading);
export const useError = () => useUserStore((state) => state.error);
export const useIsAuthenticated = () => useUserStore((state) => !!state.user && isTokenValid());
