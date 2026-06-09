import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const pagePath = resolve(process.cwd(), 'src/pages/careers/index.astro');

function readPage() {
  return readFileSync(pagePath, 'utf8');
}

describe('careers page load failure handling', () => {
  it('renders a visible error state and retry action', () => {
    const source = readPage();

    expect(source).toContain('id="page-error"');
    expect(source).toContain('id="page-error-message"');
    expect(source).toContain('id="retry-careers-btn"');
  });

  it('surfaces initial load failures instead of swallowing them into an empty table', () => {
    const source = readPage();

    expect(source).toContain('showPageError(');
    expect(source).toContain('throw error;');
    expect(source).toContain('document.getElementById(\'page-content\')?.classList.add(\'hidden\')');
  });

  it('keeps the desktop table while exposing a mobile card list', () => {
    const source = readPage();

    expect(source).toContain('id="careers-mobile-list"');
    expect(source).toContain('md:hidden');
    expect(source).toContain('hidden md:block');
    expect(source).toContain('careers-mobile-card');
  });
});
