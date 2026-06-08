export type ActivePeriodLike = {
  id?: number | string | null;
  name?: string | null;
  code?: string | null;
  is_active?: boolean | null;
  active?: boolean | null;
};

export function resolveActivePeriodLabel(periods: ActivePeriodLike[] = []): string {
  const active = periods.find((period) => period?.is_active || period?.active);
  const fallback = periods.find((period) => period?.name || period?.code);
  return active?.name || active?.code || fallback?.name || fallback?.code || 'Periodo activo';
}

export async function fetchActivePeriodLabel(
  fetcher: (path: string, options?: Record<string, unknown>) => Promise<any>,
): Promise<string> {
  try {
    const data = await fetcher('/academic/periods/');
    const periods = Array.isArray(data) ? data : (data?.results || []);
    return resolveActivePeriodLabel(periods);
  } catch {
    return 'Periodo activo';
  }
}
