import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

function readProjectFile(relativePath: string): string {
  return readFileSync(resolve(process.cwd(), relativePath), 'utf-8');
}

describe('grades display and final-grade editing contract', () => {
  it('renders /my-subjects progress as 0-10 text with fixed color bands', () => {
    const page = readProjectFile('src/pages/my-subjects/index.astro');

    expect(page).toContain("const gradeDisplay = grade != null ? `${parseFloat(grade).toFixed(1)} / 10` : 'Sin calificar todavía';");
    expect(page).toContain("const progressColor = grade == null ? 'bg-muted' : parseFloat(grade) >= 7 ? 'bg-green-500' : parseFloat(grade) >= 5 ? 'bg-yellow-500' : 'bg-red-500';");
  });

  it('renders /grades KPI cards as three-column grid with renamed final-grade label', () => {
    const page = readProjectFile('src/pages/grades/index.astro');

    expect(page).toContain('class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3"');
    expect(page).toContain('class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3" id="kpi-row"');
    expect(page).toContain("{ label: 'Notas finales', value: String(visibleFinals.length), color: 'text-primary', icon: '<path d=\"M12 20V10\"/><path d=\"M18 20V4\"/><path d=\"M6 20v-4\"/>' }");
  });

  it('renders the /my-students final-grade editor with per-class expand rows and clear confirmation', () => {
    const page = readProjectFile('src/pages/my-students/index.astro');

    expect(page).toContain('id="class-filter"');
    expect(page).toContain('id="students-table-body"');
    expect(page).toContain('data-student-row');
    expect(page).toContain('data-class-row');
    expect(page).toContain('data-testid="final-grade-input"');
    expect(page).toContain('data-testid="save-final-grade-btn"');
    expect(page).toContain('data-testid="clear-final-grade-btn"');
    expect(page).toContain("/grades/classes/${classId}/students/${studentId}/final-grade/");
    expect(page).toContain('window.confirm');
    expect(page).toContain('window.alert(message);');
    expect(page).toContain('if (!Number.isFinite(score) || score < 0 || score > 10)');
    expect(page).toContain('updateStudentFinalGrade(studentId, classId, response, action, input?.value ?? null);');
  });
});
