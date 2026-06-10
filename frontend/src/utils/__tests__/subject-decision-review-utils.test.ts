import { describe, expect, it } from 'vitest';
import {
  buildDecisionRows,
  buildOfferingRows,
  decisionBadge,
} from '../subject-decision-review-utils';

// ---------------------------------------------------------------------------
// Fixtures — DecisionLike (new offering-based shape)
// ---------------------------------------------------------------------------
const makeDecision = (overrides: Record<string, unknown> = {}) => ({
  id: 1,
  teacher: 10,
  teacher_name: 'Ana García',
  offering: 201,
  offering_label: 'Group A',
  subject_name: 'Mathematics',
  subject_code: 'MAT101',
  department_name: 'Exact Sciences',
  period: 5,
  decision: 'pending',
  stale: false,
  decided_by: null,
  reviewed_by_name: null,
  notes: '',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
});

// ---------------------------------------------------------------------------
// Fixtures — OfferingLike
// ---------------------------------------------------------------------------
const makeOffering = (overrides: Record<string, unknown> = {}) => ({
  id: 201,
  subject: 101,
  subject_name: 'Mathematics',
  subject_code: 'MAT101',
  department: 3,
  department_name: 'Exact Sciences',
  period: 5,
  max_students: 30,
  is_active: true,
  label: 'Group A',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  ...overrides,
});

// ---------------------------------------------------------------------------
// decisionBadge
// ---------------------------------------------------------------------------
describe('decisionBadge', () => {
  it('returns a pending badge for decision=pending without stale', () => {
    const badge = decisionBadge('pending', false);
    expect(badge).toContain('Pendiente');
    expect(badge).not.toContain('Desactualizada');
  });

  it('returns an approved badge for decision=approved without stale', () => {
    const badge = decisionBadge('approved', false);
    expect(badge).toContain('Aprobada');
    expect(badge).not.toContain('Desactualizada');
  });

  it('returns a rejected badge for decision=rejected without stale', () => {
    const badge = decisionBadge('rejected', false);
    expect(badge).toContain('Rechazada');
    expect(badge).not.toContain('Desactualizada');
  });

  it('appends yellow Stale marker when stale=true', () => {
    const badge = decisionBadge('approved', true);
    expect(badge).toContain('Aprobada');
    expect(badge).toContain('Desactualizada');
    expect(badge).toContain('yellow');
  });

  it('stale=true also works on pending decisions', () => {
    const badge = decisionBadge('pending', true);
    expect(badge).toContain('Pendiente');
    expect(badge).toContain('Desactualizada');
  });

  it('falls back gracefully for unknown decision states', () => {
    const badge = decisionBadge('unknown', false);
    expect(typeof badge).toBe('string');
    expect(badge.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// buildDecisionRows — offering-based shape
// ---------------------------------------------------------------------------
describe('buildDecisionRows', () => {
  it('maps decision objects to row objects with offering fields', () => {
    const input = [
      makeDecision({
        id: 1,
        teacher: 10,
        teacher_name: 'Ana García',
        offering: 201,
        offering_label: 'Group A',
        subject_name: 'Mathematics',
        subject_code: 'MAT101',
        decision: 'pending',
        stale: false,
      }),
      makeDecision({
        id: 2,
        teacher: 11,
        teacher_name: 'Luis Torres',
        offering: 202,
        offering_label: 'Group B',
        subject_name: 'Physics',
        subject_code: 'FIS202',
        decision: 'approved',
        stale: true,
      }),
    ];
    const rows = buildDecisionRows(input);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      id: 1,
      teacherId: 10,
      teacherName: 'Ana García',
      offeringId: 201,
      offeringLabel: 'Group A',
      subjectName: 'Mathematics',
      subjectCode: 'MAT101',
      decision: 'pending',
      stale: false,
    });
    expect(rows[1].teacherName).toBe('Luis Torres');
    expect(rows[1].offeringId).toBe(202);
    expect(rows[1].offeringLabel).toBe('Group B');
    expect(rows[1].stale).toBe(true);
  });

  it('returns empty array when input is empty', () => {
    expect(buildDecisionRows([])).toEqual([]);
  });

  it('handles missing teacher_name gracefully', () => {
    const input = [makeDecision({ teacher_name: undefined })];
    const rows = buildDecisionRows(input);
    expect(rows[0].teacherName).toBe('');
  });

  it('handles missing offering_label gracefully', () => {
    const input = [makeDecision({ offering_label: undefined })];
    const rows = buildDecisionRows(input);
    expect(rows[0].offeringLabel).toBe('');
  });

  it('handles missing department_name gracefully', () => {
    const input = [makeDecision({ department_name: undefined })];
    const rows = buildDecisionRows(input);
    expect(rows[0].departmentName).toBe('');
  });

  it('uses reviewed_by_name field (not decided_by_name)', () => {
    const input = [makeDecision({ reviewed_by_name: 'Admin User' })];
    const rows = buildDecisionRows(input);
    expect(rows[0].decidedByName).toBe('Admin User');
  });

  it('stale defaults to false when stale field is absent', () => {
    const input = [makeDecision({ stale: undefined })];
    const rows = buildDecisionRows(input);
    expect(rows[0].stale).toBe(false);
  });

  it('decision defaults to pending when decision field is absent', () => {
    const input = [makeDecision({ decision: undefined })];
    const rows = buildDecisionRows(input);
    expect(rows[0].decision).toBe('pending');
  });
});

// ---------------------------------------------------------------------------
// buildOfferingRows
// ---------------------------------------------------------------------------
describe('buildOfferingRows', () => {
  it('maps offering objects to row objects with expected fields', () => {
    const input = [
      makeOffering({ id: 201, subject_name: 'Mathematics', subject_code: 'MAT101', is_active: true, label: 'Group A', max_students: 30 }),
      makeOffering({ id: 202, subject_name: 'Physics', subject_code: 'FIS202', is_active: false, label: 'Group B', max_students: 20 }),
    ];
    const rows = buildOfferingRows(input);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      id: 201,
      subjectName: 'Mathematics',
      subjectCode: 'MAT101',
      isActive: true,
      label: 'Group A',
      maxStudents: 30,
    });
    expect(rows[1].isActive).toBe(false);
    expect(rows[1].maxStudents).toBe(20);
  });

  it('returns empty array when input is empty', () => {
    expect(buildOfferingRows([])).toEqual([]);
  });

  it('handles missing label gracefully', () => {
    const input = [makeOffering({ label: undefined })];
    const rows = buildOfferingRows(input);
    expect(rows[0].label).toBe('');
  });

  it('handles missing max_students gracefully', () => {
    const input = [makeOffering({ max_students: undefined })];
    const rows = buildOfferingRows(input);
    expect(rows[0].maxStudents).toBe(0);
  });

  it('is_active defaults to false when field is absent', () => {
    const input = [makeOffering({ is_active: undefined })];
    const rows = buildOfferingRows(input);
    expect(rows[0].isActive).toBe(false);
  });
});
