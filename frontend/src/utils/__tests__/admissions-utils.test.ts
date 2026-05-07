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
  it('slices ISO datetime to YYYY-MM-DDTHH:mm for datetime-local input', () => {
    expect(toDatetimeLocal('2026-01-15T09:00:00Z')).toBe('2026-01-15T09:00');
  });

  it('returns empty string for null', () => {
    expect(toDatetimeLocal(null)).toBe('');
  });

  it('returns empty string for undefined', () => {
    expect(toDatetimeLocal(undefined)).toBe('');
  });

  it('handles datetime without timezone suffix', () => {
    expect(toDatetimeLocal('2026-02-28T23:59:00')).toBe('2026-02-28T23:59');
  });
});

// ---------------------------------------------------------------------------
// buildAdmissionDate
// ---------------------------------------------------------------------------
describe('buildAdmissionDate', () => {
  it('returns the value as-is when non-empty', () => {
    expect(buildAdmissionDate('2026-01-15T09:00')).toBe('2026-01-15T09:00');
  });

  it('returns null for empty string (field not set)', () => {
    expect(buildAdmissionDate('')).toBeNull();
  });

  it('returns null for whitespace-only string', () => {
    expect(buildAdmissionDate('   ')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// shouldHideApplyLink
// ---------------------------------------------------------------------------
describe('shouldHideApplyLink', () => {
  it('hides link when student has submitted application', () => {
    const enrollments: any[] = [];
    const applications = [{ status: 'submitted' }];
    expect(shouldHideApplyLink(enrollments, applications)).toBe(true);
  });

  it('hides link when student has admitted application', () => {
    const enrollments: any[] = [];
    const applications = [{ status: 'admitted' }];
    expect(shouldHideApplyLink(enrollments, applications)).toBe(true);
  });

  it('hides link when student has active career enrollment', () => {
    const enrollments = [{ status: 'active' }];
    const applications: any[] = [];
    expect(shouldHideApplyLink(enrollments, applications)).toBe(true);
  });

  it('shows link when student has no application and no enrollment', () => {
    expect(shouldHideApplyLink([], [])).toBe(false);
  });

  it('shows link when application is withdrawn (can re-apply)', () => {
    const enrollments: any[] = [];
    const applications = [{ status: 'withdrawn' }];
    expect(shouldHideApplyLink(enrollments, applications)).toBe(false);
  });

  it('shows link when application is expired (can re-apply)', () => {
    const enrollments: any[] = [];
    const applications = [{ status: 'expired' }];
    expect(shouldHideApplyLink(enrollments, applications)).toBe(false);
  });

  it('hides link for all active admission statuses', () => {
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
  it('reads email, phone, date_of_birth from nested data.student', () => {
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

  it('returns null values when student fields are missing', () => {
    const data = { student: {}, overall_gpa: null, periods: [] };
    const result = parseStudentFields(data);
    expect(result.email).toBeNull();
    expect(result.phone).toBeNull();
    expect(result.date_of_birth).toBeNull();
  });

  it('handles missing student object gracefully', () => {
    const result = parseStudentFields({});
    expect(result.email).toBeNull();
    expect(result.phone).toBeNull();
  });
});
