import { describe, expect, it } from 'vitest';
import {
  buildPaginatedEndpoint,
  getTotalPages,
  normalizePaginatedResponse,
  paginationSummary,
  shouldRecoverToLastPage,
} from '../pagination-utils';

describe('pagination-utils', () => {
  it('normalizes DRF payload and supports legacy array payload', () => {
    const drf = normalizePaginatedResponse({ count: 21, next: 'n', previous: null, results: [{ id: 1 }] });
    expect(drf.count).toBe(21);
    expect(drf.results).toHaveLength(1);

    const legacy = normalizePaginatedResponse([{ id: 1 }, { id: 2 }]);
    expect(legacy.count).toBe(2);
    expect(legacy.next).toBeNull();
    expect(legacy.previous).toBeNull();
  });

  it('builds endpoint preserving filters and replacing page', () => {
    const endpoint = buildPaginatedEndpoint('/academic/subjects/', 2, { career: '3', search: 'abc' });
    expect(endpoint).toContain('page=2');
    expect(endpoint).toContain('career=3');
    expect(endpoint).toContain('search=abc');
  });

  it('computes total pages and summary text', () => {
    expect(getTotalPages(0, 20)).toBe(1);
    expect(getTotalPages(41, 20)).toBe(3);
    expect(paginationSummary({ count: 41, currentPage: 2, pageSize: 20 })).toBe('Mostrando 21-40 de 41');
  });

  it('marks out-of-range page as recoverable when count remains positive', () => {
    expect(shouldRecoverToLastPage({ count: 21, currentPage: 3, resultsLength: 0, pageSize: 20 })).toBe(true);
    expect(shouldRecoverToLastPage({ count: 0, currentPage: 2, resultsLength: 0, pageSize: 20 })).toBe(false);
  });
});
