import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('enrollment teacher consumer alignment', () => {
  it('renders my-enrolment from canonical teacher_name only', () => {
    const page = readProjectFile('src/pages/my-enrolment/index.astro');
    expect(page).toContain("const teacher = c.teacher_name || '-';");
    expect(page).not.toContain('c.teacher?.full_name');
  });

  it('renders my-subjects from canonical teacher_name only', () => {
    const page = readProjectFile('src/pages/my-subjects/index.astro');
    expect(page).toContain("const teacher = s.teacher_name || 'Profesor desconocido';");
    expect(page).not.toContain('s.teacher ||');
  });

  it('renders receipt teacher labels from canonical teacher_name only', () => {
    const page = readProjectFile('src/pages/enrollment/receipt/[id].astro');
    expect(page).toContain('cls.teacher_name ?? ""');
    expect(page).not.toContain('cls.teacher?.full_name');
  });
});
