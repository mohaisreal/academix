/**
 * Definiciones de tipos de usuario alineadas con el modelo User del backend Django
 */
export type UserRole = 's' | 't' | 'm' | 'a';

export interface User {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: UserRole;
  dni?: string | null;
  email_verified?: boolean;
  identity_verification_status?: 'unsubmitted' | 'pending' | 'approved' | 'rejected';
  identity_verification_notes?: string | null;
  is_active?: boolean;
  phone: string;
  address: string | null;
  date_of_birth: string | null;
  profile_image: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserRegisterData {
  email: string;
  password: string;
  password2?: string;
  first_name: string;
  last_name: string;
  role?: UserRole;
  dni?: string;
  phone?: string;
  address?: string;
  date_of_birth?: string;
}

export interface UserLoginData {
  username: string;
  password: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface LoginResponse {
  user: User;
  tokens: AuthTokens;
  message?: string;
}

export interface RegisterResponse {
  detail: string;
}

export interface UserResponse {
  user: User;
}

export interface ApiError {
  message: string;
  errors?: Record<string, string[]>;
  status?: number;
}
