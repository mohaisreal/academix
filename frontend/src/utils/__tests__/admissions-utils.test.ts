import { describe, it, expect } from 'vitest';
import {
  toDatetimeLocal,
  buildAdmissionDate,
  shouldHideApplyLink,
  parseStudentFields,
} from '../admissions-utils';

// ---------------------------------------------------------------------------
// toDatetimeLocal
// ---------------------------------------------------------------------------
describe('toDatetimeLocal', () => {
  it('recorta datetime ISO a YYYY-MM-DDTHH:mm para input datetime-local', () => {
    expect(toDatetimeLocal('2026-01-15T09:00:00Z')).toBe('2026-01-15T09:00');
  });

  it('devuelve cadena vacía para null', () => {
    expect(toDatetimeLocal(null)).toBe('');
  });

  it('devuelve cadena vacía para undefined', () => {
    expect(toDatetimeLocal(undefined)).toBe('');
  });

  it('maneja datetime sin sufijo de zona horaria', () => {
    expect(toDatetimeLocal('2026-02-28T23:59:00')).toBe('2026-02-28T23:59');
  });
});

// ---------------------------------------------------------------------------
// buildAdmissionDate
// ---------------------------------------------------------------------------
describe('buildAdmissionDate', () => {
  it('devuelve el valor tal cual cuando no está vacío', () => {
    expect(buildAdmissionDate('2026-01-15T09:00')).toBe('2026-01-15T09:00');
  });

  it('devuelve null para cadena vacía (campo sin completar)', () => {
    expect(buildAdmissionDate('')).toBeNull();
  });

  it('devuelve null para cadena con solo espacios', () => {
    expect(buildAdmissionDate('   ')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// shouldHideApplyLink
// ---------------------------------------------------------------------------
describe('shouldHideApplyLink', () => {
  it('oculta el enlace cuando el estudiante tiene una solicitud enviada', () => {
    const enrollments: any[] = [];
    const applications = [{ status: 'submitted' }];
    expect(shouldHideApplyLink(enrollments, applications)).toBe(true);
  });

  it('oculta el enlace cuando el estudiante tiene una solicitud admitida', () => {
    const enrollments: any[] = [];
    const applications = [{ status: 'admitted' }];
    expect(shouldHideApplyLink(enrollments, applications)).toBe(true);
  });

  it('oculta el enlace cuando el estudiante tiene matrícula activa en una carrera', () => {
    const enrollments = [{ status: 'active' }];
    const applications: any[] = [];
    expect(shouldHideApplyLink(enrollments, applications)).toBe(true);
  });

  it('muestra el enlace cuando el estudiante no tiene solicitud ni matrícula', () => {
    expect(shouldHideApplyLink([], [])).toBe(false);
  });

  it('muestra el enlace cuando la solicitud está retirada (puede volver a postularse)', () => {
    const enrollments: any[] = [];
    const applications = [{ status: 'withdrawn' }];
    expect(shouldHideApplyLink(enrollments, applications)).toBe(false);
  });

  it('muestra el enlace cuando la solicitud está vencida (puede volver a postularse)', () => {
    const enrollments: any[] = [];
    const applications = [{ status: 'expired' }];
    expect(shouldHideApplyLink(enrollments, applications)).toBe(false);
  });

  it('oculta el enlace para todos los estados activos de admisión', () => {
    const activeStatuses = [
      'submitted', 'under_review', 'provisional_admitted',
      'provisional_waitlisted', 'admitted', 'confirmed', 'completed',
    ];
    for (const s of activeStatuses) {
      expect(shouldHideApplyLink([], [{ status: s }])).toBe(true);
    }
  });
});

// ---------------------------------------------------------------------------
// parseStudentFields
// ---------------------------------------------------------------------------
describe('parseStudentFields', () => {
  it('lee email, phone y date_of_birth desde data.student anidado', () => {
    const data = {
      student: {
        email: 'test@example.com',
        phone: '+34600000000',
        date_of_birth: '2000-05-20',
        username: 'testuser',
        full_name: 'Test User',
      },
      overall_gpa: 8.5,
      periods: [],
    };
    const result = parseStudentFields(data);
    expect(result.email).toBe('test@example.com');
    expect(result.phone).toBe('+34600000000');
    expect(result.date_of_birth).toBe('2000-05-20');
    expect(result.username).toBe('testuser');
    expect(result.full_name).toBe('Test User');
  });

  it('devuelve valores null cuando faltan campos de student', () => {
    const data = { student: {}, overall_gpa: null, periods: [] };
    const result = parseStudentFields(data);
    expect(result.email).toBeNull();
    expect(result.phone).toBeNull();
    expect(result.date_of_birth).toBeNull();
  });

  it('maneja correctamente la ausencia del objeto student', () => {
    const result = parseStudentFields({});
    expect(result.email).toBeNull();
    expect(result.phone).toBeNull();
  });
});
