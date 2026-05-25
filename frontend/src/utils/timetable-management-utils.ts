type TimetableRunLike = { id: number; period?: { id: number; name?: string | null } | null; period_name?: string | null; status?: string | null; assignments_count?: number | null };
type TimetableClassLike = { id: number; period?: { id: number } | null };
type TimetableViolationLike = { severity?: string | null; penalty?: number | null };

export type TimetableTareaFormValues = { clsId: string; teacherId: string; classroomId: string; timeslotId: string; activityType: string; source: string; status: string };
export type TimeslotBreakRange = { startTime: string; endTime: string };
export type TimeslotBatchFormValues = { period: string; dayOfWeek: string; startTime: string; endTime: string; intervalMinutes: string; breakRanges: TimeslotBreakRange[] };
export type TimeslotPayload = { period: number; day_of_week: number; start_time: string; end_time: string };
export type TimetableApiError = Error & { status?: number; payload?: any };
export type TimetableViolationSummary = { total: number; hard: number; soft: number; penalty: number };
export type AssignmentGridRow = { id: number; cls?: number; subject_name?: string; subject_code?: string; classroom_name?: string; teacher_name?: string; career_id?: number; career_name?: string; timeslot_day_name?: string; timeslot_start_time?: string; timeslot_end_time?: string };
export type TimetableGridBlock = { id: number; day: number; hour: string; label: string; careerId: number | null; careerName: string | null };
export type ConstraintFormValues = { kind: string; scope: string; period: string; teacher: string; classroom: string; career: string; dayOfWeek: string; startTime: string; endTime: string; isActive: boolean };

export type BulkBreakRange = { start: string; end: string };
export type SlotPayload = { period: number; day_of_week: number; start_time: string; end_time: string };
export type BulkSlotResult = { toCreate: SlotPayload[]; skipped: Array<{ day_of_week: number; start_time: string; end_time: string; reason: 'break' | 'duplicate' }> };

function toOptionalNumber(value: string) { const normalized = value.trim(); return normalized ? Number(normalized) : null; }
function assertTime(value: string) { if (!/^\d{2}:\d{2}$/.test(value)) throw new Error('Usá el formato HH:MM.'); }
function timeToMinutes(value: string) { assertTime(value); const [h, m] = value.split(':').map(Number); if (h < 0 || h > 23 || m < 0 || m > 59) throw new Error('Usá el formato HH:MM.'); return h * 60 + m; }
function minutesToTime(value: number) { const h = Math.floor(value / 60); const m = value % 60; return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`; }
function rangesOverlap(start: number, end: number, breakStart: number, breakEnd: number) { return start < breakEnd && end > breakStart; }

export function parseTimeslotBreakRanges(value: string): TimeslotBreakRange[] {
  const normalized = value.trim(); if (!normalized) return [];
  return normalized.split(/[\n,;]+/).map((item) => item.trim()).filter(Boolean).map((item) => {
    const match = item.match(/^(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})$/);
    if (!match) throw new Error('Usá HH:MM-HH:MM para cada descanso.');
    const startTime = match[1]; const endTime = match[2];
    if (timeToMinutes(startTime) >= timeToMinutes(endTime)) throw new Error('La hora fin del descanso debe ser posterior al inicio.');
    return { startTime, endTime };
  });
}

export function buildTimeslotBatch(values: TimeslotBatchFormValues): TimeslotPayload[] {
  const period = Number(values.period); const dayOfWeek = Number(values.dayOfWeek); const intervalMinutes = Number(values.intervalMinutes);
  const startMinutes = timeToMinutes(values.startTime); const endMinutes = timeToMinutes(values.endTime);
  if (!Number.isInteger(period) || period <= 0) throw new Error('Seleccioná un período válido antes de crear franjas.');
  if (!Number.isInteger(dayOfWeek) || dayOfWeek < 0 || dayOfWeek > 6) throw new Error('Seleccioná un día válido.');
  if (!Number.isFinite(intervalMinutes) || intervalMinutes <= 0) throw new Error('La duración debe ser mayor que 0.');
  if (startMinutes >= endMinutes) throw new Error('La hora de fin debe ser posterior a la hora de inicio.');
  const breaks = values.breakRanges.map((range) => ({ start: timeToMinutes(range.startTime), end: timeToMinutes(range.endTime) }));
  const slots: TimeslotPayload[] = [];
  for (let cursor = startMinutes; cursor + intervalMinutes <= endMinutes; cursor += intervalMinutes) {
    const next = cursor + intervalMinutes;
    if (breaks.some((r) => rangesOverlap(cursor, next, r.start, r.end))) continue;
    slots.push({ period, day_of_week: dayOfWeek, start_time: minutesToTime(cursor), end_time: minutesToTime(next) });
  }
  return slots;
}

export function requireSelectedPeriod(periodValue: string, errorMessage = 'Seleccioná un período antes de continuar.') {
  const period = Number(periodValue);
  if (!Number.isInteger(period) || period <= 0) throw new Error(errorMessage);
  return period;
}

export function buildDraftRunPayload(period: string | number) {
  return { period: requireSelectedPeriod(String(period), 'Seleccioná un período para crear la ejecución.'), status: 'draft', metadata: {} };
}

export function buildManualTimeslotPayload(input: { period: string | number; dayOfWeek: string | number; startTime: string; endTime: string }): TimeslotPayload {
  const periodId = requireSelectedPeriod(String(input.period), 'Seleccioná un período para crear franjas.');
  const dayOfWeek = Number(input.dayOfWeek);
  if (!Number.isInteger(dayOfWeek) || dayOfWeek < 0 || dayOfWeek > 6) throw new Error('Seleccioná un día válido.');
  if (timeToMinutes(input.startTime) >= timeToMinutes(input.endTime)) throw new Error('La hora de fin debe ser posterior a la hora de inicio.');
  return { period: periodId, day_of_week: dayOfWeek, start_time: input.startTime, end_time: input.endTime };
}

export function classifyTimetableActionError(error: unknown, action: 'generate' | 'publish' | 'draft' | 'timeslot') {
  const typedError = error as TimetableApiError;
  const status = typedError?.status;
  const payload = typedError?.payload;
  const detail = String(payload?.detail || typedError?.message || '').toLowerCase();
  const preconditionErrors = payload?.metadata?.generator?.precondition_errors;
  const classPreparationErrors = payload?.metadata?.generator?.class_preparation_errors;
  const unresolvedTeachers = payload?.metadata?.generator?.unresolved_teachers;
  const categories = Array.isArray(preconditionErrors) ? preconditionErrors : [];
  const preparationCategories = Array.isArray(classPreparationErrors) ? classPreparationErrors : [];
  const fieldError = payload && typeof payload === 'object' && Object.keys(payload).some((key) => ['period', 'day_of_week', 'start_time', 'end_time', 'non_field_errors'].includes(key));

  if (status === 400 && action === 'generate' && (detail.includes('failed') || payload?.status === 'failed')) {
    if (categories.includes('missing_classes')) {
      return 'No se pudo generar: faltan clases activas para el período seleccionado.';
    }
    if (categories.includes('missing_teachers')) {
      return 'No se pudo generar: hay clases sin docente asignado.';
    }
    if (categories.includes('missing_classrooms')) {
      return 'No se pudo generar: hay clases sin aula asignada.';
    }
    if (categories.includes('missing_time_slots')) {
      return 'No se pudo generar: faltan franjas horarias para el período seleccionado.';
    }
    if (preparationCategories.includes('class_preparation_insufficient_subjects')) {
      return 'No se pudo generar: faltan materias activas para preparar clases del período.';
    }
    if (preparationCategories.includes('class_preparation_insufficient_classrooms')) {
      return 'No se pudo generar: faltan aulas disponibles para preparar clases del período.';
    }
    if (Array.isArray(unresolvedTeachers) && unresolvedTeachers.length > 0) {
      return `No se pudo generar: hay docentes sin resolver en ${unresolvedTeachers.length} clase(s).`;
    }
    if (detail.includes('faltan')) {
      return String(payload?.detail || typedError?.message || 'No se pudo generar.');
    }
    return 'No se pudo generar: faltan datos válidos o hay conflictos duros. Revisá clases, franjas y recursos del período.';
  }
  if (status === 400 && action === 'publish' && detail.includes('cannot publish a failed run')) {
    return 'No se puede publicar una ejecución fallida. Generá nuevamente tras corregir los datos.';
  }
  if (status === 400 && fieldError) {
    return 'Validación incompleta: revisá período, día y rango horario antes de enviar.';
  }
  return typedError?.message || 'Error técnico inesperado.';
}

export function resolveAssignmentTeacherDisplay(assignment: Record<string, any>) {
  const directTeacher = String(assignment?.teacher_name || assignment?.teacher?.full_name || assignment?.teacher?.username || '').trim();
  if (directTeacher) return directTeacher;

  const departmentTeacher = String(assignment?.department_teacher_name || assignment?.subject?.department_teacher_name || '').trim();
  if (departmentTeacher) return `${departmentTeacher} (depto)`;

  return 'No resuelto';
}

export function buildBulkTimeSlots(input: { periodId: number; daysOfWeek: number[]; startTime: string; endTime: string; intervalMinutes: number; breakRanges: BulkBreakRange[]; existingKeys: Set<string> }): BulkSlotResult {
  const toCreate: SlotPayload[] = []; const skipped: BulkSlotResult['skipped'] = [];
  const start = timeToMinutes(input.startTime); const end = timeToMinutes(input.endTime);
  const breaks = input.breakRanges.map((b) => ({ start: timeToMinutes(b.start), end: timeToMinutes(b.end) }));
  for (const dayOfWeek of input.daysOfWeek) {
    for (let cursor = start; cursor + input.intervalMinutes <= end; cursor += input.intervalMinutes) {
      const next = cursor + input.intervalMinutes;
      const startTime = minutesToTime(cursor);
      const endTime = minutesToTime(next);
      if (breaks.some((r) => rangesOverlap(cursor, next, r.start, r.end))) {
        skipped.push({ day_of_week: dayOfWeek, start_time: startTime, end_time: endTime, reason: 'break' });
        continue;
      }
      const key = `${dayOfWeek}|${startTime}|${endTime}`;
      if (input.existingKeys.has(key)) { skipped.push({ day_of_week: dayOfWeek, start_time: startTime, end_time: endTime, reason: 'duplicate' }); continue; }
      input.existingKeys.add(key);
      toCreate.push({ period: input.periodId, day_of_week: dayOfWeek, start_time: startTime, end_time: endTime });
    }
  }
  return { toCreate, skipped };
}

export function filterClassesForRunPeriod<T extends TimetableClassLike>(classes: T[], runs: TimetableRunLike[], selectedRunId: number | null) {
  if (!selectedRunId) return classes;
  const run = runs.find((r) => Number(r.id) === Number(selectedRunId));
  const periodId = run?.period?.id;
  if (!periodId) return classes;
  return classes.filter((cls) => Number(cls.period?.id) === Number(periodId));
}

export function buildTareaPayload(values: TimetableTareaFormValues, runId: number, fallbackTeacherId: number | null) {
  const explicitTeacherId = toOptionalNumber(values.teacherId);
  return { run_id: Number(runId), cls_id: Number(values.clsId), teacher_id: explicitTeacherId ?? fallbackTeacherId, classroom_id: toOptionalNumber(values.classroomId), timeslot_id: Number(values.timeslotId), activity_type: values.activityType, source: values.source, status: values.status };
}

export function summarizeViolations(violations: TimetableViolationLike[]) {
  return violations.reduce<TimetableViolationSummary>((summary, v) => {
    summary.total += 1; summary.penalty += Number(v.penalty ?? 0);
    if ((v.severity || '').toLowerCase() === 'hard') summary.hard += 1; else summary.soft += 1;
    return summary;
  }, { total: 0, hard: 0, soft: 0, penalty: 0 });
}

export function getRunDisplayName(run: TimetableRunLike) {
  const period = run.period_name?.trim() || run.period?.name?.trim() || `Ejecución #${run.id}`;
  const status = run.status?.trim() || 'draft';
  const count = Number(run.assignments_count ?? 0);
  return `${period} · ${status} · ${count} asignaciones`;
}

export function formatActivityType(activityType: string) {
  const key = String(activityType || '').toLowerCase();
  if (key === 'theory') return 'Teoría';
  if (key === 'lab') return 'Laboratorio';
  if (key === 'practice') return 'Práctica';
  if (key === 'seminar') return 'Seminario';
  return activityType || '—';
}

export type MyScheduleRow = { class_id: number; subject_name: string; day_of_week: number; start_time: string; end_time: string; source?: string | null; [key: string]: any };
export function normalizeMyScheduleRows(rows: MyScheduleRow[]) {
  return rows.map((row) => ({ ...row, source: row.source || 'legacy', schedule: [{ day_of_week: row.day_of_week, start_time: row.start_time, end_time: row.end_time }] }));
}

export function groupAssignmentsByClass(assignments: Array<Record<string, any>>) {
  const bucket = new Map<number, { cls: number; items: Array<Record<string, any>> }>();
  for (const assignment of assignments) { const cls = Number(assignment.cls ?? assignment.cls_id); if (!bucket.has(cls)) bucket.set(cls, { cls, items: [] }); bucket.get(cls)!.items.push(assignment); }
  return Array.from(bucket.values());
}

export function buildRunPreviewInfo(run: Record<string, any> | null, assignments: Array<Record<string, any>>) {
  const status = String(run?.status || 'draft').toLowerCase();
  const statusLabelMap: Record<string, string> = {
    draft: 'Borrador', running: 'En ejecución', completed: 'Completada', partial: 'Parcial', failed: 'Fallida', published: 'Publicada',
  };
  const metadata = run?.metadata && typeof run.metadata === 'object' ? run.metadata : {};
  const score = metadata.score ?? metadata.summary?.score ?? metadata.metrics?.score;
  const metadataRows = Object.entries(metadata)
    .filter(([key]) => key !== 'score')
    .map(([key, value]) => ({ key, value: typeof value === 'string' ? value : JSON.stringify(value) }));
  const assignmentsCount = Number(run?.assignments_count ?? run?.asignaciones_count ?? assignments.length ?? 0);
  const violationsCount = Number(run?.violations_count ?? 0);

  return {
    periodLabel: run?.period_name || run?.period?.name || `Ejecución #${run?.id ?? '—'}`,
    statusLabel: statusLabelMap[status] || status,
    assignmentsCount,
    violationsCount,
    scoreLabel: Number.isFinite(Number(score)) ? String(score) : '—',
    metadataRows,
    hasAssignments: assignmentsCount > 0,
  };
}

export function extractCareerOptions(assignments: AssignmentGridRow[]) {
  const map = new Map<number, string>();
  assignments.forEach((a) => {
    const id = Number(a.career_id);
    if (Number.isInteger(id) && id > 0 && !map.has(id)) map.set(id, a.career_name || `Carrera #${id}`);
  });
  return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
}

const DAY_TO_INDEX: Record<string, number> = {
  monday: 0, tuesday: 1, wednesday: 2, thursday: 3, friday: 4,
};

export function normalizeAssignmentsToWeekGrid(assignments: AssignmentGridRow[], selectedCareerId: number | null = null) {
  return assignments
    .filter((a) => (selectedCareerId ? Number(a.career_id) === Number(selectedCareerId) : true))
    .map<TimetableGridBlock>((a) => {
      const dayName = String(a.timeslot_day_name || '').toLowerCase();
      const day = DAY_TO_INDEX[dayName] ?? -1;
      const hour = String(a.timeslot_start_time || '00:00:00').slice(0, 5);
      const label = `${a.subject_code || a.subject_name || 'Clase'} · ${a.classroom_name || 'Sin aula'}`;
      return { id: Number(a.id), day, hour, label, careerId: a.career_id ? Number(a.career_id) : null, careerName: a.career_name || null };
    })
    .filter((b) => b.day >= 0 && b.day <= 4);
}

export function buildConstraintPayload(values: ConstraintFormValues) {
  return {
    kind: values.kind,
    scope: values.scope,
    period: values.scope === 'period' ? toOptionalNumber(values.period) : null,
    teacher: values.kind === 'teacher_unavailable' ? toOptionalNumber(values.teacher) : null,
    classroom: values.kind === 'classroom_unavailable' ? toOptionalNumber(values.classroom) : null,
    career: values.kind === 'career_unavailable' ? toOptionalNumber(values.career) : null,
    day_of_week: Number(values.dayOfWeek),
    start_time: values.startTime,
    end_time: values.endTime,
    is_active: values.isActive,
    metadata: {},
  };
}

export function mapConstraintFieldErrors(payload: any): Record<string, string> {
  if (!payload || typeof payload !== 'object') return {};
  const result: Record<string, string> = {};
  Object.entries(payload).forEach(([key, value]) => {
    if (Array.isArray(value) && value[0]) result[key] = String(value[0]);
  });
  return result;
}
