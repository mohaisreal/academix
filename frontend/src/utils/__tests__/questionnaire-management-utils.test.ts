import { describe, expect, it } from 'vitest';
import { buildQuestionnaireMobileCards } from '../questionnaire-management-utils';

describe('buildQuestionnaireMobileCards', () => {
  it('normaliza los cuestionarios para tarjetas móviles', () => {
    expect(buildQuestionnaireMobileCards([
      {
        id: 7,
        title: '  Admisión 2025  ',
        description: '  Ingreso general  ',
        flow_type: 'admissions',
        career: 3,
        step_count: 4,
        is_active: true,
        is_preinscripcion_wizard: true,
      },
    ], [{ id: 3, name: 'Ingeniería' }])).toEqual([
      {
        id: 7,
        title: 'Admisión 2025',
        description: 'Ingreso general',
        typeLabel: 'Admisiones',
        typeTone: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
        careerLabel: 'Ingeniería',
        stepCount: 4,
        isActive: true,
        isWizard: true,
      },
    ]);
  });
});
