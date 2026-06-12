import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

describe('Frontend SSR production runtime contract', () => {
  it('uses the Astro Node runtime instead of nginx in frontend/Dockerfile', () => {
    const content = fs.readFileSync(path.resolve(process.cwd(), 'Dockerfile'), 'utf8');

    expect(content).toContain('FROM node:20-alpine AS production');
    expect(content).toContain('COPY package.json pnpm-lock.yaml ./');
    expect(content).toContain('RUN pnpm install --prod --frozen-lockfile');
    expect(content).toContain('COPY --from=builder /app/dist ./dist');
    expect(content).toContain('CMD ["node", "dist/server/entry.mjs"]');
    expect(content).toContain('EXPOSE 4321');
    expect(content).not.toContain('nginx');
  });

  it('keeps prod compose mapped to the SSR port and health endpoint', () => {
    const compose = fs.readFileSync(path.resolve(process.cwd(), '..', 'docker-compose.prod.yml'), 'utf8');

    expect(compose).toContain('80:4321');
    expect(compose).toContain('http://localhost:4321/health');
  });

  it('proxies same-origin API requests in Astro middleware', () => {
    const middleware = fs.readFileSync(path.resolve(process.cwd(), 'src', 'middleware.ts'), 'utf8');

    expect(middleware).toContain("/api/");
    expect(middleware).toContain("/health");
    expect(middleware).toContain('backend:8000/api');
  });
});
