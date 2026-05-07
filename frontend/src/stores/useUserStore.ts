/**
 * Almacén de estado de usuario para autenticación y gestión del estado
 * Usa Zustand con persistencia del estado entre sesiones
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
} from '@/types/user';

interface UserState {
  // Estado
  user: User | null;
  isLoading: boolean;
  error: string | null;

  // Acciones
  fetchUser: (userId: number) => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
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

          // Si no tiene autorización, limpia todo
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
              : 'No se ha podido iniciar sesión. Revisa tus credenciales.';

          set({
            error: errorMessage,
            isLoading: false,
            user: null,
          });

          // Limpia cualquier token existente si falla el inicio de sesión
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
              : 'No se ha podido completar el registro. Inténtalo de nuevo.';

          set({
            error: errorMessage,
            isLoading: false,
            user: null,
          });

          // Limpia cualquier token si falla el registro
          clearTokens();

          throw err;
        }
      },

      /**
       * Cierra la sesión del usuario
       * Limpia el estado de usuario y los tokens JWT
       */
      logout: () => {
        // Limpia los tokens del almacenamiento
        clearTokens();

        // Limpia el estado de usuario
        set({
          user: null,
          isLoading: false,
          error: null,
        });

        // Opcional: llama al endpoint de cierre de sesión para invalidar el token en el servidor
        // Es una petición de lanzar y olvidar; no esperamos a que termine
        try {
          api.post('/users/logout/', {}).catch(() => {
            // Ignora errores en el endpoint de cierre de sesión
          });
        } catch {
          // Ignora errores
        }
      },

      /**
       * Limpia el mensaje de error
       */
      cleanError: () => {
        set({ error: null });
      },

      /**
       * Establece datos de usuario manualmente (útil para actualizaciones)
       */
      setUser: (user: User | null) => {
        set({ user });
      },
    }),
    {
      name: 'user-storage',
      // Persiste solo los datos de usuario, no los estados de carga/error
      partialize: (state) => ({ user: state.user }),
    }
  )
);

/**
 * Hooks selectores para partes concretas del estado
 * Ayudan a evitar rerenderizados innecesarios
 */
export const useUser = () => useUserStore((state) => state.user);
export const useIsLoading = () => useUserStore((state) => state.isLoading);
export const useError = () => useUserStore((state) => state.error);
export const useIsAuthenticated = () => useUserStore((state) => !!state.user && isTokenValid());
