/**
 * Funciones puras de utilidad para lógica de interfaz relacionada con admisiones.
 * Extraídas para facilitar pruebas: sin efectos secundarios ni acceso al DOM.
 */
const ACTIVE_ADMISSION_STATUSES = new Set([
  'submitted',
  'under_review',
  'provisional_admitted',
  'provisional_waitlisted',
  'admitted',
  'confirmed',
  'completed',
]);

/**
 * Convierte una fecha ISO al formato esperado por <input type="datetime-local">.
 * Devuelve una cadena vacía para null/undefined.
 */
export function toDatetimeLocal(iso: string | null | undefined): string {
  if (!iso) return '';
  return iso.slice(0, 16);
}

/**
 * Convierte el valor de un input datetime-local a un valor listo para la API.
 * Las cadenas vacías o solo con espacios pasan a null (campo no establecido).
 */
export function buildAdmissionDate(value: string): string | null {
  return value.trim() ? value : null;
}

/**
 * Devuelve true si debe ocultarse el enlace lateral "Solicitar plaza en una titulación".
 * Se oculta cuando el estudiante tiene una admisión activa en curso O una matrícula activa.
 */
export function shouldHideApplyLink(
  enrollments: Array<{ status: string }>,
  applications: Array<{ status: string }>,
): boolean {
  if (enrollments.some(e => e.status === 'active' || e.status === 'completed')) {
    return true;
  }
  if (applications.some(a => ACTIVE_ADMISSION_STATUSES.has(a.status))) {
    return true;
  }
  return false;
}

/**
 * Lee campos del perfil del estudiante desde la forma anidada de la respuesta API:
 * { student: { email, phone, date_of_birth, username, full_name }, ... }
 */
export function parseStudentFields(data: Record<string, any>): {
  email: string | null;
  phone: string | null;
  date_of_birth: string | null;
  username: string | null;
  full_name: string | null;
} {
  const s = data?.student ?? {};
  return {
    email: s.email ?? null,
    phone: s.phone ?? null,
    date_of_birth: s.date_of_birth ?? null,
    username: s.username ?? null,
    full_name: s.full_name ?? null,
  };
}
