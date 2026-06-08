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

    expect(teacherPage).toContain('teacher-subject-selection-form');
    expect(teacherPage).toContain('teacher-subject-selection-submit-btn');
    expect(reviewPage).toContain('subject-decisions-list');
    expect(reviewPage).toContain('subject-eligibility-editor');
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

  it('keeps grouped subject rendering and edit flow hooks visible', () => {
    const enrollmentClasses = readProjectFile('src/pages/enrollment/classes/index.astro');
    const reviewPage = readProjectFile('src/pages/management/subject-decisions.astro');

    expect(enrollmentClasses).toContain('bySubject');
    expect(enrollmentClasses).toContain('subjectClasses');
    expect(reviewPage).toContain('subject-eligibility-editor');
    expect(reviewPage).toContain('subject-decisions-list');
  });
});
