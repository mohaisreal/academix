import { describe, expect, it } from 'vitest';
import {
  createEmptyChargeRow,
  normalizeExtraChargeRows,
  serializeExtraChargeRows,
  validateExtraChargeRows,
} from '../system-enrollment-charges-utils';

describe('normalizeExtraChargeRows', () => {
  it('normaliza datos incompletos con defaults seguros', () => {
    const result = normalizeExtraChargeRows([
      { label: '  Carné universitario  ', amount: '12.00' },
      { amount: '5.50', active: false },
      null,
    ]);

    expect(result).toHaveLength(2);
    expect(result[0].label).toBe('Carné universitario');
    expect(result[0].amount).toBe('12.00');
    expect(result[0].active).toBe(true);
    expect(result[1].label).toBe('');
    expect(result[1].amount).toBe('5.50');
    expect(result[1].active).toBe(false);
  });
});

describe('createEmptyChargeRow', () => {
  it('crea una fila editable vacía y activa por defecto', () => {
    const row = createEmptyChargeRow();
    expect(row.label).toBe('');
    expect(row.amount).toBe('0.00');
    expect(row.active).toBe(true);
    expect(row.clientId.length).toBeGreaterThan(0);
  });
});

describe('validateExtraChargeRows', () => {
  it('reporta errores por label vacío y monto inválido', () => {
    const result = validateExtraChargeRows([
      { clientId: 'r1', label: ' ', amount: '-1', active: true },
      { clientId: 'r2', label: 'Seguro', amount: 'abc', active: true },
    ]);

    expect(result[0].errors.label).toBeDefined();
    expect(result[0].errors.amount).toBeDefined();
    expect(result[1].errors.amount).toBeDefined();
  });
});

describe('serializeExtraChargeRows', () => {
  it('serializa shape exacto sin metadatos de cliente', () => {
    const result = serializeExtraChargeRows([
      {
        clientId: 'r1',
        label: 'Carné',
        amount: '12.00',
        active: true,
        errors: { amount: 'x' },
      },
    ]);

    expect(result).toEqual([{ label: 'Carné', amount: '12.00', active: true }]);
  });
});
