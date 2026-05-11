/**
 * Ejemplos de uso de autenticación
 * Este fichero muestra distintas formas de usar el sistema de autenticación.
 * Copia estos patrones en tus propios componentes según sea necesario.
 */
import { useAuth } from '@/hooks/useAuth';
import { api, ApiErrorClass } from '@/utils/apiClient';
import { useEffect, useState } from 'react';
import type { User } from '@/types/user';

// ============================================================================
// Ejemplo 1: componente simple de inicio de sesión
// ============================================================================

export function SimpleLoginExample() {
  const { login, isLoading, error } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(username, password);
      // Redirige tras iniciar sesión correctamente
      window.location.href = '/dashboard';
    } catch (err) {
      // El error lo gestiona automáticamente el almacén de estado
      console.error('Falló el inicio de sesión:', err);
    }
  };

  return (
    <form onSubmit={handleLogin}>
      {error && <div className="error">{error}</div>}
      <input
        type="text"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        placeholder="Nombre de usuario"
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        placeholder="Contraseña"
      />
      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Iniciando sesión...' : 'Iniciar sesión'}
      </button>
    </form>
  );
}

// ============================================================================
// Ejemplo 2: ruta/componente protegido
// ============================================================================

export function ProtectedDashboard() {
  const { user, isAuthenticated, logout } = useAuth();

  // Redirige si no hay autenticación
  useEffect(() => {
    if (!isAuthenticated) {
      window.location.href = '/login';
    }
  }, [isAuthenticated]);

  if (!isAuthenticated) {
    return <div>Cargando...</div>;
  }

  return (
    <div>
      <h1>¡Bienvenido, {user?.first_name}!</h1>
      <p>Correo electrónico: {user?.email}</p>
      <p>Role: {user?.role}</p>
      <button onClick={logout}>Cerrar sesión</button>
    </div>
  );
}

// ============================================================================
// Ejemplo 3: perfil de usuario con actualizaciones
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
      // Refresca los datos del usuario
      await fetchUser(user.id);
      alert('Perfil actualizado correctamente');
    } catch (err) {
      if (err instanceof ApiErrorClass) {
        setUpdateError(err.message);
      }
    } finally {
      setIsUpdating(false);
    }
  };

  const handleUpdateTeléfono = async () => {
    const newTeléfono = prompt('Enter new phone number:');
    if (newTeléfono) {
      await updateProfile({ phone: newTeléfono });
    }
  };

  return (
    <div>
      <h2>Perfil de usuario</h2>
      {updateError && <div className="error">{updateError}</div>}

      <div>
        <strong>Name:</strong> {user?.first_name} {user?.last_name}
      </div>
      <div>
        <strong>Correo electrónico:</strong> {user?.email}
      </div>
      <div>
        <strong>Teléfono:</strong> {user?.phone || 'Not set'}
      </div>

      <button onClick={handleUpdateTeléfono} disabled={isUpdating}>
        {isUpdating ? 'Actualizando...' : 'Actualizar teléfono'}
      </button>
    </div>
  );
}

// ============================================================================
// Ejemplo 4: formulario de registro
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
      setLocalError('Las contraseñas no coinciden');
      return;
    }

    try {
      const { confirmPassword, ...registerData } = formData;
      await register({ ...registerData, password2: confirmPassword });
      window.location.href = '/dashboard';
    } catch (err) {
      console.error('No se pudo completar el registro:', err);
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
        placeholder="Nombre"
        required
      />
      <input
        name="last_name"
        value={formData.last_name}
        onChange={handleChange}
        placeholder="Apellidos"
        required
      />
      <input
        name="username"
        value={formData.username}
        onChange={handleChange}
        placeholder="Nombre de usuario"
        required
      />
      <input
        name="email"
        type="email"
        value={formData.email}
        onChange={handleChange}
        placeholder="Correo electrónico"
        required
      />
      <input
        name="password"
        type="password"
        value={formData.password}
        onChange={handleChange}
        placeholder="Contraseña"
        required
      />
      <input
        name="confirmPassword"
        type="password"
        value={formData.confirmPassword}
        onChange={handleChange}
        placeholder="Confirmar contraseña"
        required
      />

      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Creando cuenta...' : 'Registrarse'}
      </button>
    </form>
  );
}

// ============================================================================
// Ejemplo 5: uso directo del cliente de API
// ============================================================================

export function DirectAPIExample() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);

    try {
      // Petición GET con autenticación automática
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
        {loading ? 'Cargando...' : 'Obtener usuarios'}
      </button>

      {error && <div className="error">{error}</div>}

      <ul>
        {users.map(user => (
          <li key={user.id}>
            {user.first_name} {user.last_name} - {user.email}
            <button onClick={() => deleteUser(user.id)}>Eliminar</button>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ============================================================================
// Ejemplo 6: renderizado condicional según el estado de autenticación
// ============================================================================

export function ConditionalRenderingExample() {
  const { user, isAuthenticated, logout } = useAuth();

  return (
    <div>
      {isAuthenticated ? (
        <div>
          <p>Sesión iniciada como: {user?.email}</p>
          <button onClick={logout}>Cerrar sesión</button>
        </div>
      ) : (
        <div>
          <p>Please log in to continue</p>
          <a href="/login">Iniciar sesión</a>
          <a href="/register">Registrarse</a>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Ejemplo 7: control de acceso basado en roles
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
      <h1>Panel</h1>

      {/* Disponible para todos los usuarios autenticados */
}
      <section>
        <h2>Mi perfil</h2>
        <p>Name: {user?.first_name} {user?.last_name}</p>
      </section>

      {/* Sección solo para profesores */
}
      {isTeacher && (
        <section>
          <h2>Panel de profesor</h2>
          <p>Manage your classes and students</p>
        </section>
      )}

      {/* Sección solo para administración */
}
      {isAdmin && (
        <section>
          <h2>Admin Panel</h2>
          <p>System administration</p>
        </section>
      )}

      {/* Sección solo para estudiantes */
}
      {isStudent && (
        <section>
          <h2>Mis cursos</h2>
          <p>View your enrolled courses</p>
        </section>
      )}
    </div>
  );
}

// ============================================================================
// Ejemplo 8: patrones de gestión de errores
// ============================================================================

export function ErrorHandlingExample() {
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleLoginWithDetailedErrors = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      await login(username, password);
      window.location.href = '/dashboard';
    } catch (err) {
      if (err instanceof ApiErrorClass) {
        // Gestiona códigos de estado concretos
        switch (err.status) {
          case 401:
            alert('Credenciales inválidas. Inténtalo de nuevo.');
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

        // Gestiona errores específicos de campo
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
        type="text"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
      />
      <input
        type="password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <button type="submit">Iniciar sesión</button>
    </form>
  );
}
