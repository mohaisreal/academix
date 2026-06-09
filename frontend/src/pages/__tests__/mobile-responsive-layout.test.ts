import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('mobile responsive layout contracts', () => {
  it('keeps the dashboard shell viewport-safe while preserving the desktop sidebar offset', () => {
    const layout = readProjectFile('src/layouts/DashboardLayout.astro');

    expect(layout).toContain('<body class="bg-background text-foreground overflow-x-hidden"');
    expect(layout).toContain('class="mt-14 lg:pl-60 flex-1 min-w-0 max-w-full bg-muted/20');
    expect(layout).toContain('lg:translate-x-0');
    expect(layout).toContain('lg:pl-60');
  });

  it('keeps the dashboard home grids responsive and preserves scroll-contained tables', () => {
    const page = readProjectFile('src/pages/index.astro');

    expect(page).toContain('grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4');
    expect(page).toContain('grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3');
    expect(page).toContain('grid grid-cols-1 gap-4 sm:grid-cols-2');
    expect(page).toContain('overflow-x-auto');
  });

  it('stacks split panes and constrains overlays on messages, marking, and reports', () => {
    const messages = readProjectFile('src/pages/messages/index.astro');
    const marking = readProjectFile('src/pages/marking/index.astro');
    const reports = readProjectFile('src/pages/reports/index.astro');

    expect(messages).toContain('flex flex-col lg:flex-row');
    expect(messages).toContain('w-full lg:w-80');
    expect(messages).toContain('w-full bg-card rounded-xl border border-border animate-pulse sm:w-80');

    expect(marking).toContain('flex flex-col lg:flex-row');
    expect(marking).toContain('w-full lg:w-80');
    expect(marking).toContain('w-full max-w-[calc(100vw-2rem)] sm:w-96');

    expect(reports).toContain('flex flex-col lg:flex-row');
    expect(reports).toContain('w-full lg:w-64');
    expect(reports).toContain('overflow-x-auto');
  });

  it('keeps timetable and my-file datasets contained on mobile widths', () => {
    const timetable = readProjectFile('src/pages/timetable/index.astro');
    const myFile = readProjectFile('src/pages/my-file/index.astro');

    expect(timetable).toContain('min-w-[700px]');
    expect(timetable).toContain('overflow-x-auto');
    expect(timetable).toContain('hidden md:block');
    expect(timetable).toContain('md:hidden');

    expect(myFile).toContain('grid grid-cols-1 gap-4 sm:grid-cols-2');
    expect(myFile).toContain('overflow-x-auto');
    expect(myFile).toContain('print:hidden');
  });

  it('keeps admissions, questionnaire, and enrollment flows mobile-safe', () => {
    const preinscripcion = readProjectFile('src/pages/admissions/preinscripcion.astro');
    const myApplications = readProjectFile('src/pages/admissions/my-applications/index.astro');
    const apply = readProjectFile('src/pages/admissions/apply/[id].astro');
    const questionnaire = readProjectFile('src/pages/admissions/questionnaire/[id].astro');
    const enrolment = readProjectFile('src/pages/enrolment/management/index.astro');
    const receipt = readProjectFile('src/pages/enrollment/receipt/[id].astro');

    expect(preinscripcion).toContain('flex flex-col gap-3 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6');
    expect(preinscripcion).toContain('p-4 sm:p-6 max-w-3xl mx-auto');
    expect(preinscripcion).toContain('flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between');

    expect(myApplications).toContain('flex flex-col gap-3 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6');
    expect(myApplications).toContain('flex flex-col gap-3 px-5 py-3.5 border-b border-border bg-muted/20 sm:flex-row sm:items-center sm:justify-between');
    expect(myApplications).toContain('flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground');

    expect(apply).toContain('flex flex-col gap-3 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6');
    expect(apply).toContain('grid grid-cols-1 gap-4 sm:grid-cols-2');
    expect(apply).toContain('flex flex-col sm:flex-row gap-3');

    expect(questionnaire).toContain('flex flex-col gap-3 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6');
    expect(questionnaire).toContain('flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between pt-2');
    expect(questionnaire).toContain('w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-md bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:pointer-events-none');

    expect(enrolment).toContain('flex flex-col gap-3 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6');
    expect(enrolment).toContain('flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 px-5 py-4 border-t border-border shrink-0');
    expect(enrolment).toContain('w-full max-w-lg rounded-xl border border-border bg-background shadow-2xl max-h-[90vh] flex flex-col');

    expect(receipt).toContain('flex flex-col gap-3 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6 print:hidden');
    expect(receipt).toContain('grid grid-cols-1 gap-4 sm:grid-cols-2');
  });

  it('keeps questionnaires and preferences responsive without changing desktop widths', () => {
    const managementList = readProjectFile('src/pages/management/questionnaires/index.astro');
    const managementBuilder = readProjectFile('src/pages/management/questionnaires/[id].astro');
    const preferences = readProjectFile('src/pages/notifications/preferences.astro');

    expect(managementList).toContain('flex flex-col gap-3 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6');
    expect(managementList).toContain('flex flex-col sm:flex-row items-stretch sm:items-center gap-3');
    expect(managementList).toContain('w-full sm:w-64');

    expect(managementBuilder).toContain('flex flex-col gap-3 border-b border-border px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6');
    expect(managementBuilder).toContain('w-full lg:w-64');
    expect(managementBuilder).toContain('flex flex-col lg:flex-row');

    expect(preferences).toContain('border-b border-border px-4 py-4 sm:px-6');
    expect(preferences).toContain('grid gap-3 sm:grid-cols-2 md:grid-cols-3');
  });

  it('keeps grades usable for all classes while preserving desktop tabs', () => {
    const grades = readProjectFile('src/pages/grades/index.astro');

    expect(grades).toContain("const classQueryParam = new URLSearchParams(window.location.search).get('class');");
    expect(grades).toContain('const selectedClassId = getClassId(gradesData[selectedIdx]);');
    expect(grades).toContain('id="subject-selector"');
    expect(grades).toContain('hidden gap-1 overflow-x-auto pb-2 mb-4 border-b border-border md:flex');
    expect(grades).toContain('space-y-4 md:hidden');
    expect(grades).toContain('hidden overflow-x-auto md:block');
    expect(grades).toContain('<article class="rounded-xl border border-border bg-card p-4 shadow-sm">');
    expect(grades).toContain('activateSubject(`panel-${selectedIdx}`, selectedClassId);');
  });

  it('keeps questionnaire mobile actions wired to the shared page handlers', () => {
    const managementList = readProjectFile('src/pages/management/questionnaires/index.astro');

    expect(managementList).toContain('btn-toggle-active');
    expect(managementList).toContain('btn-set-wizard');
    expect(managementList).toContain('btn-unset-wizard');
    expect(managementList).toContain('btn-export');
    expect(managementList).toContain('btn-delete');
    expect(managementList).toContain('wireActions(mobile);');
    expect(managementList).toContain('wireActions(body);');
  });
});
