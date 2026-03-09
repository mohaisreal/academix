/**
 * Tests for useUserStore
 *
 * Note: To run these tests, you'll need to install testing dependencies:
 * npm install -D vitest @testing-library/react @testing-library/jest-dom happy-dom
 *
 * Add to package.json scripts:
 * "test": "vitest",
 * "test:ui": "vitest --ui",
 * "test:coverage": "vitest --coverage"
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useUserStore } from '../useUserStore';
import * as apiClient from '@/utils/apiClient';
import * as tokenManager from '@/utils/tokenManager';

// Mock the API client and token manager
vi.mock('@/utils/apiClient', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
  ApiErrorClass: class ApiErrorClass extends Error {
    status?: number;
    errors?: Record<string, string[]>;
    constructor(message: string, status?: number, errors?: Record<string, string[]>) {
      super(message);
      this.status = status;
      this.errors = errors;
    }
  },
}));

vi.mock('@/utils/tokenManager', () => ({
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
  getAccessToken: vi.fn(),
  getRefreshToken: vi.fn(),
}));

describe('useUserStore', () => {
  const mockUser = {
    id: 1,
    username: 'testuser',
    first_name: 'Test',
    last_name: 'User',
    email: 'test@example.com',
    role: 's' as const,
    phone: '1234567890',
    address: '123 Test St',
    date_of_birth: '2000-01-01',
    profile_image: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  const mockTokens = {
    access: 'mock-access-token',
    refresh: 'mock-refresh-token',
  };

  beforeEach(() => {
    // Reset store state before each test
    const { logout } = useUserStore.getState();
    logout();

    // Clear all mocks
    vi.clearAllMocks();
  });

  describe('Initial State', () => {
    it('should have correct initial state', () => {
      const state = useUserStore.getState();

      expect(state.user).toBeNull();
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('login', () => {
    it('should successfully login a user', async () => {
      const mockResponse = {
        user: mockUser,
        access: mockTokens.access,
        refresh: mockTokens.refresh,
      };

      vi.mocked(apiClient.api.post).mockResolvedValueOnce(mockResponse);

      const { login } = useUserStore.getState();
      await login('test@example.com', 'password123');

      const state = useUserStore.getState();

      expect(state.user).toEqual(mockUser);
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
      expect(tokenManager.setTokens).toHaveBeenCalledWith(mockTokens);
    });

    it('should handle login errors', async () => {
      const mockError = new apiClient.ApiErrorClass('Invalid credentials', 401);
      vi.mocked(apiClient.api.post).mockRejectedValueOnce(mockError);

      const { login } = useUserStore.getState();

      await expect(login('test@example.com', 'wrongpassword')).rejects.toThrow();

      const state = useUserStore.getState();

      expect(state.user).toBeNull();
      expect(state.isLoading).toBe(false);
      expect(state.error).toBe('Invalid credentials');
      expect(tokenManager.clearTokens).toHaveBeenCalled();
    });

    it('should validate required fields', async () => {
      const { login } = useUserStore.getState();

      await expect(login('', '')).rejects.toThrow();

      const state = useUserStore.getState();

      expect(state.error).toBe('Email and password are required');
      expect(apiClient.api.post).not.toHaveBeenCalled();
    });
  });

  describe('register', () => {
    it('should successfully register a user', async () => {
      const mockResponse = {
        user: mockUser,
        access: mockTokens.access,
        refresh: mockTokens.refresh,
      };

      vi.mocked(apiClient.api.post).mockResolvedValueOnce(mockResponse);

      const registerData = {
        username: 'testuser',
        email: 'test@example.com',
        password: 'password123',
        first_name: 'Test',
        last_name: 'User',
      };

      const { register } = useUserStore.getState();
      await register(registerData);

      const state = useUserStore.getState();

      expect(state.user).toEqual(mockUser);
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
      expect(tokenManager.setTokens).toHaveBeenCalledWith(mockTokens);
    });

    it('should handle registration errors', async () => {
      const mockError = new apiClient.ApiErrorClass('Username already exists', 400);
      vi.mocked(apiClient.api.post).mockRejectedValueOnce(mockError);

      const registerData = {
        username: 'existinguser',
        email: 'test@example.com',
        password: 'password123',
        first_name: 'Test',
        last_name: 'User',
      };

      const { register } = useUserStore.getState();

      await expect(register(registerData)).rejects.toThrow();

      const state = useUserStore.getState();

      expect(state.user).toBeNull();
      expect(state.error).toBe('Username already exists');
      expect(tokenManager.clearTokens).toHaveBeenCalled();
    });

    it('should validate required fields', async () => {
      const invalidData = {
        username: '',
        email: '',
        password: '',
        first_name: '',
        last_name: '',
      };

      const { register } = useUserStore.getState();

      await expect(register(invalidData)).rejects.toThrow();

      const state = useUserStore.getState();

      expect(state.error).toBe('Username, email, and password are required');
    });
  });

  describe('fetchUser', () => {
    it('should successfully fetch user data', async () => {
      const mockResponse = { user: mockUser };
      vi.mocked(apiClient.api.get).mockResolvedValueOnce(mockResponse);

      const { fetchUser } = useUserStore.getState();
      await fetchUser(1);

      const state = useUserStore.getState();

      expect(state.user).toEqual(mockUser);
      expect(state.isLoading).toBe(false);
      expect(state.error).toBeNull();
    });

    it('should handle fetch errors', async () => {
      const mockError = new apiClient.ApiErrorClass('User not found', 404);
      vi.mocked(apiClient.api.get).mockRejectedValueOnce(mockError);

      const { fetchUser } = useUserStore.getState();

      await expect(fetchUser(999)).rejects.toThrow();

      const state = useUserStore.getState();

      expect(state.user).toBeNull();
      expect(state.error).toBe('User not found');
    });

    it('should clear tokens on 401 error', async () => {
      const mockError = new apiClient.ApiErrorClass('Unauthorized', 401);
      vi.mocked(apiClient.api.get).mockRejectedValueOnce(mockError);

      const { fetchUser } = useUserStore.getState();

      await expect(fetchUser(1)).rejects.toThrow();

      expect(tokenManager.clearTokens).toHaveBeenCalled();
    });
  });

  describe('logout', () => {
    it('should clear user state and tokens', () => {
      // Set up some user state
      const state = useUserStore.getState();
      state.setUser(mockUser);

      // Logout
      state.logout();

      const newState = useUserStore.getState();

      expect(newState.user).toBeNull();
      expect(newState.error).toBeNull();
      expect(tokenManager.clearTokens).toHaveBeenCalled();
    });
  });

  describe('cleanError', () => {
    it('should clear error state', () => {
      const state = useUserStore.getState();

      // Manually set an error (normally done by failed API calls)
      useUserStore.setState({ error: 'Test error' });

      expect(useUserStore.getState().error).toBe('Test error');

      state.cleanError();

      expect(useUserStore.getState().error).toBeNull();
    });
  });

  describe('setUser', () => {
    it('should update user state', () => {
      const { setUser } = useUserStore.getState();

      setUser(mockUser);

      const state = useUserStore.getState();

      expect(state.user).toEqual(mockUser);
    });

    it('should allow setting user to null', () => {
      const { setUser } = useUserStore.getState();

      setUser(mockUser);
      expect(useUserStore.getState().user).toEqual(mockUser);

      setUser(null);
      expect(useUserStore.getState().user).toBeNull();
    });
  });
});
