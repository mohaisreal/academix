// Utilidades puras para el flujo de revisión de decisiones de materias en gestión.
// Sin acceso al DOM — se puede importar en Vitest sin jsdom.

// ---------------------------------------------------------------------------
// Tipos — forma de TeacherSubjectDecision (nuevo: FK a offering, no a subject)
// ---------------------------------------------------------------------------

export type DecisionLike = {
  id: number;
  teacher: number;
  teacher_name?: string;
  /** FK a SubjectOffering (reemplaza el FK anterior a subject) */
  offering?: number;
  offering_label?: string;
  subject_name?: string;
  subject_code?: string;
  department_name?: string;
  period?: number;
  decision?: string;
  stale?: boolean;
  decided_by?: number | null;
  reviewed_by_name?: string | null;
  [key: string]: unknown;
};

export type DecisionRow = {
  id: number;
  teacherId: number;
  teacherName: string;
  offeringId: number;
  offeringLabel: string;
  subjectName: string;
  subjectCode: string;
  departmentName: string;
  decision: string;
  stale: boolean;
  decidedByName: string;
};

// ---------------------------------------------------------------------------
// Tipos — forma de SubjectOffering (para el panel de lista de ofertas)
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
  isActive: boolean;
  label: string;
};

const DECISION_LABELS: Record<string, string> = {
  pending: 'Pendiente',
  approved: 'Aprobada',
  rejected: 'Rechazada',
  none: 'Sin decisión',
};

const DECISION_CLASSES: Record<string, string> = {
  pending: 'bg-muted text-foreground',
  approved: 'bg-green-500/10 text-green-300',
  rejected: 'bg-red-500/10 text-red-300',
  none: 'bg-muted text-muted-foreground',
};

/**
 * Construye una cadena HTML de badge para un estado de decisión.
 * Cuando stale=true (la oferta está inactiva), agrega un indicador amarillo "Desactualizada".
 */
export function decisionBadge(decision: string, stale: boolean): string {
  const label = DECISION_LABELS[decision] ?? 'Estado desconocido';
  const classes = DECISION_CLASSES[decision] ?? 'bg-muted text-foreground';
  const baseBadge = `<span class="inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${classes}">${label}</span>`;
  if (!stale) return baseBadge;
  const staleBadge = `<span class="inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium bg-yellow-500/10 text-yellow-300">Desactualizada</span>`;
  return `${baseBadge} ${staleBadge}`;
}

/**
 * Mapea los objetos de decisión devueltos por GET /decisions/ en objetos de fila planos
 * usados por el renderizador de revisión en gestión.
 * Las decisiones ahora referencian una oferta (no un subject directamente).
 */
export function buildDecisionRows(decisions: DecisionLike[]): DecisionRow[] {
  return decisions.map((d) => ({
    id: d.id,
    teacherId: d.teacher,
    teacherName: (d.teacher_name as string | undefined) ?? '',
    offeringId: (d.offering as number | undefined) ?? 0,
    offeringLabel: (d.offering_label as string | undefined) ?? '',
    subjectName: (d.subject_name as string | undefined) ?? '',
    subjectCode: (d.subject_code as string | undefined) ?? '',
    departmentName: (d.department_name as string | undefined) ?? '',
    decision: (d.decision as string | undefined) ?? 'pending',
    stale: Boolean(d.stale),
    decidedByName: (d.reviewed_by_name as string | null | undefined) ?? '',
  }));
}

/**
 * Mapea los objetos SubjectOffering devueltos por GET /offerings/ en objetos de fila planos
 * usados por el renderizador de la lista de ofertas.
 */
export function buildOfferingRows(offerings: OfferingLike[]): OfferingRow[] {
  return offerings.map((o) => ({
    id: o.id,
    subjectName: o.subject_name ?? '',
    subjectCode: o.subject_code ?? '',
    departmentName: o.department_name ?? '',
    maxStudents: o.max_students ?? 0,
    isActive: Boolean(o.is_active),
    label: o.label ?? '',
  }));
}

// ---------------------------------------------------------------------------
// Utilidades heredadas — se conservan por compatibilidad retroactiva y se limpiarán
// ---------------------------------------------------------------------------

/** @deprecated Ya no existe el concepto de elegibilidad — se conserva para evitar errores de importación. */
export type EligibilityLike = {
  id: number;
  teacher?: number;
  subject: number;
  subject_name?: string;
  subject_code?: string;
  department_name?: string;
  is_eligible?: boolean;
  [key: string]: unknown;
};

/** @deprecated Ya no existe el concepto de elegibilidad — se conserva para evitar errores de importación. */
export type EligibilityRow = {
  id: number;
  subjectId: number;
  subjectName: string;
  subjectCode: string;
  departmentName: string;
  isEligible: boolean;
};

/** @deprecated Devuelve un arreglo vacío — se eliminó el concepto de elegibilidad. */
export function buildEligibilityRows(_eligibilities: EligibilityLike[]): EligibilityRow[] {
  return [];
}

/** @deprecated Devuelve checked=false siempre — se eliminó el concepto de elegibilidad. */
export function eligibilityRowState(_row: EligibilityLike): { checked: boolean } {
  return { checked: false };
}
