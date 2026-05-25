export type PaginatedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export function normalizePaginatedResponse<T>(payload: unknown): PaginatedResponse<T> {
  if (Array.isArray(payload)) {
    return { count: payload.length, next: null, previous: null, results: payload as T[] };
  }
  const obj = (payload ?? {}) as Record<string, unknown>;
  const results = Array.isArray(obj.results) ? (obj.results as T[]) : [];
  return {
    count: Number(obj.count ?? results.length),
    next: (obj.next as string | null) ?? null,
    previous: (obj.previous as string | null) ?? null,
    results,
  };
}

export function getTotalPages(count: number, pageSize = 20): number {
  return Math.max(1, Math.ceil((count || 0) / pageSize));
}

export function buildPaginatedEndpoint(basePath: string, page: number, filters: Record<string, string> = {}): string {
  const params = new URLSearchParams();
  params.set('page', String(Math.max(1, page)));
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== '') {
      params.set(key, String(value));
    }
  });
  return `${basePath}?${params.toString()}`;
}

export function paginationSummary({ count, currentPage, pageSize = 20 }: { count: number; currentPage: number; pageSize?: number }): string {
  const safeCount = Math.max(0, count || 0);
  const start = safeCount === 0 ? 0 : ((currentPage - 1) * pageSize) + 1;
  const end = Math.min(currentPage * pageSize, safeCount);
  return `Mostrando ${start}-${end} de ${safeCount}`;
}

export function shouldRecoverToLastPage({ count, currentPage, resultsLength, pageSize = 20 }: { count: number; currentPage: number; resultsLength: number; pageSize?: number }): boolean {
  return count > 0 && resultsLength === 0 && currentPage > getTotalPages(count, pageSize);
}
