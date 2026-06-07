import { describe, expect, it } from 'vitest';
import {
  getEnrollmentClassAvailability,
  getEnrollmentClassAction,
  getScheduleSummaryLabel,
} from '../enrollment-class-selection-utils';

type EnrollmentClassLike = Parameters<typeof getEnrollmentClassAction>[0]['cls'];

describe('enrollment-class-selection-utils', () => {
  it('marks class unavailable when schedule_available is false', () => {
    const cls = {
      schedule_available: false,
      schedule_unavailable_reason: 'schedule_unavailable',
      schedules: [],
    };

    expect(getEnrollmentClassAvailability(cls)).toEqual({
      available: false,
      reason: 'schedule_unavailable',
    });
  });

  it('derives availability from assignment schedules when schedule_available is missing', () => {
    const cls = {
      schedules: [{ assignment_id: 1, source: 'generated' }],
    };

    expect(getEnrollmentClassAvailability(cls)).toEqual({
      available: true,
      reason: null,
    });
  });

  it('returns unavailable action for missing canonical schedule', () => {
    const cls = {
      schedule_available: false,
      schedule_unavailable_reason: 'schedule_unavailable',
      schedules: [],
    };

    expect(getEnrollmentClassAction({ cls, isEnrolled: false, isFull: false, isCompleted: false })).toEqual({
      key: 'unavailable',
      label: 'Sin horario disponible',
      disabled: true,
    });
  });

  it('returns grace action when convocation eligibility is extraordinary-grace', () => {
    const cls: EnrollmentClassLike = {
      schedule_available: true,
      convocation_eligibility: 'extraordinary-grace',
      schedules: [{ assignment_id: 1, source: 'generated' }],
    };

    expect(getEnrollmentClassAction({ cls, isEnrolled: false, isFull: false, isCompleted: false })).toEqual({
      key: 'enroll-grace',
      label: 'Caso excepcional',
      disabled: false,
    });
  });

  it('returns blocked action when convocation eligibility is blocked', () => {
    const cls: EnrollmentClassLike = {
      schedule_available: true,
      convocation_eligibility: 'blocked',
      convocation_block_reason: 'limit_reached',
      schedules: [{ assignment_id: 1, source: 'generated' }],
    };

    expect(getEnrollmentClassAction({ cls, isEnrolled: false, isFull: false, isCompleted: false })).toEqual({
      key: 'blocked',
      label: 'Límite de convocatorias alcanzado',
      disabled: true,
    });
  });

  it('formats schedule label from backend schedules', () => {
    const schedules = [{ day_name: 'Lunes', start_time: '08:00', end_time: '10:00' }];
    expect(getScheduleSummaryLabel(schedules)).toBe('Lunes 08:00–10:00');
  });
});
