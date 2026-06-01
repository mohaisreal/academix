import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const pagePath = resolve(process.cwd(), 'src/pages/management/timetable/index.astro');

function readPage() {
  return readFileSync(pagePath, 'utf8');
}

describe('management timetable page layout cleanup', () => {
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
});
