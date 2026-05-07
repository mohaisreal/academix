/**
 * Fichero de configuración de pruebas para Vitest
 * Este fichero se ejecuta antes de todas las pruebas
 */
import { beforeAll, afterEach } from 'vitest';

// Simula localStorage
const localStorageMock = {
  getItem: (key: string) => null,
  setItem: (key: string, value: string) => {},
  removeItem: (key: string) => {},
  clear: () => {},
  key: (index: number) => null,
  length: 0,
};

// Configura los mocks globales
beforeAll(() => {
  Object.defineProperty(global, 'localStorage', {
    value: localStorageMock,
    writable: true,
  });
});

// Limpia después de cada prueba
afterEach(() => {
  // Reinicia localStorage
  if (global.localStorage) {
    (global.localStorage as any).clear();
  }
});
