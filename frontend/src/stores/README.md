# Authentication System Documentation

This directory contains the authentication and user management implementation for the Academix frontend.

## Overview

The authentication system uses:
- **JWT tokens** for secure authentication
- **Zustand** for state management
- **Automatic token refresh** to maintain sessions
- **TypeScript** for type safety

## Architecture

### Directory Structure

```
src/
├── stores/
│   ├── useUserStore.ts        # Main user/auth store
│   └── __tests__/
│       └── useUserStore.test.ts # Store tests
├── utils/
│   ├── apiClient.ts           # API client with JWT handling
│   └── tokenManager.ts        # Token storage/retrieval
├── hooks/
│   └── useAuth.ts             # Convenient auth hook
├── types/
│   └── user.ts                # TypeScript type definitions
└── components/
    └── auth/
        ├── LoginForm.tsx      # Example login form
        └── RegisterForm.tsx   # Example register form
```

## Key Files

### 1. useUserStore.ts
The main Zustand store that manages user state and authentication.

**State:**
- `user`: Current user object or null
- `isLoading`: Loading state for async operations
- `error`: Error message from failed operations

**Actions:**
- `login(email, password)`: Authenticate user
- `register(userData)`: Register new user
- `logout()`: Clear user session
- `fetchUser(userId)`: Fetch user by ID
- `cleanError()`: Clear error state
- `setUser(user)`: Manually set user

**Selector Hooks:**
- `useUser()`: Get current user
- `useIsLoading()`: Get loading state
- `useError()`: Get error state
- `useIsAuthenticated()`: Check if user is logged in

### 2. apiClient.ts
Handles all API requests with automatic JWT token management.

**Features:**
- Automatic token injection in Authorization header
- Automatic token refresh when expired
- Error handling and parsing
- TypeScript generics for type-safe responses

**Usage:**
```typescript
import { api } from '@/utils/apiClient';

// GET request
const data = await api.get<ResponseType>('/endpoint');

// POST request
const result = await api.post<ResponseType>('/endpoint', { data });

// With options
const result = await api.get<ResponseType>('/endpoint', {
  skipAuth: true,  // Skip authentication
  skipRefresh: true // Skip token refresh
});
```

### 3. tokenManager.ts
Manages JWT token storage and validation.

**Functions:**
- `setTokens(tokens)`: Store access and refresh tokens
- `getAccessToken()`: Retrieve access token
- `getRefreshToken()`: Retrieve refresh token
- `clearTokens()`: Remove all tokens
- `isAuthenticated()`: Check if tokens exist
- `isTokenExpired(token)`: Check token expiration
- `needsTokenRefresh()`: Check if refresh needed

### 4. useAuth.ts
Convenience hook combining all auth functionality.

**Usage:**
```typescript
import { useAuth } from '@/hooks/useAuth';

function MyComponent() {
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

  // Use auth functionality
}
```

## API Endpoints

The system expects the following backend endpoints:

### Authentication
- `POST /api/auth/login/`
  - Body: `{ email: string, password: string }`
  - Response: `{ access: string, refresh: string, user: User }`

- `POST /api/auth/register/`
  - Body: `UserRegisterData`
  - Response: `{ access: string, refresh: string, user: User }`

- `POST /api/auth/logout/`
  - Headers: `Authorization: Bearer <token>`
  - Response: `204 No Content`

- `POST /api/auth/token/refresh/`
  - Body: `{ refresh: string }`
  - Response: `{ access: string }`

### User Management
- `GET /api/users/{id}/`
  - Headers: `Authorization: Bearer <token>`
  - Response: `{ user: User }`

## User Type Definition

```typescript
interface User {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  email: string;
  role: 's' | 't' | 'm' | 'a';  // student, teacher, management, admin
  phone: string;
  address: string | null;
  date_of_birth: string | null;
  profile_image: string | null;
  created_at: string;
  updated_at: string;
}
```

## Usage Examples

### 1. Login Form

```typescript
import { useAuth } from '@/hooks/useAuth';

function LoginPage() {
  const { login, isLoading, error } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await login(email, password);
      // Redirect on success
      window.location.href = '/dashboard';
    } catch (err) {
      // Error is automatically set in store
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      {error && <div>{error}</div>}
      {/* form fields */}
      <button disabled={isLoading}>
        {isLoading ? 'Logging in...' : 'Login'}
      </button>
    </form>
  );
}
```

### 2. Protected Component

```typescript
import { useAuth } from '@/hooks/useAuth';

function Dashboard() {
  const { user, isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }

  return (
    <div>
      <h1>Welcome, {user?.first_name}!</h1>
      {/* Dashboard content */}
    </div>
  );
}
```

### 3. User Registration

```typescript
import { useAuth } from '@/hooks/useAuth';

function RegisterPage() {
  const { register, isLoading, error } = useAuth();

  const handleSubmit = async (formData) => {
    try {
      await register({
        username: formData.username,
        email: formData.email,
        password: formData.password,
        first_name: formData.firstName,
        last_name: formData.lastName,
        role: 's',
      });
      window.location.href = '/dashboard';
    } catch (err) {
      // Error handling
    }
  };

  // Form implementation
}
```

### 4. Manual API Calls

```typescript
import { api } from '@/utils/apiClient';

// GET request with automatic auth
const userData = await api.get<UserResponse>('/users/123/');

// POST request
const result = await api.post<any>('/users/profile/', {
  address: '123 Main St',
  phone: '555-1234',
});

// Handle errors
try {
  await api.post('/endpoint/', data);
} catch (err) {
  if (err instanceof ApiErrorClass) {
    console.error(err.message, err.status, err.errors);
  }
}
```

## Token Flow

1. **Login/Register**: User provides credentials
2. **Token Receipt**: Backend returns access + refresh tokens
3. **Token Storage**: Tokens stored in localStorage
4. **API Requests**: Access token added to Authorization header
5. **Token Expiry**: When token expires (detected before request)
6. **Token Refresh**: Refresh token used to get new access token
7. **Request Retry**: Original request retried with new token
8. **Logout**: All tokens cleared from storage

## Error Handling

All API errors are wrapped in `ApiErrorClass`:

```typescript
class ApiErrorClass extends Error {
  status?: number;           // HTTP status code
  errors?: Record<string, string[]>; // Field-specific errors
  message: string;           // Error message
}
```

Example error handling:

```typescript
try {
  await login(email, password);
} catch (err) {
  if (err instanceof ApiErrorClass) {
    if (err.status === 401) {
      // Handle unauthorized
    }
    if (err.errors) {
      // Display field-specific errors
    }
  }
}
```

## Testing

Run tests with:

```bash
# Run all tests
npm test

# Run with UI
npm run test:ui

# Run with coverage
npm run test:coverage
```

Test files are located in `__tests__` directories next to the files they test.

## Configuration

API URL is configured in `/src/config/api.ts`:

```typescript
const API_URL = import.meta.env.BACKEND_API_URL || 'http://localhost:8000/api';
```

Set `BACKEND_API_URL` environment variable to override.

## Security Considerations

1. **Tokens in localStorage**: Tokens are stored in localStorage (susceptible to XSS). Consider httpOnly cookies for production.
2. **Token Refresh**: Implemented with 60-second buffer to prevent mid-request expiration
3. **Auto-logout**: On 401 errors, tokens are automatically cleared
4. **HTTPS**: Always use HTTPS in production
5. **Password Validation**: Implement strong password requirements on backend

## Future Improvements

- [ ] Add remember me functionality
- [ ] Implement refresh token rotation
- [ ] Add biometric authentication support
- [ ] Add OAuth/social login
- [ ] Move to httpOnly cookies for better security
- [ ] Add rate limiting on frontend
- [ ] Implement password reset flow
- [ ] Add email verification
- [ ] Add two-factor authentication
