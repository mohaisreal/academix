import { describe, expect, it } from 'vitest';
import {
  buildBulkTimeSlots,
  buildTimeslotBatch,
  canDeleteTimetableRunStatus,
  classifyTimetableActionError,
  requireSelectedPeriod,
  buildDraftRunPayload,
  buildManualTimeslotPayload,
  normalizeMyScheduleRows,
  groupAssignmentsByClass,
  extractCareerOptions,
  normalizeAssignmentsToWeekGrid,
  buildWeekGridRows,
  buildConstraintPayload,
  buildResponsiveScheduleCards,
  formatConstraintDay,
  formatConstraintEntity,
  formatConstraintKind,
  formatConstraintScope,
  formatConstraintTimeRange,
  mapConstraintFieldErrors,
  resolveAssignmentTeacherDisplay,
  resolveTimetableRunPeriodId,
  filterClassesForRunPeriod,
} from '../timetable-management-utils';

describe('buildBulkTimeSlots', () => {
  it('crea slots por intervalos y omite descansos', () => {
    const result = buildBulkTimeSlots({
      periodId: 7,
      daysOfWeek: [1],
      startTime: '08:00',
      endTime: '10:00',
      intervalMinutes: 30,
      breakRanges: [{ start: '09:00', end: '09:30' }],
      existingKeys: new Set<string>(),
    });

    expect(result.toCreate).toHaveLength(3);
    expect(result.toCreate.map((s) => `${s.start_time}-${s.end_time}`)).toEqual([
      '08:00-08:30',
      '08:30-09:00',
      '09:30-10:00',
    ]);
    expect(result.skipped).toEqual([
      { day_of_week: 1, start_time: '09:00', end_time: '09:30', reason: 'break' },
    ]);
  });

  it('evita duplicados por clave día/inicio/fin y los reporta', () => {
    const result = buildBulkTimeSlots({
      periodId: 7,
      daysOfWeek: [1],
      startTime: '08:00',
      endTime: '09:00',
      intervalMinutes: 30,
      breakRanges: [],
      existingKeys: new Set<string>(['1|08:00|08:30']),
    });

    expect(result.toCreate).toEqual([
      { period: 7, day_of_week: 1, start_time: '08:30', end_time: '09:00' },
    ]);
    expect(result.skipped).toEqual([
      { day_of_week: 1, start_time: '08:00', end_time: '08:30', reason: 'duplicate' },
    ]);
  });

  it('avanza tras un duplicado y sigue generando las siguientes franjas', () => {
    const result = buildBulkTimeSlots({
      periodId: 7,
      daysOfWeek: [1],
      startTime: '08:00',
      endTime: '09:30',
      intervalMinutes: 30,
      breakRanges: [],
      existingKeys: new Set<string>(['1|08:00|08:30']),
    });

    expect(result.toCreate.map((s) => `${s.start_time}-${s.end_time}`)).toEqual([
      '08:30-09:00',
      '09:00-09:30',
    ]);
    expect(result.skipped).toEqual([
      { day_of_week: 1, start_time: '08:00', end_time: '08:30', reason: 'duplicate' },
    ]);
  });

  it('salta un descanso y reanuda con la siguiente franja válida', () => {
    const result = buildBulkTimeSlots({
      periodId: 7,
      daysOfWeek: [1],
      startTime: '08:15',
      endTime: '14:15',
      intervalMinutes: 55,
      breakRanges: [{ start: '11:00', end: '11:30' }],
      existingKeys: new Set<string>(),
    });

    expect(result.toCreate.map((s) => `${s.start_time}-${s.end_time}`)).toEqual([
      '08:15-09:10',
      '09:10-10:05',
      '10:05-11:00',
      '11:30-12:25',
      '12:25-13:20',
      '13:20-14:15',
    ]);
    expect(result.skipped).toEqual([{ day_of_week: 1, start_time: '11:00', end_time: '11:55', reason: 'break' }]);
  });

  it('salta múltiples descansos en orden sin generar franjas dentro de ellos', () => {
    const result = buildBulkTimeSlots({
      periodId: 7,
      daysOfWeek: [1],
      startTime: '08:15',
      endTime: '16:15',
      intervalMinutes: 55,
      breakRanges: [
        { start: '11:00', end: '11:30' },
        { start: '14:15', end: '14:45' },
      ],
      existingKeys: new Set<string>(),
    });

    expect(result.toCreate.map((s) => `${s.start_time}-${s.end_time}`)).toEqual([
      '08:15-09:10',
      '09:10-10:05',
      '10:05-11:00',
      '11:30-12:25',
      '12:25-13:20',
      '13:20-14:15',
      '14:45-15:40',
    ]);
    expect(result.skipped).toEqual([
      { day_of_week: 1, start_time: '11:00', end_time: '11:55', reason: 'break' },
      { day_of_week: 1, start_time: '14:15', end_time: '15:10', reason: 'break' },
    ]);
  });
});

describe('buildResponsiveScheduleCards', () => {
  it('flatten schedule rows into mobile-friendly cards', () => {
    const cards = buildResponsiveScheduleCards([
      {
        subject_name: 'Matemática',
        classroom_name: 'A-101',
        schedules: [{ day_of_week: 1, start_time: '08:00', end_time: '09:30' }],
      },
    ]);

    expect(cards).toEqual([
      { subject: 'Matemática', day: 'Lun', time: '08:00 – 09:30', classroom: 'A-101' },
    ]);
  });
});

describe('buildTimeslotBatch', () => {
  it('incluye period en cada slot generado', () => {
    const batch = buildTimeslotBatch({
      period: '9',
      dayOfWeek: '1',
      startTime: '08:00',
      endTime: '09:00',
      intervalMinutes: '30',
      breakRanges: [],
    });

    expect(batch).toEqual([
      { period: 9, day_of_week: 1, start_time: '08:00', end_time: '08:30' },
      { period: 9, day_of_week: 1, start_time: '08:30', end_time: '09:00' },
    ]);
  });

  it('falla cuando el periodo no está seleccionado', () => {
    expect(() => buildTimeslotBatch({
      period: '',
      dayOfWeek: '1',
      startTime: '08:00',
      endTime: '09:00',
      intervalMinutes: '30',
      breakRanges: [],
    })).toThrow('Selecciona un periodo válido antes de crear franjas.');
  });

  it('falla cuando el intervalo es inválido (start >= end)', () => {
    expect(() => buildTimeslotBatch({
      period: '9',
      dayOfWeek: '1',
      startTime: '09:00',
      endTime: '09:00',
      intervalMinutes: '30',
      breakRanges: [],
    })).toThrow('La hora de fin debe ser posterior a la hora de inicio.');
  });
});

describe('requireSelectedPeriod', () => {
  it('devuelve id numérico cuando hay periodo válido', () => {
    expect(requireSelectedPeriod('12')).toBe(12);
  });

  it('rechaza cuando falta periodo', () => {
    expect(() => requireSelectedPeriod('')).toThrow('Selecciona un periodo antes de continuar.');
  });
});

describe('classifyTimetableActionError', () => {
  it('mapea 400 de negocio en generate', () => {
    const e = Object.assign(new Error('Run failed due to hard constraints'), { status: 400, payload: { status: 'failed' } });
    expect(classifyTimetableActionError(e, 'generate')).toContain('No se pudo generar');
  });

  it('muestra mensaje específico cuando faltan clases', () => {
    const e = Object.assign(new Error('Bad request'), {
      status: 400,
      payload: {
        status: 'failed',
        detail: 'No se pudo generar: faltan clases para el periodo.',
        metadata: { generator: { precondition_errors: ['missing_classes'] } },
      },
    });

    expect(classifyTimetableActionError(e, 'generate')).toContain('faltan clases');
  });

  it('muestra mensaje específico cuando faltan franjas', () => {
    const e = Object.assign(new Error('Bad request'), {
      status: 400,
      payload: {
        status: 'failed',
        metadata: { generator: { precondition_errors: ['missing_time_slots'] } },
      },
    });

    expect(classifyTimetableActionError(e, 'generate')).toContain('franjas horarias');
  });

  it('mapea error de preparación por falta de materias activas', () => {
    const e = Object.assign(new Error('Bad request'), {
      status: 400,
      payload: {
        status: 'failed',
        metadata: { generator: { class_preparation_errors: ['class_preparation_insufficient_subjects'] } },
      },
    });

    expect(classifyTimetableActionError(e, 'generate')).toContain('materias activas');
  });

  it('mapea error de preparación por falta de aulas', () => {
    const e = Object.assign(new Error('Bad request'), {
      status: 400,
      payload: {
        status: 'failed',
        metadata: { generator: { class_preparation_errors: ['class_preparation_insufficient_classrooms'] } },
      },
    });

    expect(classifyTimetableActionError(e, 'generate')).toContain('aulas disponibles');
  });

  it('muestra mensaje específico cuando hay docentes sin resolver', () => {
    const e = Object.assign(new Error('Bad request'), {
      status: 400,
      payload: {
        status: 'failed',
        metadata: { generator: { unresolved_teachers: [44, 45] } },
      },
    });

    expect(classifyTimetableActionError(e, 'generate')).toContain('docentes sin resolver');
  });

  it('mapea 400 de validación/precondición por campos', () => {
    const e = Object.assign(new Error('Bad request'), { status: 400, payload: { period: ['This field is required.'] } });
    expect(classifyTimetableActionError(e, 'timeslot')).toBe('Validación incompleta: revisá periodo, día y rango horario antes de enviar.');
  });

  it('mapea 400 de negocio en publish failed', () => {
    const e = Object.assign(new Error('Cannot publish a failed run.'), { status: 400, payload: { detail: 'Cannot publish a failed run.' } });
    expect(classifyTimetableActionError(e, 'publish')).toContain('No se puede publicar una ejecución fallida');
  });

  it('mapea 400 de negocio en delete published', () => {
    const e = Object.assign(new Error('No se puede eliminar una ejecución publicada.'), { status: 400, payload: { detail: 'No se puede eliminar una ejecución publicada.' } });
    expect(classifyTimetableActionError(e, 'delete')).toContain('publicada');
  });
});

describe('canDeleteTimetableRunStatus', () => {
  it('habilita delete para runs no publicadas', () => {
    expect(canDeleteTimetableRunStatus('draft')).toBe(true);
    expect(canDeleteTimetableRunStatus('failed')).toBe(true);
    expect(canDeleteTimetableRunStatus('partial')).toBe(true);
    expect(canDeleteTimetableRunStatus('completed')).toBe(true);
  });

  it('bloquea delete para published y desconocidos', () => {
    expect(canDeleteTimetableRunStatus('published')).toBe(false);
    expect(canDeleteTimetableRunStatus('archived')).toBe(false);
    expect(canDeleteTimetableRunStatus(undefined)).toBe(false);
    expect(canDeleteTimetableRunStatus(null)).toBe(false);
  });
});

describe('resolveTimetableRunPeriodId', () => {
  it('resuelve period numérico plano', () => {
    expect(resolveTimetableRunPeriodId({ id: 1, period: 7 })).toBe(7);
  });

  it('resuelve period_id y period.id', () => {
    expect(resolveTimetableRunPeriodId({ id: 1, period_id: 8 })).toBe(8);
    expect(resolveTimetableRunPeriodId({ id: 1, period: { id: 9 } })).toBe(9);
  });

  it('rechaza valores inválidos', () => {
    expect(resolveTimetableRunPeriodId({ id: 1, period: 0 })).toBeNull();
    expect(resolveTimetableRunPeriodId({ id: 1, period_id: 'x' as any })).toBeNull();
    expect(resolveTimetableRunPeriodId({ id: 1, period: { id: null as any } })).toBeNull();
  });
});

describe('filterClassesForRunPeriod', () => {
  it('filtra clases por periodo cuando la ejecución resuelve periodo', () => {
    const classes = [{ id: 1, period: { id: 3 } }, { id: 2, period: { id: 4 } }];
    const runs = [{ id: 10, period: 3 }];

    expect(filterClassesForRunPeriod(classes, runs as any, 10)).toEqual([{ id: 1, period: { id: 3 } }]);
  });

  it('conserva fallback cuando la ejecución no resuelve periodo', () => {
    const classes = [{ id: 1, period: { id: 3 } }, { id: 2, period: { id: 4 } }];
    const runs = [{ id: 10, period: null }];

    expect(filterClassesForRunPeriod(classes, runs as any, 10)).toEqual(classes);
  });
});

describe('payload helpers', () => {
  it('arma payload de draft con period canónico', () => {
    expect(buildDraftRunPayload('12')).toEqual({ period: 12, status: 'draft', metadata: {} });
  });

  it('bloquea draft cuando falta periodo', () => {
    expect(() => buildDraftRunPayload('')).toThrow('Selecciona un periodo para crear la ejecución.');
  });

  it('arma payload de slot manual con period y horario', () => {
    expect(buildManualTimeslotPayload({ period: '9', dayOfWeek: '2', startTime: '08:00', endTime: '09:00' })).toEqual({
      period: 9,
      day_of_week: 2,
      start_time: '08:00',
      end_time: '09:00',
    });
  });

  it('bloquea slot manual cuando falta periodo', () => {
    expect(() => buildManualTimeslotPayload({ period: '', dayOfWeek: '2', startTime: '08:00', endTime: '09:00' })).toThrow('Selecciona un periodo para crear franjas.');
  });
});

describe('normalizeMyScheduleRows', () => {
  it('normaliza filas del contrato generated-first sin romper legacy', () => {
    const rows = normalizeMyScheduleRows([
      {
        class_id: 10,
        subject_name: 'Algoritmos',
        day_of_week: 1,
        start_time: '08:00',
        end_time: '09:00',
        source: 'generated',
      },
      {
        class_id: 10,
        subject_name: 'Algoritmos',
        day_of_week: 3,
        start_time: '10:00',
        end_time: '11:00',
      },
    ]);

    expect(rows).toHaveLength(2);
    expect(rows[0].source).toBe('generated');
    expect(rows[1].source).toBe('legacy');
    expect(rows[1].schedule).toHaveLength(1);
  });

  it('preserva múltiples bloques cuando la fila ya trae schedule/schedules', () => {
    const rows = normalizeMyScheduleRows([
      {
        class_id: 22,
        subject_name: 'Física',
        source: 'generated',
        schedules: [
          { day_of_week: 1, start_time: '08:00', end_time: '09:00' },
          { day_of_week: 3, start_time: '10:00', end_time: '11:00' },
        ],
      },
    ] as any);

    expect(rows).toHaveLength(1);
    expect(rows[0].schedule).toEqual([
      { day_of_week: 1, start_time: '08:00', end_time: '09:00' },
      { day_of_week: 3, start_time: '10:00', end_time: '11:00' },
    ]);
  });
});

describe('groupAssignmentsByClass', () => {
  it('agrupa asignaciones por clase para edición operativa', () => {
    const grouped = groupAssignmentsByClass([
      { id: 1, cls: 20, run: 3, slot: 4, classroom: 5, teacher: 7, source: 'generated' },
      { id: 2, cls: 20, run: 3, slot: 8, classroom: 5, teacher: 7, source: 'generated' },
      { id: 3, cls: 21, run: 3, slot: 4, classroom: 5, teacher: 9, source: 'manual' },
    ]);

    expect(grouped).toHaveLength(2);
    expect(grouped[0].cls).toBe(20);
    expect(grouped[0].items).toHaveLength(2);
    expect(grouped[1].cls).toBe(21);
  });

  it('soporta cls_id alternativo y ordena ítems por slot', () => {
    const grouped = groupAssignmentsByClass([
      { id: 11, cls_id: 40, timeslot_day_name: 'Wednesday', timeslot_start_time: '10:00:00' },
      { id: 10, cls_id: 40, timeslot_day_name: 'Monday', timeslot_start_time: '08:00:00' },
    ]);

    expect(grouped).toHaveLength(1);
    expect(grouped[0].cls).toBe(40);
    expect(grouped[0].items.map((i) => i.id)).toEqual([10, 11]);
  });
});

describe('preview grid + constraints helpers', () => {
  it('extrae carreras únicas desde asignaciones', () => {
    const careers = extractCareerOptions([
      { id: 1, career_id: 2, career_name: 'Ingeniería' },
      { id: 2, career_id: 2, career_name: 'Ingeniería' },
      { id: 3, career_id: 3, career_name: 'Derecho' },
    ]);
    expect(careers).toEqual([{ id: 2, name: 'Ingeniería' }, { id: 3, name: 'Derecho' }]);
  });

  it('normaliza asignaciones a grilla L-V y filtra por carrera', () => {
    const grid = normalizeAssignmentsToWeekGrid([
      { id: 10, career_id: 2, career_name: 'Ingeniería', subject_code: 'ALG', classroom_name: 'A1', timeslot_day_name: 'Monday', timeslot_start_time: '08:00:00' },
      { id: 11, career_id: 3, career_name: 'Derecho', subject_code: 'DER', classroom_name: 'B1', timeslot_day_name: 'Tuesday', timeslot_start_time: '09:00:00' },
    ], 2);
    expect(grid).toHaveLength(1);
    expect(grid[0].day).toBe(0);
    expect(grid[0].hour).toBe('08:00');
  });

  it('mapea días en español (Lunes..Viernes) a índices válidos de preview', () => {
    const grid = normalizeAssignmentsToWeekGrid([
      { id: 21, subject_code: 'MAT', classroom_name: 'A1', timeslot_day_name: 'Lunes', timeslot_start_time: '08:00:00' },
      { id: 22, subject_code: 'FIS', classroom_name: 'A2', timeslot_day_name: 'Martes', timeslot_start_time: '09:00:00' },
      { id: 23, subject_code: 'QUI', classroom_name: 'A3', timeslot_day_name: 'Miércoles', timeslot_start_time: '10:00:00' },
      { id: 24, subject_code: 'HIS', classroom_name: 'A4', timeslot_day_name: 'Jueves', timeslot_start_time: '11:00:00' },
      { id: 25, subject_code: 'BIO', classroom_name: 'A5', timeslot_day_name: 'Viernes', timeslot_start_time: '12:00:00' },
    ]);

    expect(grid.map((b) => b.day)).toEqual([0, 1, 2, 3, 4]);
  });

  it('normaliza variantes con/sin tilde y case-insensitive de Miércoles', () => {
    const grid = normalizeAssignmentsToWeekGrid([
      { id: 31, subject_code: 'ALG', classroom_name: 'A1', timeslot_day_name: 'miércoles', timeslot_start_time: '08:00:00' },
      { id: 32, subject_code: 'ALG', classroom_name: 'A1', timeslot_day_name: 'MIERCOLES', timeslot_start_time: '09:00:00' },
      { id: 33, subject_code: 'ALG', classroom_name: 'A1', timeslot_day_name: 'Miercoles', timeslot_start_time: '10:00:00' },
    ]);

    expect(grid).toHaveLength(3);
    expect(grid.every((b) => b.day === 2)).toBe(true);
  });

  it('mantiene compatibilidad legacy en inglés y excluye etiquetas inválidas', () => {
    const grid = normalizeAssignmentsToWeekGrid([
      { id: 41, subject_code: 'ING', classroom_name: 'B1', timeslot_day_name: 'Monday', timeslot_start_time: '08:00:00' },
      { id: 42, subject_code: 'INV', classroom_name: 'B2', timeslot_day_name: 'Funday', timeslot_start_time: '09:00:00' },
      { id: 43, subject_code: 'VAC', classroom_name: 'B3', timeslot_day_name: '', timeslot_start_time: '10:00:00' },
    ]);

    expect(grid).toHaveLength(1);
    expect(grid[0].id).toBe(41);
    expect(grid[0].day).toBe(0);
  });

  it('mantiene colisiones en misma celda día/hora para render múltiple', () => {
    const rows = buildWeekGridRows([
      { id: 10, day: 0, hour: '08:00', label: 'ALG · A1', careerId: 2, careerName: 'Ingeniería' },
      { id: 11, day: 0, hour: '08:00', label: 'FIS · A2', careerId: 2, careerName: 'Ingeniería' },
      { id: 12, day: 1, hour: '08:00', label: 'DER · B1', careerId: 3, careerName: 'Derecho' },
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0].hour).toBe('08:00');
    expect(rows[0].cells[0].blocks.map((b) => b.id)).toEqual([10, 11]);
    expect(rows[0].cells[1].blocks.map((b) => b.id)).toEqual([12]);
  });

  it('arma payload de restricción por tipo/scope', () => {
    const payload = buildConstraintPayload({
      kind: 'teacher_unavailable', scope: 'period', period: '5', teacher: '8', classroom: '', career: '', dayOfWeek: '2', startTime: '10:00:00', endTime: '11:00:00', isActive: true,
    });
    expect(payload.period).toBe(5);
    expect(payload.teacher).toBe(8);
    expect(payload.classroom).toBeNull();
  });

  it('emite subject y run para subject_unavailable', () => {
    const payload = buildConstraintPayload({
      kind: 'subject_unavailable', scope: 'period', period: '5', teacher: '', classroom: '', career: '', dayOfWeek: '2', startTime: '10:00:00', endTime: '11:00:00', isActive: true, subject: '7', run: '3',
    } as any);

    expect(payload.subject).toBe(7);
    expect(payload.run).toBe(3);
  });

  it('mapea errores por campo desde payload DRF', () => {
    expect(mapConstraintFieldErrors({ period: ['Requerido'], teacher: ['Inválido'] })).toEqual({ period: 'Requerido', teacher: 'Inválido' });
  });

  it('resuelve docente visible con precedencia teacher > department > pendiente', () => {
    expect(resolveAssignmentTeacherDisplay({ teacher_name: 'Ada Lovelace', department_teacher_name: 'Grace Hopper' })).toBe('Ada Lovelace');
    expect(resolveAssignmentTeacherDisplay({ teacher_name: '', department_teacher_name: 'Grace Hopper' })).toContain('Grace Hopper');
    expect(resolveAssignmentTeacherDisplay({ teacher_name: '', department_teacher_name: '' })).toBe('No resuelto');
  });

  it('prioriza labels de backend para kind/scope/day', () => {
    expect(formatConstraintKind({ kind: 'teacher_unavailable', kind_label: 'Docente bloqueado' } as any)).toBe('Docente bloqueado');
    expect(formatConstraintScope({ scope: 'period', scope_label: 'Periodo académico' } as any)).toBe('Periodo académico');
    expect(formatConstraintDay({ day_of_week: 0, day_label: 'Lunes (backend)' } as any)).toBe('Lunes (backend)');
  });

  it('usa fallback conocido y placeholder neutral para códigos desconocidos', () => {
    expect(formatConstraintKind({ kind: 'classroom_unavailable' } as any)).toBe('Aula no disponible');
    expect(formatConstraintScope({ scope: 'global' } as any)).toBe('Global');
    expect(formatConstraintKind({ kind: 'x_unknown' } as any)).toBe('Tipo no especificado');
    expect(formatConstraintScope({ scope: 'x_unknown' } as any)).toBe('Alcance no especificado');
    expect(formatConstraintDay({ day_of_week: 99 } as any)).toBe('Día no especificado');
  });

  it('formatea entidad y rango horario en formato amigable', () => {
    expect(formatConstraintEntity({ teacher_name: 'Ada Lovelace' } as any)).toBe('Ada Lovelace');
    expect(formatConstraintEntity({ classroom_name: 'Aula 101' } as any)).toBe('Aula 101');
    expect(formatConstraintEntity({ subject_name: 'Ingeniería' } as any)).toBe('Ingeniería');
    expect(formatConstraintEntity({} as any)).toBe('Entidad no especificada');

    expect(formatConstraintTimeRange({ start_time: '08:00:00', end_time: '09:30:00' } as any)).toBe('08:00–09:30');
    expect(formatConstraintTimeRange({ start_time: '', end_time: '' } as any)).toBe('Horario no especificado');
  });

  it('labels subject unavailable constraints', () => {
    expect(formatConstraintKind({ kind: 'subject_unavailable' } as any)).toBe('Asignatura no disponible');
  });

  it('nulls subject when kind is different', () => {
    const payload = buildConstraintPayload({
      kind: 'teacher_unavailable', scope: 'period', period: '5', teacher: '8', classroom: '', career: '', dayOfWeek: '2', startTime: '10:00:00', endTime: '11:00:00', isActive: true, subject: '7', run: '',
    } as any);

    expect(payload.subject).toBeNull();
  });
});
