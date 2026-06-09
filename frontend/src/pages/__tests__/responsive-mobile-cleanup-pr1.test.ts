import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('responsive mobile cleanup PR1', () => {
  it('adds mobile dropdown filters while keeping desktop tabs on notifications and materials', () => {
    const notifications = readProjectFile('src/pages/notifications/index.astro');
    const materials = readProjectFile('src/pages/my-materials/index.astro');

    expect(notifications).toContain('id="notification-filter-mobile"');
    expect(notifications).toContain('md:hidden');
    expect(notifications).toContain('hidden gap-1 border-b border-border md:flex');
    expect(notifications).toContain('syncNotificationFilter');

    expect(materials).toContain('id="class-filter-mobile"');
    expect(materials).toContain('md:hidden');
    expect(materials).toContain('hidden gap-1 overflow-x-auto pb-1 border-b border-border md:flex');
    expect(materials).toContain('syncClassFilter');
  });

  it('adds a mobile teacher card layout while preserving the desktop table', () => {
    const teachers = readProjectFile('src/pages/my-teachers/index.astro');

    expect(teachers).toContain('id="teachers-cards"');
    expect(teachers).toContain('md:hidden');
    expect(teachers).toContain('hidden overflow-x-auto md:block');
    expect(teachers).toContain('renderTeacherCards(teachers)');
    expect(teachers).toContain('Enviar mensaje');
  });

  it('adds mobile cards for enrolment, files, and my classes while preserving desktop tables', () => {
    const enrolment = readProjectFile('src/pages/my-enrolment/index.astro');
    const files = readProjectFile('src/pages/files/index.astro');
    const myClasses = readProjectFile('src/pages/my-classes/index.astro');

    expect(enrolment).toContain('id="classes-cards"');
    expect(enrolment).toContain('md:hidden');
    expect(enrolment).toContain('hidden overflow-x-auto md:block');
    expect(enrolment).toContain('renderClassesCards(classes)');

    expect(files).toContain('id="files-cards"');
    expect(files).toContain('md:hidden');
    expect(files).toContain('hidden overflow-x-auto md:block');
    expect(files).toContain('renderFilesCards(files)');
    expect(files).toContain('view-file-btn');

    expect(myClasses).toContain('id="classes-cards"');
    expect(myClasses).toContain('md:hidden');
    expect(myClasses).toContain('hidden overflow-x-auto md:block');
    expect(myClasses).toContain('renderClassCards(classes)');
  });

  it('adds a mobile subject selector and optional class handling on grades', () => {
    const grades = readProjectFile('src/pages/grades/index.astro');

    expect(grades).toContain('id="subject-selector"');
    expect(grades).toContain('md:hidden');
    expect(grades).toContain('hidden gap-1 overflow-x-auto pb-2 mb-4 border-b border-border md:flex');
    expect(grades).toContain('space-y-4 md:hidden');
    expect(grades).toContain('hidden overflow-x-auto md:block');
    expect(grades).toContain('classQueryParam');
    expect(grades).toContain('selectedClassId');
    expect(grades).toContain('activateSubject(`panel-${selectedIdx}`, selectedClassId)');
  });
});
