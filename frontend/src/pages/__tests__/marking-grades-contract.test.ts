import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('marking and grades grading contract', () => {
  it('removes quiz, uses datetime-local, and wires file submission toggles on marking', () => {
    const marking = readProjectFile('src/pages/marking/index.astro');

    expect(marking).not.toContain('<option value="quiz">Cuestionario</option>');
    expect(marking).toContain('type="datetime-local"');
    expect(marking).toContain('allows_file_submission');
    expect(marking).toContain('data-testid="evaluation-file-toggle"');
    expect(marking).toContain('data-testid="evaluation-submission-status"');
    expect(marking).toContain('submission_file_url');
    expect(marking).toContain('submission_file_name');
  });

  it('renders datetime, upload wiring, and authoritative submission states on grades', () => {
    const grades = readProjectFile('src/pages/grades/index.astro');

    expect(grades).not.toContain("quiz: 'bg-blue-500/15 text-blue-400'");
    expect(grades).toContain("toLocaleString('es-ES'");
    expect(grades).toContain('allows_file_submission');
    expect(grades).toContain('submission_status');
    expect(grades).toContain('data-testid="grade-submission-status"');
    expect(grades).toContain('data-eval-row');
    expect(grades).toContain('eval-upload-input');
    expect(grades).toContain('eval-upload-btn');
    expect(grades).toContain('closest(\'[data-eval-row]\')');
    expect(grades).toContain('row?.querySelector(`.eval-upload-input[data-eval-id="${evalId}"]`)');
    expect(grades).toContain('Entregado');
    expect(grades).toContain('Pendiente');
    expect(grades).toContain('/grades/evaluations/${evalId}/submissions/');
  });

  it('exposes is_hidden and min_score controls and a PATCH path for editing', () => {
    const marking = readProjectFile('src/pages/marking/index.astro');

    expect(marking).toContain('data-testid="evaluation-hidden-toggle"');
    expect(marking).toContain('data-testid="evaluation-min-score"');
    expect(marking).toMatch(/PATCH/);
    expect(marking).toMatch(/evaluations\/\$\{/);
  });

  it('handles the warnings array returned by the API after create/edit', () => {
    const marking = readProjectFile('src/pages/marking/index.astro');

    expect(marking).toMatch(/data\??\.warnings/);
    expect(marking).toContain('toast.warning');
  });

  it('renders edit and delete affordances and an "Oculta" badge for hidden evaluations', () => {
    const marking = readProjectFile('src/pages/marking/index.astro');

    expect(marking).toContain('data-testid="evaluation-edit-btn"');
    expect(marking).toContain('data-testid="evaluation-delete-btn"');
    expect(marking).toContain('Oculta');
    expect(marking).toContain('e.is_hidden');
  });

  it('shares the create/edit modal: title and submit label switch by mode', () => {
    const marking = readProjectFile('src/pages/marking/index.astro');

    expect(marking).toContain("modalMode === 'edit'");
    expect(marking).toContain('Editar evaluación');
    expect(marking).toContain('Nueva evaluación');
    expect(marking).toContain("'Guardar'");
    expect(marking).toContain("'Crear'");
    // POST for create, PATCH for edit, against the same form
    expect(marking).toContain("method = isEdit ? 'PATCH' : 'POST'");
    expect(marking).toMatch(/apiFetchWithStatus\(path,\s*\{\s*method,/);
  });

  it('declares Europe/Madrid as the display timezone for due dates on both pages', () => {
    const marking = readProjectFile('src/pages/marking/index.astro');
    const grades = readProjectFile('src/pages/grades/index.astro');

    expect(marking).toMatch(/formatDateTime[\s\S]*?timeZone:\s*'Europe\/Madrid'/);
    expect(grades).toMatch(/formatDateTime[\s\S]*?timeZone:\s*'Europe\/Madrid'/);
  });

  it('provides a datetime-local prefill helper for the edit form that targets Europe/Madrid', () => {
    const marking = readProjectFile('src/pages/marking/index.astro');

    expect(marking).toContain('toDatetimeLocalValue');
    expect(marking).toMatch(/toDatetimeLocalValue[\s\S]*?Europe\/Madrid/);
    expect(marking).toContain('eval-due-date');
  });
});
