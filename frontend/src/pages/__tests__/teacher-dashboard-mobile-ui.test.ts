import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('teacher dashboard mobile UI', () => {
  it('preserves the desktop table and adds mobile cards', () => {
    const page = readProjectFile('src/pages/index.astro');

    expect(page).toContain('id="tch-classes-cards"');
    expect(page).toContain('hidden overflow-x-auto md:block');
    expect(page).toContain('visibleClasses.map((c: any) => {');
    expect(page).toContain('Calificar');
  });
});
