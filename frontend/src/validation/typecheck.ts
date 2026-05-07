/**
 * Fichero de validación de tipos para asegurar que todos los tipos compilen correctamente
 * Este fichero es solo para validación y no debe importarse en producción
 */
import type { User, UserRole, UserLoginData, UserRegisterData, AuthTokens, LoginResponse, ApiError } from '@/types/user';
import { useUserStore, useUser, useIsLoading, useError, useIsAuthenticated } from '@/stores/useUserStore';
import { api, ApiErrorClass } from '@/utils/apiClient';
import { setTokens, getAccessToken, getRefreshToken, clearTokens, isAuthenticated, isTokenExpired, needsTokenRefresh } from '@/utils/tokenManager';
import { useAuth } from '@/hooks/useAuth';

// Pruebas de validación de tipos
const validateTypes = () => {
  // Tipo de usuario
  const user: User = {
    id: 1,
    username: 'test',
    first_name: 'Test',
    last_name: 'User',
    email: 'test@test.com',
    role: 's' as UserRole,
    phone: '123',
    address: null,
    date_of_birth: null,
    profile_image: null,
    created_at: '2024-01-01',
    updated_at: '2024-01-01',
  };

  // Tokens de autenticación
  const tokens: AuthTokens = {
    access: 'token',
    refresh: 'token',
  };

  // Login data
  const loginData: UserLoginData = {
    username: 'test',
    password: 'password',
  };

  // Register data
  const registerData: UserRegisterData = {
    email: 'test@test.com',
    password: 'password',
    password2: 'password',
    first_name: 'Test',
    last_name: 'User',
  };

  // Error de API
  const error: ApiError = {
    message: 'Error',
    errors: {},
    status: 400,
  };

  console.log('All types validated successfully');
};

// Store validation
const validateStore = async () => {
  const store = useUserStore.getState();

  // Propiedades de estado
  const user: User | null = store.user;
  const isLoading: boolean = store.isLoading;
  const error: string | null = store.error;

  // Action methods
  await store.login('username', 'password');
  await store.register({
    email: 'test@test.com',
    password: 'password',
    password2: 'password',
    first_name: 'Test',
    last_name: 'User',
  });
  await store.fetchUser(1);
  store.logout();
  store.cleanError();
  store.setUser(null);

  // Selector hooks
  const hookUser = useUser();
  const hookIsLoading = useIsLoading();
  const hookError = useError();
  const hookIsAuthenticated = useIsAuthenticated();

  console.log('Store validation successful');
};

// API Client validation
const validateApiClient = async () => {
  // GET
  const getResult = await api.get<User>('/users/1/');

  // POST
  const postResult = await api.post<LoginResponse>('/users/login/', {
    username: 'test',
    password: 'password',
  });

  // PUT
  const putResult = await api.put<User>('/users/1/', {});

  // PATCH
  const patchResult = await api.patch<User>('/users/1/', {});

  // DELETE
  await api.delete('/users/1/');

  // ApiErrorClass
  const error = new ApiErrorClass('Error message', 400, {});
  const message: string = error.message;
  const status: number | undefined = error.status;
  const errors: Record<string, string[]> | undefined = error.errors;

  console.log('API client validation successful');
};

// Token manager validation
const validateTokenManager = () => {
  // Set tokens
  setTokens({ access: 'token', refresh: 'token' });

  // Get tokens
  const accessToken: string | null = getAccessToken();
  const refreshToken: string | null = getRefreshToken();

  // Limpia tokens
  clearTokens();

  // Check authentication
  const authenticated: boolean = isAuthenticated();

  // Check expiration
  const expired: boolean = isTokenExpired('token');
  const needsRefresh: boolean = needsTokenRefresh();

  console.log('Token manager validation successful');
};

// Validación del hook de autenticación
const validateAuthHook = async () => {
  const {
    user,
    isLoading,
    error,
    isAuthenticated,
    login,
    logout,
    register,
    fetchUser,
    cleanError,
  } = useAuth();

  // Type checks
  const userType: User | null = user;
  const loadingType: boolean = isLoading;
  const errorType: string | null = error;
  const authType: boolean = isAuthenticated;

  // Method calls
  await login('username', 'password');
  await register({
    email: 'test@test.com',
    password: 'password',
    password2: 'password',
    first_name: 'Test',
    last_name: 'User',
  });
  await fetchUser(1);
  logout();
  cleanError();

  console.log('Validación del hook de autenticación successful');
};

export { validateTypes, validateStore, validateApiClient, validateTokenManager, validateAuthHook };
