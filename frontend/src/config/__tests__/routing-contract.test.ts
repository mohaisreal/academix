import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

describe('Localhost routing contract', () => {
  it('keeps /login owned by the frontend and /api/* delegated to Django', () => {
    const loginPage = fs.readFileSync(path.resolve(process.cwd(), 'src', 'pages', 'login', 'index.astro'), 'utf8');
    const middleware = fs.readFileSync(path.resolve(process.cwd(), 'src', 'middleware.ts'), 'utf8');

    expect(loginPage).toContain('<title>Iniciar sesión — Academix</title>');
    expect(loginPage).not.toContain('/api/');
    expect(middleware).toContain("if (!context.url.pathname.startsWith('/api/')) {");
    expect(middleware).toContain("const backendApiBaseUrl = (import.meta.env.BACKEND_API_URL ?? 'http://backend:8000/api').replace(/\\/$/, '');");
    expect(middleware).toContain("const apiPath = context.url.pathname.slice('/api'.length) || '/';");
  });
});
