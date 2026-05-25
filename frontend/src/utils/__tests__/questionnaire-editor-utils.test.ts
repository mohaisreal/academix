import { describe, expect, it } from 'vitest';
import { formatQuestionIdBadge, QUESTION_ID_BADGE_CLASS } from '../questionnaire-editor-utils';

describe('formatQuestionIdBadge', () => {
  it('muestra el id persistido cuando existe', () => {
    expect(formatQuestionIdBadge(42)).toBe('ID: 42');
  });

  it('usa fallback cuando id es null o undefined', () => {
    expect(formatQuestionIdBadge(null)).toBe('ID: —');
    expect(formatQuestionIdBadge(undefined)).toBe('ID: —');
  });
});

describe('QUESTION_ID_BADGE_CLASS', () => {
  it('mantiene estilo neutral y discreto', () => {
    expect(QUESTION_ID_BADGE_CLASS).toContain('bg-muted');
    expect(QUESTION_ID_BADGE_CLASS).toContain('text-muted-foreground');
    expect(QUESTION_ID_BADGE_CLASS).toContain('border-border');
  });
});
