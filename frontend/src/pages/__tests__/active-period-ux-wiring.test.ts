import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('active-period UX wiring', () => {
  it('wires my-subjects to the shared active-period label helper', () => {
    const page = readProjectFile('src/pages/my-subjects/index.astro');
    expect(page).toContain("import { fetchActivePeriodLabel } from '@/utils/period-display';");
    expect(page).toContain('data-active-period-label');
  });

  it('wires grades and statistics pages to the shared active-period label helper', () => {
    const gradesPage = readProjectFile('src/pages/grades/index.astro');
    const statisticsPage = readProjectFile('src/pages/statistics/index.astro');
    expect(gradesPage).toContain("import { fetchActivePeriodLabel } from '@/utils/period-display';");
    expect(gradesPage).toContain('data-active-period-label');
    expect(statisticsPage).toContain("import { fetchActivePeriodLabel } from '@/utils/period-display';");
    expect(statisticsPage).toContain('data-active-period-label');
  });

  it('keeps my-file historical and without active-period filtering', () => {
    const page = readProjectFile('src/pages/my-file/index.astro');
    expect(page).not.toContain('resolveActivePeriodLabel');
    expect(page).toContain("/grades/my-file/");
  });
});
