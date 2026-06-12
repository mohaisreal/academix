import { describe, expect, it } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

function readEnvFile(fileName: string): Record<string, string> {
  const fullPath = path.resolve(process.cwd(), '..', fileName);
  const content = fs.readFileSync(fullPath, 'utf8');
  const lines = content.split(/\r?\n/);
  const result: Record<string, string> = {};

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim();
    const value = line.slice(eq + 1).trim();
    result[key] = value;
  }

  return result;
}

describe('ENV contract root files', () => {
  it('.env.dev incluye variables frontend/backend requeridas', () => {
    const env = readEnvFile('.env.dev');
    const required = [
      'PUBLIC_API_URL',
      'BACKEND_API_URL',
      'FRONTEND_URL',
      'DATABASE_PATH',
      'STRIPE_SECRET_KEY',
      'STRIPE_PUBLIC_KEY',
      'STRIPE_WEBHOOK_SECRET',
    ];

    for (const key of required) {
      expect(env[key], `missing key: ${key}`).toBeDefined();
    }

    expect(env.PUBLIC_API_URL).toBe('http://localhost:8000/api');
  });

  it('.env.prod usa el dominio academix.cv y proxy relativo para frontend', () => {
    const env = readEnvFile('.env.prod');
    expect(env.ALLOWED_HOSTS).toBe('academix.cv');
    expect(env.CORS_ALLOWED_ORIGINS).toBe('https://academix.cv');
    expect(env.CSRF_TRUSTED_ORIGINS).toBe('https://academix.cv');
    expect(env.FRONTEND_URL).toBe('https://academix.cv');
    expect(env.PUBLIC_API_URL).toBe('/api');
    expect(env.BACKEND_API_URL).toBe('http://backend:8000/api');
    expect(env.ALLOWED_HOSTS).not.toContain('localhost');
  });

  it('.env.prod.example mantiene placeholders seguros para secretos de producción', () => {
    const env = readEnvFile('.env.prod.example');
    expect(env.AWS_ACCESS_KEY_ID).toBe('replace-with-aws-access-key');
    expect(env.AWS_SECRET_ACCESS_KEY).toBe('replace-with-aws-secret-key');
    expect(env.POSTGRES_PASSWORD).toBe('replace-with-strong-password');
    expect(env.EMAIL_HOST_USER).toBe('');
    expect(env.EMAIL_HOST_PASSWORD).toBe('');
    expect(env.STRIPE_SECRET_KEY).toBe('');
    expect(env.STRIPE_PUBLIC_KEY).toBe('');
  });

  it('.env.prod incluye conexión AWS/S3 para archivos', () => {
    const env = readEnvFile('.env.prod');
    const required = [
      'AWS_ACCESS_KEY_ID',
      'AWS_SECRET_ACCESS_KEY',
      'AWS_STORAGE_BUCKET_NAME',
      'AWS_S3_REGION_NAME',
    ];

    for (const key of required) {
      expect(env[key], `missing key: ${key}`).toBeDefined();
    }
  });
});

describe('Frontend dev server host config', () => {
  it('permite academix.cv en Astro/Vite sin crear vite.config.js', () => {
    const configPath = path.resolve(process.cwd(), 'astro.config.mjs');
    const content = fs.readFileSync(configPath, 'utf8');

    expect(content).toContain('server:');
    expect(content).toContain('host: true');
    expect(content).toContain('port: 4321');
    expect(content).toContain('academix.cv');
    expect(content).toContain('localhost');
    expect(content).toContain('127.0.0.1');
    expect(content).toContain('::1');
    expect(content).not.toContain('vite.config.js');
  });
});

describe('Regression fallback localhost en frontend', () => {
  it('no deja fallback inline localhost:8000/api en src', () => {
    const srcDir = path.resolve(process.cwd(), 'src');
    const filesToScan: string[] = [];

    function walk(dir: string) {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          if (entry.name === '__tests__') continue;
          walk(full);
          continue;
        }
        if (/\.(astro|ts|tsx)$/.test(entry.name)) filesToScan.push(full);
      }
    }

    walk(srcDir);
    const offenders: string[] = [];
    for (const file of filesToScan) {
      const content = fs.readFileSync(file, 'utf8');
      if (content.includes('http://localhost:8000/api')) offenders.push(file);
    }

    expect(offenders).toEqual([]);
  });
});
