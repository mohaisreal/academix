import { describe, expect, it } from 'vitest';
import {
  buildBulkTimeSlots,
  buildTimeslotBatch,
  buildRunPreviewInfo,
  classifyTimetableActionError,
  requireSelectedPeriod,
  buildDraftRunPayload,
  buildManualTimeslotPayload,
  normalizeMyScheduleRows,
  groupAssignmentsByClass,
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

  it('falla cuando el período no está seleccionado', () => {
    expect(() => buildTimeslotBatch({
      period: '',
      dayOfWeek: '1',
      startTime: '08:00',
      endTime: '09:00',
      intervalMinutes: '30',
      breakRanges: [],
    })).toThrow('Seleccioná un período válido antes de crear franjas.');
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
  it('devuelve id numérico cuando hay período válido', () => {
    expect(requireSelectedPeriod('12')).toBe(12);
  });

  it('rechaza cuando falta período', () => {
    expect(() => requireSelectedPeriod('')).toThrow('Seleccioná un período antes de continuar.');
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
        detail: 'No se pudo generar: faltan clases para el período.',
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

  it('mapea 400 de validación/precondición por campos', () => {
    const e = Object.assign(new Error('Bad request'), { status: 400, payload: { period: ['This field is required.'] } });
    expect(classifyTimetableActionError(e, 'timeslot')).toBe('Validación incompleta: revisá período, día y rango horario antes de enviar.');
  });

  it('mapea 400 de negocio en publish failed', () => {
    const e = Object.assign(new Error('Cannot publish a failed run.'), { status: 400, payload: { detail: 'Cannot publish a failed run.' } });
    expect(classifyTimetableActionError(e, 'publish')).toContain('No se puede publicar una ejecución fallida');
  });
});

describe('payload helpers', () => {
  it('arma payload de draft con period canónico', () => {
    expect(buildDraftRunPayload('12')).toEqual({ period: 12, status: 'draft', metadata: {} });
  });

  it('bloquea draft cuando falta período', () => {
    expect(() => buildDraftRunPayload('')).toThrow('Seleccioná un período para crear la ejecución.');
  });

  it('arma payload de slot manual con period y horario', () => {
    expect(buildManualTimeslotPayload({ period: '9', dayOfWeek: '2', startTime: '08:00', endTime: '09:00' })).toEqual({
      period: 9,
      day_of_week: 2,
      start_time: '08:00',
      end_time: '09:00',
    });
  });

  it('bloquea slot manual cuando falta período', () => {
    expect(() => buildManualTimeslotPayload({ period: '', dayOfWeek: '2', startTime: '08:00', endTime: '09:00' })).toThrow('Seleccioná un período para crear franjas.');
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
});

describe('buildRunPreviewInfo', () => {
  it('arma resumen de preview con metadata y score en distintas rutas', () => {
    const preview = buildRunPreviewInfo(
      {
        id: 33,
        status: 'completed',
        period_name: '2026-1',
        assignments_count: 4,
        violations_count: 1,
        metadata: {
          score: 87.5,
          generator: 'greedy-v2',
          summary: { created: 4, unassigned: 0 },
        },
      },
      [{ id: 1 }, { id: 2 }],
    );

    expect(preview.statusLabel).toBe('Completada');
    expect(preview.assignmentsCount).toBe(4);
    expect(preview.violationsCount).toBe(1);
    expect(preview.scoreLabel).toBe('87.5');
    expect(preview.metadataRows).toEqual([
      { key: 'generator', value: 'greedy-v2' },
      { key: 'summary', value: '{"created":4,"unassigned":0}' },
    ]);
    expect(preview.hasAssignments).toBe(true);
  });

  it('tolera metadata vacía y usa fallback con lista real de asignaciones', () => {
    const preview = buildRunPreviewInfo(
      {
        id: 34,
        status: 'partial',
        period_name: '2026-2',
        metadata: null,
      },
      [{ id: 1 }, { id: 2 }, { id: 3 }],
    );

    expect(preview.statusLabel).toBe('Parcial');
    expect(preview.assignmentsCount).toBe(3);
    expect(preview.violationsCount).toBe(0);
    expect(preview.scoreLabel).toBe('—');
    expect(preview.metadataRows).toEqual([]);
    expect(preview.hasAssignments).toBe(true);
  });

  it('muestra preview vacío sin asignaciones y sin endpoint dedicado', () => {
    const preview = buildRunPreviewInfo(
      {
        id: 35,
        status: 'draft',
        period_name: '2026-3',
        metadata: {},
      },
      [],
    );

    expect(preview.statusLabel).toBe('Borrador');
    expect(preview.assignmentsCount).toBe(0);
    expect(preview.violationsCount).toBe(0);
    expect(preview.hasAssignments).toBe(false);
    expect(preview.metadataRows).toEqual([]);
  });
});
