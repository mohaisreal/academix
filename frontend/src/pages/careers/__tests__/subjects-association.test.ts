import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const pagePath = resolve(process.cwd(), 'src/pages/careers/index.astro');

describe('careers page subject associations', () => {
  it('renders and submits shared subject associations', () => {
    const source = readFileSync(pagePath, 'utf8');

    expect(source).toContain('id="career-subjects"');
    expect(source).toContain('subject_ids');
    expect(source).toContain('loadAllSubjects()');
  });
});
