import { describe, expect, it } from 'vitest';
import { resolveApiBaseUrl, resolveWebSocketBaseUrl } from '../api';

describe('resolveApiBaseUrl', () => {
  it('usa /api por defecto cuando no hay env', () => {
    expect(resolveApiBaseUrl({ MODE: 'development' })).toBe('/api');
  });

  it('usa /api en production cuando no hay env', () => {
    expect(resolveApiBaseUrl({ MODE: 'production', DEV: false })).toBe('/api');
  });

  it('prioriza PUBLIC_API_URL sobre BACKEND_API_URL', () => {
    expect(
      resolveApiBaseUrl({
        BACKEND_API_URL: 'http://backend:8000/api',
        PUBLIC_API_URL: '/api',
        MODE: 'production',
      }),
    ).toBe('/api');
  });

  it('usa BACKEND_API_URL cuando PUBLIC_API_URL no existe', () => {
    expect(
      resolveApiBaseUrl({
        BACKEND_API_URL: 'http://backend:8000/api',
        MODE: 'production',
      }),
    ).toBe('http://backend:8000/api');
  });

  it('usa ws://localhost:8000 para websocket en desarrollo cuando la API es relativa', () => {
    expect(resolveWebSocketBaseUrl({ MODE: 'development', DEV: true })).toBe('ws://localhost:8000');
  });

  it('convierte https a wss para websocket', () => {
    expect(resolveWebSocketBaseUrl({ PUBLIC_API_URL: 'https://portal.example.edu/api' })).toBe('wss://portal.example.edu');
  });
});
