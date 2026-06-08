import { describe, expect, it } from 'vitest';
import { resolveActivePeriodLabel, type ActivePeriodLike } from '../period-display';

describe('resolveActivePeriodLabel', () => {
  it('prefers an explicit active period entry', () => {
    const periods: ActivePeriodLike[] = [
      { id: 1, name: '2025-A', is_active: false },
      { id: 2, name: '2026-A', is_active: true },
    ];

    expect(resolveActivePeriodLabel(periods)).toBe('2026-A');
  });

  it('falls back to the first period when no active flag exists', () => {
    const periods: ActivePeriodLike[] = [{ id: 3, name: '2024-B' }];

    expect(resolveActivePeriodLabel(periods)).toBe('2024-B');
  });

  it('returns a generic label when it cannot infer a name', () => {
    expect(resolveActivePeriodLabel([])).toBe('Periodo activo');
  });
});
