import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const pagePath = resolve(process.cwd(), 'src/pages/subject/index.astro');

describe('subject page modal wiring', () => {
  it('removes the single-career field from the edit modal', () => {
    const source = readFileSync(pagePath, 'utf8');

    expect(source).not.toContain('id="subject-career"');
    expect(source).not.toContain('careerSel.value = subject.career || \'\'');
    expect(source).not.toContain('const career = (document.getElementById(\'subject-career\') as HTMLSelectElement).value;');
  });
});
