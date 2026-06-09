import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('enrollment classes convocation UI', () => {
  it('renders grace and blocked states visibly', () => {
    const page = readProjectFile('src/pages/enrollment/classes/index.astro');

    expect(page).toContain('Seleccionar');
    expect(page).toContain('Caso excepcional');
    expect(page).toContain('Límite de convocatorias alcanzado');
    expect(page).toContain("convocationEligibility === 'extraordinary-grace'");
    expect(page).toContain("convocationEligibility === 'blocked'");
  });

  it('keeps the timetable responsive with a mobile card rail', () => {
    const page = readProjectFile('src/pages/enrollment/classes/index.astro');

    expect(page).toContain('hidden overflow-x-auto md:block');
    expect(page).toContain('id="schedule-cards"');
    expect(page).toContain('renderScheduleCards(enrolledClasses)');
  });
});
