import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

describe('Astro production adapter config', () => {
  it('declares the Node adapter and hybrid output in astro.config.mjs', () => {
    const configPath = path.resolve(process.cwd(), 'astro.config.mjs');
    const content = fs.readFileSync(configPath, 'utf8');

    expect(content).toContain("from '@astrojs/node';");
    expect(content).toContain('adapter: node({');
    expect(content).toContain("output: 'server'");
  });
});
