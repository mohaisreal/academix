export const DEFAULT_TOTAL_SPOTS = 100;

export function resolveCareerTotalSpots(totalSpots: unknown): number {
  const parsed = Number(totalSpots);
  if (Number.isInteger(parsed) && parsed >= 0) {
    return parsed;
  }
  return DEFAULT_TOTAL_SPOTS;
}

export function parseValidTotalSpots(rawValue: string): number | null {
  const normalized = rawValue.trim();
  if (normalized.length === 0) {
    return null;
  }

  const parsed = Number(normalized);
  if (!Number.isInteger(parsed) || parsed < 0) {
    return null;
  }

  return parsed;
}
