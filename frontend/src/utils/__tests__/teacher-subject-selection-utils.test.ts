import { describe, expect, it } from 'vitest';
import {
  buildOfferingRows,
  buildSubjectRows,
  buildPayload,
  decisionStatusBadge,
  diffSelected,
  getDecisionForOffering,
  renderOfferingCard,
} from '../teacher-subject-selection-utils';

// ---------------------------------------------------------------------------
// Fixtures — OfferingLike (new shape from SubjectOfferingSerializer)
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
// Fixtures — DecisionLike (from TeacherSubjectDecisionSerializer)
// ---------------------------------------------------------------------------
const makeDecision = (overrides: Record<string, unknown> = {}) => ({
  id: 1,
  teacher: 10,
  offering: 201,
  decision: 'pending',
  ...overrides,
});

// ---------------------------------------------------------------------------
// buildOfferingRows (new)
// ---------------------------------------------------------------------------
describe('buildOfferingRows', () => {
  it('maps offering objects to row objects with expected fields', () => {
    const input = [
      makeOffering({ id: 201, subject_name: 'Mathematics', subject_code: 'MAT101', department_name: 'Exact Sciences', max_students: 30, label: 'Group A' }),
      makeOffering({ id: 202, subject_name: 'Physics', subject_code: 'FIS202', department_name: 'Exact Sciences', max_students: 20, label: 'Group B' }),
    ];
    const rows = buildOfferingRows(input);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      id: 201,
      subjectName: 'Mathematics',
      subjectCode: 'MAT101',
      departmentName: 'Exact Sciences',
      maxStudents: 30,
      label: 'Group A',
    });
    expect(rows[1].label).toBe('Group B');
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

  it('handles missing department_name gracefully', () => {
    const input = [makeOffering({ department_name: undefined })];
    const rows = buildOfferingRows(input);
    expect(rows[0].departmentName).toBe('');
  });

  it('handles missing subject_name gracefully', () => {
    const input = [makeOffering({ subject_name: undefined })];
    const rows = buildOfferingRows(input);
    expect(rows[0].subjectName).toBe('');
  });
});

// ---------------------------------------------------------------------------
// getDecisionForOffering (new)
// ---------------------------------------------------------------------------
describe('getDecisionForOffering', () => {
  it('returns the decision status for a matching offering', () => {
    const decisions = [
      makeDecision({ offering: 201, decision: 'pending' }),
      makeDecision({ id: 2, offering: 202, decision: 'approved' }),
    ];
    expect(getDecisionForOffering(decisions, 201)).toBe('pending');
    expect(getDecisionForOffering(decisions, 202)).toBe('approved');
  });

  it('returns null when teacher has no decision for the offering', () => {
    const decisions = [makeDecision({ offering: 201 })];
    expect(getDecisionForOffering(decisions, 999)).toBeNull();
  });

  it('returns null for empty decisions list', () => {
    expect(getDecisionForOffering([], 201)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// decisionStatusBadge (new)
// ---------------------------------------------------------------------------
describe('decisionStatusBadge', () => {
  it('returns a pending badge', () => {
    const badge = decisionStatusBadge('pending');
    expect(badge).toContain('Pendiente');
    expect(badge).toContain('rounded-full');
  });

  it('returns an approved badge with green classes', () => {
    const badge = decisionStatusBadge('approved');
    expect(badge).toContain('Aprobada');
    expect(badge).toContain('green');
  });

  it('returns a rejected badge with red classes', () => {
    const badge = decisionStatusBadge('rejected');
    expect(badge).toContain('Rechazada');
    expect(badge).toContain('red');
  });

  it('falls back gracefully for unknown decision', () => {
    const badge = decisionStatusBadge('unknown');
    expect(badge).toContain('Estado desconocido');
  });
});

// ---------------------------------------------------------------------------
// renderOfferingCard (new)
// ---------------------------------------------------------------------------
describe('renderOfferingCard', () => {
  const row = {
    id: 201,
    subjectName: 'Mathematics',
    subjectCode: 'MAT101',
    departmentName: 'Exact Sciences',
    maxStudents: 30,
    label: 'Group A',
  };

  it('shows select button when no existing decision', () => {
    const html = renderOfferingCard(row, null);
    expect(html).toContain('select-offering-btn');
    expect(html).toContain('data-offering-id="201"');
    expect(html).not.toContain('Pending');
  });

  it('shows pending badge instead of select button when decision=pending', () => {
    const html = renderOfferingCard(row, 'pending');
    expect(html).not.toContain('select-offering-btn');
    expect(html).toContain('Pendiente');
  });

  it('shows approved badge when decision=approved', () => {
    const html = renderOfferingCard(row, 'approved');
    expect(html).not.toContain('select-offering-btn');
    expect(html).toContain('Aprobada');
  });

  it('shows rejected badge when decision=rejected', () => {
    const html = renderOfferingCard(row, 'rejected');
    expect(html).not.toContain('select-offering-btn');
    expect(html).toContain('Rechazada');
  });

  it('uses combined label and subject name as display name when label is present', () => {
    const html = renderOfferingCard(row, null);
    expect(html).toContain('Group A');
    expect(html).toContain('Mathematics');
  });

  it('uses subject name alone as display name when label is empty', () => {
    const noLabelRow = { ...row, label: '' };
    const html = renderOfferingCard(noLabelRow, null);
    expect(html).toContain('Mathematics');
    expect(html).not.toContain(' — ');
  });

  it('shows capacity in meta', () => {
    const html = renderOfferingCard(row, null);
    expect(html).toContain('Cupo 30');
  });
});

// ---------------------------------------------------------------------------
// buildSubjectRows (legacy — kept for backwards compatibility)
// ---------------------------------------------------------------------------
describe('buildSubjectRows (legacy)', () => {
  it('maps eligible subjects to row objects with expected fields', () => {
    const input = [
      { id: 1, subject: 101, subject_name: 'Mathematics', subject_code: 'MAT101', department_name: 'Exact Sciences', is_eligible: true },
      { id: 2, subject: 102, subject_name: 'Physics', subject_code: 'FIS202', department_name: 'Exact Sciences', is_eligible: true },
    ];
    const rows = buildSubjectRows(input);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      id: 1,
      subjectId: 101,
      subjectName: 'Mathematics',
      subjectCode: 'MAT101',
      departmentName: 'Exact Sciences',
    });
    expect(rows[1].subjectCode).toBe('FIS202');
  });

  it('returns empty array when input is empty', () => {
    expect(buildSubjectRows([])).toEqual([]);
  });

  it('handles missing department_name gracefully', () => {
    const input = [{ id: 1, subject: 101, subject_name: 'Math', subject_code: 'M1', department_name: undefined, is_eligible: true }];
    const rows = buildSubjectRows(input);
    expect(rows[0].departmentName).toBe('');
  });
});

// ---------------------------------------------------------------------------
// buildPayload (legacy)
// ---------------------------------------------------------------------------
describe('buildPayload', () => {
  it('returns decision=selected with subject_ids when ids are non-empty', () => {
    const payload = buildPayload([101, 202]);
    expect(payload).toEqual({ decision: 'selected', subject_ids: [101, 202] });
  });

  it('returns decision=none (no subject_ids) when the array is empty', () => {
    const payload = buildPayload([]);
    expect(payload).toEqual({ decision: 'none' });
  });
});

// ---------------------------------------------------------------------------
// diffSelected (legacy)
// ---------------------------------------------------------------------------
describe('diffSelected', () => {
  it('identifies newly added ids', () => {
    const diff = diffSelected([1, 2], [1, 2, 3]);
    expect(diff.added).toEqual([3]);
    expect(diff.removed).toEqual([]);
  });

  it('identifies removed ids', () => {
    const diff = diffSelected([1, 2, 3], [1]);
    expect(diff.added).toEqual([]);
    expect(diff.removed).toEqual([2, 3]);
  });

  it('handles both added and removed at once', () => {
    const diff = diffSelected([1, 2], [2, 3]);
    expect(diff.added).toEqual([3]);
    expect(diff.removed).toEqual([1]);
  });

  it('returns empty diff when sets are identical', () => {
    const diff = diffSelected([1, 2], [1, 2]);
    expect(diff.added).toEqual([]);
    expect(diff.removed).toEqual([]);
  });

  it('handles empty previous and new selections', () => {
    expect(diffSelected([], [])).toEqual({ added: [], removed: [] });
  });

  it('handles going from empty to some', () => {
    const diff = diffSelected([], [5, 6]);
    expect(diff.added).toEqual([5, 6]);
    expect(diff.removed).toEqual([]);
  });
});
