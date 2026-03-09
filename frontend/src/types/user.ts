/**
 * User type definitions matching the Django backend User model
 */

export type UserRole = 's' | 't' | 'm' | 'a';

export interface User {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: UserRole;
  phone: string;
  address: string | null;
  date_of_birth: string | null;
  profile_image: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserRegisterData {
  username: string;
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  role?: UserRole;
  phone?: string;
  address?: string;
  date_of_birth?: string;
}

export interface UserLoginData {
  email: string;
  password: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface RegisterResponse {
  user: User;
  access: string;
  refresh: string;
}

export interface UserResponse {
  user: User;
}

export interface ApiError {
  message: string;
  errors?: Record<string, string[]>;
  status?: number;
}
