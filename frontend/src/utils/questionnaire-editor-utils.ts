export const QUESTION_ID_BADGE_CLASS =
  'inline-flex items-center rounded-full border border-border bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground';

export function formatQuestionIdBadge(id: number | null | undefined): string {
  return `ID: ${id ?? '—'}`;
}
