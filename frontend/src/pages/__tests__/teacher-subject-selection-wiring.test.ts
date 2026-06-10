import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('teacher subject selection wiring', () => {
  it('exposes the teacher submission page and management review page', () => {
    const teacherPage = readProjectFile('src/pages/enrollment/teacher-subjects.astro');
    const reviewPage = readProjectFile('src/pages/management/subject-decisions.astro');

    // Página del docente: selección por oferta (nuevo modelo — sin formulario masivo)
    expect(teacherPage).toContain('offerings-list');
    expect(teacherPage).toContain('select-offering-btn');
    // Página de gestión: lista de ofertas + panel de decisiones
    expect(reviewPage).toContain('offerings-list');
    expect(reviewPage).toContain('decisions-panel');
  });

  it('adds sidebar links for the new teacher and review flows', () => {
    const layout = readProjectFile('src/layouts/DashboardLayout.astro');

    expect(layout).toContain('/enrollment/teacher-subjects');
    expect(layout).toContain('/management/subject-decisions');
    expect(layout).toContain('<div id="nav-teacher" class="hidden">');
  });

  it('shows section labels and decision status hooks on key pages', () => {
    const enrollmentClasses = readProjectFile('src/pages/enrollment/classes/index.astro');
    const timetable = readProjectFile('src/pages/management/timetable/index.astro');
    const departments = readProjectFile('src/pages/departments/index.astro');

    expect(enrollmentClasses).toContain('Sección');
    expect(timetable).toContain('section_label');
    expect(departments).toContain('Decisiones');
  });

  it('keeps neutral Spanish copy and no English error fallbacks in target flows', () => {
    const teacherPage = readProjectFile('src/pages/enrollment/teacher-subjects.astro');
    const reviewPage = readProjectFile('src/pages/management/subject-decisions.astro');

    expect(teacherPage).toContain('Selecciona las ofertas que quieres dictar en este período.');
    expect(reviewPage).toContain('Error de conexión.');
    expect(teacherPage).not.toContain('querés');
    expect(teacherPage).not.toContain('Unexpected error');
    expect(teacherPage).not.toContain('Network error.');
    expect(reviewPage).not.toContain('Unexpected error');
    expect(reviewPage).not.toContain('Network error.');
  });

  it('keeps grouped subject rendering and edit flow hooks visible', () => {
    const enrollmentClasses = readProjectFile('src/pages/enrollment/classes/index.astro');
    const reviewPage = readProjectFile('src/pages/management/subject-decisions.astro');

    expect(enrollmentClasses).toContain('bySubject');
    expect(enrollmentClasses).toContain('subjectClasses');
    // Página de gestión: panel de lista de ofertas + panel de decisiones docentes (se eliminó el concepto de elegibilidad)
    expect(reviewPage).toContain('offerings-list');
    expect(reviewPage).toContain('decisions-panel');
  });
});
