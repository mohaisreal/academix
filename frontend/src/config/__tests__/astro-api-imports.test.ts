import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

function listAstroFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const fullPath = join(dir, entry);
    const stat = statSync(fullPath);
    if (stat.isDirectory()) return listAstroFiles(fullPath);
    return entry.endsWith('.astro') ? [fullPath] : [];
  });
}

describe('Astro API base URL imports', () => {
  it('keeps API_BASE_URL out of frontmatter across frontend pages', () => {
    const astroFiles = listAstroFiles(join(process.cwd(), 'src/pages'));

    for (const file of astroFiles) {
      const content = readFileSync(file, 'utf8');
      const frontmatter = content.startsWith('---') ? content.slice(3, content.indexOf('---', 3)) : '';
      expect(frontmatter).not.toContain("import API_BASE_URL from '@/config/api';");
    }
  });
});
