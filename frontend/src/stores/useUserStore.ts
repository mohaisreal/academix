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
      // Initial state
      user: null,
      isLoading: false,
      error: null,

      /**
       * Fetch user by ID from the API
       */
      fetchUser: async (userId: number) => {
        set({ isLoading: true, error: null });

        try {
          const response = await api.get<UserResponse>(`/users/${userId}/`);
          set({ user: response.user, isLoading: false, error: null });
        } catch (err) {
          const errorMessage =
            err instanceof ApiErrorClass
              ? err.message
              : 'Failed to fetch user data';

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
       * Login user with email and password
       * Stores JWT tokens and user data on success
       */
      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });

        try {
          // Validate inputs
          if (!email || !password) {
            throw new ApiErrorClass('Email and password are required');
          }

          const loginData: UserLoginData = { email, password };

          // Call login API endpoint
          const response = await api.post<LoginResponse>(
            '/users/login/',
            loginData,
            { skipAuth: true }
          );

          // Store tokens
          setTokens({
            access: response.access,
            refresh: response.refresh,
          });

          // Update user state
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
       * Register a new user
       * Automatically logs in the user on successful registration
       */
      register: async (userData: UserRegisterData) => {
        set({ isLoading: true, error: null });

        try {
          // Validate required fields
          if (!userData.username || !userData.email || !userData.password) {
            throw new ApiErrorClass(
              'Username, email, and password are required'
            );
          }

          // Call register API endpoint
          const response = await api.post<RegisterResponse>(
            '/auth/register/',
            userData,
            { skipAuth: true }
          );

          // Store tokens
          setTokens({
            access: response.access,
            refresh: response.refresh,
          });

          // Update user state
          set({
            user: response.user,
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
