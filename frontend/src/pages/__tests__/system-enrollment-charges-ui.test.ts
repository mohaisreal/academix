import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('system enrollment extra charges visual editor', () => {
  it('reemplaza textarea JSON por editor visual con IDs esperados', () => {
    const systemPage = readProjectFile('src/pages/system/index.astro');

    expect(systemPage).not.toContain('id="enrollment-extra-charges"');
    expect(systemPage).toContain('id="extra-charges-list"');
    expect(systemPage).toContain('id="extra-charges-empty"');
    expect(systemPage).toContain('id="add-extra-charge"');
    expect(systemPage).toContain('data-extra-charge-row');
  });

  it('mantiene el control de días de gracia y su wiring de guardado en /system', () => {
    const systemPage = readProjectFile('src/pages/system/index.astro');

    expect(systemPage).toContain('id="admission-waitlist-grace-days"');
    expect(systemPage).toContain('data.admission_waitlist_grace_days ?? 7');
    expect(systemPage).toContain('id="save-grace-days"');
    expect(systemPage).toContain('admission_waitlist_grace_days: Number(value)');
    expect(systemPage).toContain('apiFetch(\'/notifications/system-settings/\'');
  });
});
