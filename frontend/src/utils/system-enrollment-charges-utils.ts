export type EnrollmentExtraCharge = {
  label: string;
  amount: string;
  active?: boolean;
};

export type EditableChargeRow = EnrollmentExtraCharge & {
  clientId: string;
  errors?: {
    label?: string;
    amount?: string;
  };
};

function buildClientId() {
  return `charge-${Math.random().toString(36).slice(2, 10)}`;
}

export function createEmptyChargeRow(): EditableChargeRow {
  return {
    clientId: buildClientId(),
    label: '',
    amount: '0.00',
    active: true,
    errors: {},
  };
}

export function normalizeExtraChargeRows(value: unknown): EditableChargeRow[] {
  if (!Array.isArray(value)) return [];

  return value
    .filter((item) => item && typeof item === 'object')
    .map((item) => {
      const record = item as Record<string, unknown>;
      return {
        clientId: buildClientId(),
        label: String(record.label ?? '').trim(),
        amount: String(record.amount ?? '0.00').trim(),
        active: record.active === undefined ? true : Boolean(record.active),
        errors: {},
      };
    });
}

function isValidAmount(amount: string): boolean {
  if (!/^\d+(\.\d{1,2})?$/.test(amount)) return false;
  return Number(amount) >= 0;
}

export function validateExtraChargeRows(rows: EditableChargeRow[]): EditableChargeRow[] {
  return rows.map((row) => {
    const nextErrors: EditableChargeRow['errors'] = {};
    const label = row.label.trim();
    const amount = row.amount.trim();

    if (!label) nextErrors.label = 'El nombre es obligatorio.';
    if (!isValidAmount(amount)) nextErrors.amount = 'Monto inválido. Debe ser >= 0 con hasta 2 decimales.';

    return {
      ...row,
      label,
      amount,
      errors: nextErrors,
    };
  });
}

export function serializeExtraChargeRows(rows: EditableChargeRow[]): EnrollmentExtraCharge[] {
  return rows.map(({ label, amount, active }) => ({
    label: label.trim(),
    amount: amount.trim(),
    active: Boolean(active),
  }));
}
