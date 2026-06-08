import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('enrollment receipt light theme path', () => {
  it('forces the dashboard layout into light mode for the receipt route', () => {
    const page = readProjectFile('src/pages/enrollment/receipt/[id].astro');

    expect(page).toContain('forceLightTheme={true}');
    expect(page).toContain('Imprimir comprobante');
    expect(page).toContain('@media print');
    expect(page).toContain('#receipt-content, #receipt-content *');
    expect(page).not.toContain('text-emerald-400');
  });

  it('keeps the layout theme bootstrap aware of forced light rendering', () => {
    const layout = readProjectFile('src/layouts/DashboardLayout.astro');

    expect(layout).toContain('forceLightTheme?: boolean;');
    expect(layout).toContain('define:vars={{ forceLightTheme }}');
    expect(layout).toContain('applyTheme(forceLightTheme ? "light"');
    expect(layout).toContain('if (!forceLightTheme) {');
  });
});
