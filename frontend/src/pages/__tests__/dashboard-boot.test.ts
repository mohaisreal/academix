import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('dashboard boot layout wiring', () => {
  it('injects the API base URL through Astro vars instead of importing it in the inline boot script', () => {
    const layout = readProjectFile('src/layouts/DashboardLayout.astro');

    expect(layout).toContain('<script define:vars={{ apiBaseUrl: API_BASE_URL, forceLightTheme }}>');
    expect(layout).not.toContain("import API_BASE_URL from '@/config/api';");
    expect(layout).not.toContain('const API_URL = API_BASE_URL;');
  });

  it('keeps the post-body startup code browser-safe and able to reveal the dashboard', () => {
    const layout = readProjectFile('src/layouts/DashboardLayout.astro');

    expect(layout).toContain('void (async function boot()');
    expect(layout).toContain('document.body.style.display = "";');
    expect(layout).toContain('window.location.replace("/login");');
    expect(layout).not.toContain('Promise<void>');
  });
});
