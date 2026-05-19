import { describe, expect, it } from 'vitest';
import {
  buildUsersListEndpoint,
  getTotalPages,
  shouldRecoverToLastPage,
  resetPageOnFilterChange,
} from '../users-page-utils';

describe('buildUsersListEndpoint', () => {
  it('incluye page/search/role en query params', () => {
    expect(buildUsersListEndpoint({ page: 2, search: 'ana', role: 't' })).toBe('/users/?page=2&search=ana&role=t');
  });

  it('omite filtros vacíos y mantiene page', () => {
    expect(buildUsersListEndpoint({ page: 3, search: '  ', role: '' })).toBe('/users/?page=3');
  });
});

describe('getTotalPages', () => {
  it('calcula total de páginas según page size', () => {
    expect(getTotalPages(41, 20)).toBe(3);
  });

  it('retorna 1 cuando no hay resultados', () => {
    expect(getTotalPages(0, 20)).toBe(1);
  });
});

describe('shouldRecoverToLastPage', () => {
  it('recupera cuando una página alta queda vacía pero hay resultados', () => {
    expect(shouldRecoverToLastPage({ requestedPage: 4, count: 21, resultsLength: 0, pageSize: 20 })).toBe(true);
  });

  it('no recupera cuando está en página 1 o cuando no hay resultados', () => {
    expect(shouldRecoverToLastPage({ requestedPage: 1, count: 21, resultsLength: 0, pageSize: 20 })).toBe(false);
    expect(shouldRecoverToLastPage({ requestedPage: 3, count: 0, resultsLength: 0, pageSize: 20 })).toBe(false);
  });
});

describe('resetPageOnFilterChange', () => {
  it('resetea a página 1 cuando cambia search o role', () => {
    expect(resetPageOnFilterChange({ currentPage: 5, prevSearch: '', nextSearch: 'ana', prevRole: '', nextRole: '' })).toBe(1);
    expect(resetPageOnFilterChange({ currentPage: 5, prevSearch: 'ana', nextSearch: 'ana', prevRole: 's', nextRole: 'a' })).toBe(1);
  });

  it('mantiene página cuando no cambian filtros', () => {
    expect(resetPageOnFilterChange({ currentPage: 3, prevSearch: 'ana', nextSearch: 'ana', prevRole: 't', nextRole: 't' })).toBe(3);
  });
});
