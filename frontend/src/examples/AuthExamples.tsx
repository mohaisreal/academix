/**
 * Authentication Usage Examples
 *
 * This file demonstrates various ways to use the authentication system.
 * Copy these patterns into your own components as needed.
 */

import { useAuth } from '@/hooks/useAuth';
import { api, ApiErrorClass } from '@/utils/apiClient';
import { useEffect, useState } from 'react';
import type { User } from '@/types/user';

// ============================================================================
// Example 1: Simple Login Component
// ============================================================================

export function SimpleLoginExample() {
  const { login, isLoading, error } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(email, password);
      // Redirect after successful login
      window.location.href = '/dashboard';
    } catch (err) {
      // Error is automatically handled by the store
      console.error('Login failed:', err);
    }
  };

  return (
    <form onSubmit={handleLogin}>
      {error && <div className="error">{error}</div>}
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="Email"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Password"
      />
      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Logging in...' : 'Login'}
      </button>
    </form>
  );
}

// ============================================================================
// Example 2: Protected Route/Component
// ============================================================================

export function ProtectedDashboard() {
  const { user, isAuthenticated, logout } = useAuth();

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      window.location.href = '/login';
    }
  }, [isAuthenticated]);

  if (!isAuthenticated) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <h1>Welcome, {user?.first_name}!</h1>
      <p>Email: {user?.email}</p>
      <p>Role: {user?.role}</p>
      <button onClick={logout}>Logout</button>
    </div>
  );
}

// ============================================================================
// Example 3: User Profile with Updates
// ============================================================================

export function UserProfileExample() {
  const { user, fetchUser } = useAuth();
  const [isUpdating, setIsUpdating] = useState(false);
  const [updateError, setUpdateError] = useState<string | null>(null);

  const updateProfile = async (updates: Partial<User>) => {
    if (!user) return;

    setIsUpdating(true);
    setUpdateError(null);

    try {
      await api.patch(`/users/${user.id}/`, updates);
      // Refresh user data
      await fetchUser(user.id);
      alert('Profile updated successfully!');
    } catch (err) {
      if (err instanceof ApiErrorClass) {
        setUpdateError(err.message);
      }
    } finally {
      setIsUpdating(false);
    }
  };

  const handleUpdatePhone = async () => {
    const newPhone = prompt('Enter new phone number:');
    if (newPhone) {
      await updateProfile({ phone: newPhone });
    }
  };

  return (
    <div>
      <h2>User Profile</h2>
      {updateError && <div className="error">{updateError}</div>}

      <div>
        <strong>Name:</strong> {user?.first_name} {user?.last_name}
      </div>
      <div>
        <strong>Email:</strong> {user?.email}
      </div>
      <div>
        <strong>Phone:</strong> {user?.phone || 'Not set'}
      </div>

      <button onClick={handleUpdatePhone} disabled={isUpdating}>
        {isUpdating ? 'Updating...' : 'Update Phone'}
      </button>
    </div>
  );
}

// ============================================================================
// Example 4: Registration Form
// ============================================================================

export function RegistrationExample() {
  const { register, isLoading, error, cleanError } = useAuth();
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    first_name: '',
    last_name: '',
  });
  const [localError, setLocalError] = useState('');

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    setLocalError('');
    cleanError();
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (formData.password !== formData.confirmPassword) {
      setLocalError('Passwords do not match');
      return;
    }

    try {
      const { confirmPassword, ...registerData } = formData;
      await register(registerData);
      window.location.href = '/dashboard';
    } catch (err) {
      console.error('Registration failed:', err);
    }
  };

  const displayError = localError || error;

  return (
    <form onSubmit={handleSubmit}>
      {displayError && <div className="error">{displayError}</div>}

      <input
        name="first_name"
        value={formData.first_name}
        onChange={handleChange}
        placeholder="First Name"
        required
      />
      <input
        name="last_name"
        value={formData.last_name}
        onChange={handleChange}
        placeholder="Last Name"
        required
      />
      <input
        name="username"
        value={formData.username}
        onChange={handleChange}
        placeholder="Username"
        required
      />
      <input
        name="email"
        type="email"
        value={formData.email}
        onChange={handleChange}
        placeholder="Email"
        required
      />
      <input
        name="password"
        type="password"
        value={formData.password}
        onChange={handleChange}
        placeholder="Password"
        required
      />
      <input
        name="confirmPassword"
        type="password"
        value={formData.confirmPassword}
        onChange={handleChange}
        placeholder="Confirm Password"
        required
      />

      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Creating account...' : 'Register'}
      </button>
    </form>
  );
}

// ============================================================================
// Example 5: Using API Client Directly
// ============================================================================

export function DirectAPIExample() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);

    try {
      // GET request with automatic authentication
      const response = await api.get<{ users: User[] }>('/users/');
      setUsers(response.users);
    } catch (err) {
      if (err instanceof ApiErrorClass) {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  const createUser = async (userData: any) => {
    try {
      const response = await api.post<{ user: User }>('/users/', userData);
      setUsers([...users, response.user]);
    } catch (err) {
      if (err instanceof ApiErrorClass) {
        alert(`Error: ${err.message}`);
      }
    }
  };

  const deleteUser = async (userId: number) => {
    try {
      await api.delete(`/users/${userId}/`);
      setUsers(users.filter(u => u.id !== userId));
    } catch (err) {
      if (err instanceof ApiErrorClass) {
        alert(`Error: ${err.message}`);
      }
    }
  };

  return (
    <div>
      <button onClick={fetchUsers} disabled={loading}>
        {loading ? 'Loading...' : 'Fetch Users'}
      </button>

      {error && <div className="error">{error}</div>}

      <ul>
        {users.map(user => (
          <li key={user.id}>
            {user.first_name} {user.last_name} - {user.email}
            <button onClick={() => deleteUser(user.id)}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ============================================================================
// Example 6: Conditional Rendering Based on Auth State
// ============================================================================

export function ConditionalRenderingExample() {
  const { user, isAuthenticated, logout } = useAuth();

  return (
    <div>
      {isAuthenticated ? (
        <div>
          <p>Logged in as: {user?.email}</p>
          <button onClick={logout}>Logout</button>
        </div>
      ) : (
        <div>
          <p>Please log in to continue</p>
          <a href="/login">Login</a>
          <a href="/register">Register</a>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Example 7: Role-Based Access Control
// ============================================================================

export function RoleBasedExample() {
  const { user, isAuthenticated } = useAuth();

  const isTeacher = user?.role === 't';
  const isAdmin = user?.role === 'a';
  const isStudent = user?.role === 's';

  if (!isAuthenticated) {
    return <div>Please log in</div>;
  }

  return (
    <div>
      <h1>Dashboard</h1>

      {/* Available to all authenticated users */}
      <section>
        <h2>My Profile</h2>
        <p>Name: {user?.first_name} {user?.last_name}</p>
      </section>

      {/* Teacher-only section */}
      {isTeacher && (
        <section>
          <h2>Teacher Dashboard</h2>
          <p>Manage your classes and students</p>
        </section>
      )}

      {/* Admin-only section */}
      {isAdmin && (
        <section>
          <h2>Admin Panel</h2>
          <p>System administration</p>
        </section>
      )}

      {/* Student-only section */}
      {isStudent && (
        <section>
          <h2>My Courses</h2>
          <p>View your enrolled courses</p>
        </section>
      )}
    </div>
  );
}

// ============================================================================
// Example 8: Error Handling Patterns
// ============================================================================

export function ErrorHandlingExample() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleLoginWithDetailedErrors = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      await login(email, password);
      window.location.href = '/dashboard';
    } catch (err) {
      if (err instanceof ApiErrorClass) {
        // Handle specific status codes
        switch (err.status) {
          case 401:
            alert('Invalid credentials. Please try again.');
            break;
          case 429:
            alert('Too many login attempts. Please try again later.');
            break;
          case 500:
            alert('Server error. Please try again later.');
            break;
          default:
            alert(err.message);
        }

        // Handle field-specific errors
        if (err.errors) {
          Object.entries(err.errors).forEach(([field, messages]) => {
            console.error(`${field}: ${messages.join(', ')}`);
          });
        }
      }
    }
  };

  return (
    <form onSubmit={handleLoginWithDetailedErrors}>
      <input
        type="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <button type="submit">Login</button>
    </form>
  );
}
