import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const pagePath = resolve(process.cwd(), 'src/pages/management/timetable/index.astro');

function readPage() {
  return readFileSync(pagePath, 'utf8');
}

describe('management timetable page layout cleanup', () => {
  it('expone el botón destructivo de limpieza de clases generadas', () => {
    const source = readPage();

    expect(source).toContain('id="cleanup-generated-classes-btn"');
    expect(source).toContain('Eliminar clases generadas');
    expect(source).toContain('title="Elimina las clases generadas automáticamente del periodo de la ejecución seleccionada"');
  });

  it('usa helper para habilitar eliminar y no hardcodea solo draft', () => {
    const source = readPage();

    expect(source).toContain('canDeleteTimetableRunStatus(run.status)');
    expect(source).not.toContain("run.status === 'draft'");
  });

  it('expone motivo visible de bloqueo al eliminar published', () => {
    const source = readPage();

    expect(source).toContain('No se puede eliminar una ejecución publicada');
    expect(source).toContain('aria-label="Eliminar ejecución"');
  });

  it('does not render inline preview or assignments sections', () => {
    const source = readPage();

    expect(source).not.toContain('Preview de ejecución generada');
    expect(source).not.toContain('<h2 class="text-lg font-semibold">Asignaciones</h2>');
  });

  it('renders Restricciones list area before form controls', () => {
    const source = readPage();
    const restrictionsIndex = source.indexOf('<h2 class="text-lg font-semibold">Restricciones</h2>');
    const listIndex = source.indexOf('id="constraints-list"', restrictionsIndex);
    const formIndex = source.indexOf('id="constraint-form"', restrictionsIndex);

    expect(restrictionsIndex).toBeGreaterThan(-1);
    expect(listIndex).toBeGreaterThan(restrictionsIndex);
    expect(formIndex).toBeGreaterThan(listIndex);
  });

  it('keeps empty-state message for restrictions list above the form', () => {
    const source = readPage();
    const emptyStateIndex = source.indexOf('Sin restricciones activas.');
    const formIndex = source.indexOf('id="constraint-form"');

    expect(emptyStateIndex).toBeGreaterThan(-1);
    expect(formIndex).toBeGreaterThan(emptyStateIndex);
  });

  it('uses select-driven restriction fields and hides raw ID placeholders', () => {
    const source = readPage();

    expect(source).toContain('<select id="constraint-period"');
    expect(source).toContain('<select id="constraint-teacher"');
    expect(source).toContain('<select id="constraint-classroom"');
    expect(source).toContain('<select id="constraint-career"');
    expect(source).not.toContain('placeholder="Period ID"');
    expect(source).not.toContain('placeholder="Teacher ID"');
    expect(source).not.toContain('placeholder="Classroom ID"');
    expect(source).not.toContain('placeholder="Career ID"');
  });

  it('restores the infringements panel markup with the expected DOM targets', () => {
    const source = readPage();

    expect(source).toContain('<h2 class="text-lg font-semibold">Infracciones</h2>');
    expect(source).toContain('id="violations-severity-filter"');
    expect(source).toContain('id="violations-total"');
    expect(source).toContain('id="violations-hard"');
    expect(source).toContain('id="violations-soft"');
    expect(source).toContain('id="violations-table-body"');
    expect(source).toContain('id="constraints-list"');
    expect(source).toContain('id="constraint-form"');
    expect(source).toContain('loadViolations()');
  });

  it('shows persistent warning counters and preview summary hooks', () => {
    const source = readPage();

    expect(source).toContain('id="selected-run-badge"');
    expect(source).toContain('id="preview-warning-summary"');
    expect(source).toContain('infracciones');
    expect(source).toContain('getRunWarningSummary');
  });

  it('guards publish and generate with soft-warning confirmation', () => {
    const source = readPage();

    expect(source).toContain('No se puede publicar: hay infracciones duras pendientes.');
    expect(source).toContain('No se puede generar: hay infracciones duras pendientes.');
    expect(source).toContain('¿Deseas publicar de todos modos?');
    expect(source).toContain('¿Deseas continuar con la generación?');
  });

  it('loads all restriction catalogs and syncs selector relevance', () => {
    const source = readPage();

    expect(source).toContain("loadAllPages('/users/teachers/')");
    expect(source).toContain("loadAllPages('/academic/classrooms/')");
    expect(source).toContain("loadAllPages('/academic/careers/')");
    expect(source).toContain('function syncConstraintSelectors()');
    expect(source).toContain("q('constraint-kind')?.addEventListener('change'");
    expect(source).toContain("q('constraint-scope')?.addEventListener('change'");
  });

  it('renders friendly constraints UI instead of raw snake_case fragments', () => {
    const source = readPage();

    expect(source).toContain('formatConstraintKind');
    expect(source).toContain('formatConstraintScope');
    expect(source).toContain('formatConstraintDay');
    expect(source).toContain('formatConstraintEntity');
    expect(source).toContain('formatConstraintTimeRange');
    expect(source).not.toContain('· ${esc(c.kind)} · día ${c.day_of_week}');
    expect(source).not.toContain('${c.kind}');
  });

  it('confirma antes de limpiar y cancela sin pegarle al endpoint', () => {
    const source = readPage();

    expect(source).toContain('window.confirm');
    expect(source).toContain('cleanup/generated-classes');
    expect(source).toContain('resolveTimetableRunPeriodId(selectedRun())');
    expect(source).toContain("body: JSON.stringify({ period: periodId })");
    expect(source).toContain("toast.success('Clases generadas eliminadas')");
    expect(source).toContain('Selecciona una ejecución con periodo antes de limpiar las clases generadas.');
  });

  it('mantiene el lote por intervalos conectado al parser de descansos', () => {
    const source = readPage();

    expect(source).toContain('buildTimeslotBatch({ period: period.value, dayOfWeek: day.value, startTime: start.value, endTime: end.value, intervalMinutes: interval.value, breakRanges: parseTimeslotBreakRanges(breaks.value) })');
    expect(source).toContain('timeslot-batch-breaks');
  });

  it('refresca runs, assignments y violations tras limpiar', () => {
    const source = readPage();

    expect(source).toContain('await Promise.all([loadRuns(), loadAssignments(), loadViolations()]);');
  });
});
