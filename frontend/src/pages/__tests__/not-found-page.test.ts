import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('404 page', () => {
  it('is a standalone Astro page without DashboardLayout', () => {
    const page = readProjectFile('src/pages/404.astro');

    expect(page).not.toContain('DashboardLayout');
    expect(page).toContain('<html lang="es">');
    expect(page).toContain('Página no encontrada');
    expect(page).toContain('href="/"');
  });
});
