/**
 * Test setup file for Vitest
 * This file is run before all tests
 */

import { beforeAll, afterEach } from 'vitest';

// Mock localStorage
const localStorageMock = {
  getItem: (key: string) => null,
  setItem: (key: string, value: string) => {},
  removeItem: (key: string) => {},
  clear: () => {},
  key: (index: number) => null,
  length: 0,
};

// Setup global mocks
beforeAll(() => {
  Object.defineProperty(global, 'localStorage', {
    value: localStorageMock,
    writable: true,
  });
});

// Clean up after each test
afterEach(() => {
  // Reset localStorage
  if (global.localStorage) {
    (global.localStorage as any).clear();
  }
});
