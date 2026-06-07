import { describe, expect, it } from 'vitest';
import {
  DEFAULT_TOTAL_SPOTS,
  getCareerSubjectIds,
  parseValidTotalSpots,
  resolveCareerTotalSpots,
} from '../careers-form-utils';

describe('resolveCareerTotalSpots', () => {
  it('devuelve el valor entero cuando total_spots es válido', () => {
    expect(resolveCareerTotalSpots(250)).toBe(250);
  });

  it('usa fallback en datos legacy inválidos', () => {
    expect(resolveCareerTotalSpots(undefined)).toBe(DEFAULT_TOTAL_SPOTS);
    expect(resolveCareerTotalSpots(-1)).toBe(DEFAULT_TOTAL_SPOTS);
    expect(resolveCareerTotalSpots('2.5')).toBe(DEFAULT_TOTAL_SPOTS);
  });
});

describe('parseValidTotalSpots', () => {
  it('parsea enteros no negativos', () => {
    expect(parseValidTotalSpots('0')).toBe(0);
    expect(parseValidTotalSpots('120')).toBe(120);
  });

  it('rechaza vacío, negativos, decimales y no numéricos', () => {
    expect(parseValidTotalSpots('')).toBeNull();
    expect(parseValidTotalSpots('  ')).toBeNull();
    expect(parseValidTotalSpots('-1')).toBeNull();
    expect(parseValidTotalSpots('1.5')).toBeNull();
    expect(parseValidTotalSpots('abc')).toBeNull();
  });
});

describe('getCareerSubjectIds', () => {
  it('prefiere subject_ids y cae a subjects para payloads legacy', () => {
    expect(getCareerSubjectIds({ subject_ids: [1, '2'] })).toEqual(new Set(['1', '2']));
    expect(getCareerSubjectIds({ subjects: [3, '4'] })).toEqual(new Set(['3', '4']));
  });
});
