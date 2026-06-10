// Utilidades puras para el flujo de selección de materias del docente.
// Sin acceso al DOM — se puede importar en Vitest sin jsdom.

// ---------------------------------------------------------------------------
// Tipos — forma de SubjectOffering (API nueva, POST /offerings/<id>/select/)
// ---------------------------------------------------------------------------

export type OfferingLike = {
  id: number;
  subject?: number;
  subject_name?: string;
  subject_code?: string;
  department?: number;
  department_name?: string;
  period?: number;
  max_students?: number;
  is_active?: boolean;
  label?: string;
  [key: string]: unknown;
};

export type OfferingRow = {
  id: number;
  subjectName: string;
  subjectCode: string;
  departmentName: string;
  maxStudents: number;
  label: string;
};

// ---------------------------------------------------------------------------
// Tipos — forma de TeacherSubjectDecision (para buscar decisiones existentes)
// ---------------------------------------------------------------------------

export type DecisionLike = {
  id: number;
  offering: number;
  decision: string;
  [key: string]: unknown;
};

// ---------------------------------------------------------------------------
// Tipos — forma heredada de elegibilidad (se conserva por compatibilidad retroactiva)
// ---------------------------------------------------------------------------

/** @deprecated Usa OfferingLike — las ofertas reemplazaron a las elegibilidades. */
export type EligibilityLike = {
  id: number;
  subject: number;
  subject_name?: string;
  subject_code?: string;
  department_name?: string;
  is_eligible?: boolean;
  [key: string]: unknown;
};

/** @deprecated Usa OfferingRow */
export type SubjectRow = {
  id: number;
  subjectId: number;
  subjectName: string;
  subjectCode: string;
  departmentName: string;
};

export type SelectionPayload =
  | { decision: 'selected'; subject_ids: number[] }
  | { decision: 'none' };

export type SelectionDiff = {
  added: number[];
  removed: number[];
};

// ---------------------------------------------------------------------------
// Utilidades de ofertas (nuevo)
// ---------------------------------------------------------------------------

/**
 * Mapea los objetos SubjectOffering devueltos por GET /offerings/?active=true
 * en objetos de fila planos usados por el renderizador de tarjetas de selección.
 */
export function buildOfferingRows(offerings: OfferingLike[]): OfferingRow[] {
  return offerings.map((o) => ({
    id: o.id,
    subjectName: o.subject_name ?? '',
    subjectCode: o.subject_code ?? '',
    departmentName: o.department_name ?? '',
    maxStudents: o.max_students ?? 0,
    label: o.label ?? '',
  }));
}

/**
 * Dada una lista de decisiones existentes del docente y un id de oferta, devuelve
 * el texto de estado de decisión ('pending' | 'approved' | 'rejected') o null
 * si el docente no tiene una decisión para esa oferta.
 */
export function getDecisionForOffering(
  decisions: DecisionLike[],
  offeringId: number,
): string | null {
  const match = decisions.find((d) => d.offering === offeringId);
  return match ? match.decision : null;
}

/**
 * Renderiza una tarjeta individual de oferta como una cadena HTML para inyección con innerHTML.
 * Muestra la etiqueta de la oferta, la materia y el cupo. Si el docente ya
 * tiene una decisión para esta oferta, muestra un badge de estado en lugar del
 * botón de selección.
 *
 * @param row - La fila de oferta a renderizar
 * @param existingDecision - El estado de decisión actual del docente, o null
 */
export function renderOfferingCard(
  row: OfferingRow,
  existingDecision: string | null,
): string {
  const displayName = row.label
    ? `${row.label} — ${row.subjectName}`
    : row.subjectName;
  const meta = [row.subjectCode, row.departmentName, row.maxStudents ? `Cupo ${row.maxStudents}` : '']
    .filter(Boolean)
    .join(' · ');

  const actionHtml = existingDecision
    ? decisionStatusBadge(existingDecision)
    : `<button
        type="button"
        class="select-offering-btn shrink-0 rounded-md border border-primary/40 bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary transition hover:bg-primary/20 disabled:opacity-50"
        data-offering-id="${row.id}"
      >Seleccionar</button>`;

  return `
<div class="flex items-start gap-3 rounded-xl border border-border bg-card p-4 transition-colors hover:bg-muted/40" data-offering-id="${row.id}">
  <div class="min-w-0 flex-1">
    <p class="text-sm font-medium text-foreground leading-snug">${escapeHtml(displayName)}</p>
    <p class="text-xs text-muted-foreground mt-0.5">${escapeHtml(meta)}</p>
  </div>
  <div class="shrink-0">
    ${actionHtml}
  </div>
</div>`.trim();
}

/**
 * Devuelve un HTML inline de badge de estado para una decisión existente.
 */
export function decisionStatusBadge(decision: string): string {
  const config: Record<string, { label: string; classes: string }> = {
    pending: { label: 'Pendiente', classes: 'bg-muted text-foreground' },
    approved: { label: 'Aprobada', classes: 'bg-green-500/10 text-green-300' },
    rejected: { label: 'Rechazada', classes: 'bg-red-500/10 text-red-300' },
  };
  const { label, classes } = config[decision] ?? { label: 'Estado desconocido', classes: 'bg-muted text-foreground' };
  return `<span class="inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${classes}">${label}</span>`;
}

// ---------------------------------------------------------------------------
// Utilidades heredadas (se conservan — aún las usan pruebas antiguas y el flujo de envío)
// ---------------------------------------------------------------------------

/**
 * @deprecated Usa buildOfferingRows — se conserva solo por compatibilidad retroactiva.
 * Mapea objetos de elegibilidad en objetos de fila planos.
 */
export function buildSubjectRows(eligibilities: EligibilityLike[]): SubjectRow[] {
  return eligibilities.map((e) => ({
    id: e.id,
    subjectId: e.subject,
    subjectName: e.subject_name ?? '',
    subjectCode: e.subject_code ?? '',
    departmentName: (e.department_name as string | undefined) ?? '',
  }));
}

/**
 * Construye el payload POST para el endpoint heredado de envío.
 * Selección vacía → decision: 'none'; cualquier selección → decision: 'selected' + ids.
 */
export function buildPayload(selectedSubjectIds: number[]): SelectionPayload {
  if (selectedSubjectIds.length === 0) {
    return { decision: 'none' };
  }
  return { decision: 'selected', subject_ids: selectedSubjectIds };
}

/**
 * Calcula el diff de dos selecciones para mostrar qué se agregó y qué se quitó.
 */
export function diffSelected(
  previous: number[],
  current: number[],
): SelectionDiff {
  const prevSet = new Set(previous);
  const currSet = new Set(current);
  return {
    added: current.filter((id) => !prevSet.has(id)),
    removed: previous.filter((id) => !currSet.has(id)),
  };
}

/**
 * @deprecated Usa renderOfferingCard — se conserva solo por compatibilidad retroactiva.
 * Renderiza una fila de materia individual como una cadena HTML de tarjeta para inyección con innerHTML.
 */
export function renderSubjectCard(row: SubjectRow): string {
  return `
<label class="flex cursor-pointer items-start gap-3 rounded-xl border border-border bg-card p-4 transition-colors hover:bg-muted/40 has-[:checked]:border-primary/60 has-[:checked]:bg-primary/5">
  <input
    type="checkbox"
    class="mt-0.5 h-4 w-4 shrink-0 accent-primary"
    name="subject_ids"
    value="${row.subjectId}"
  />
  <div class="min-w-0 flex-1">
    <p class="text-sm font-medium text-foreground leading-snug">${row.subjectName}</p>
    <p class="text-xs text-muted-foreground mt-0.5">${row.subjectCode}${row.departmentName ? ` · ${row.departmentName}` : ''}</p>
  </div>
</label>`.trim();
}

// ---------------------------------------------------------------------------
// Utilidades internas
// ---------------------------------------------------------------------------

function escapeHtml(value: unknown): string {
  const el = { textContent: String(value ?? ''), innerHTML: '' };
  // Escapeo puro de cadenas — sin DOM, seguro en Node/Vitest
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
