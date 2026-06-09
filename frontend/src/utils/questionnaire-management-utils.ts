export type QuestionnaireLike = {
  id: number;
  title?: string | null;
  description?: string | null;
  flow_type?: string | null;
  career?: number | null;
  career_name?: string | null;
  steps?: Array<unknown> | null;
  step_count?: number | null;
  is_active?: boolean | null;
  is_preinscripcion_wizard?: boolean | null;
};

export type QuestionnaireCareerLike = { id: number; name?: string | null };

export type QuestionnaireMobileCard = {
  id: number;
  title: string;
  description: string;
  typeLabel: string;
  typeTone: string;
  careerLabel: string;
  stepCount: number;
  isActive: boolean;
  isWizard: boolean;
};

export function buildQuestionnaireMobileCards(items: QuestionnaireLike[], careers: QuestionnaireCareerLike[] = []): QuestionnaireMobileCard[] {
  return items.map((q) => {
    const typeLabel = q.flow_type === 'admissions' ? 'Admisiones' : 'Matrícula';
    const typeTone = q.flow_type === 'admissions'
      ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
      : 'bg-violet-500/10 text-violet-400 border-violet-500/20';
    const careerLabel = q.career_name ?? careers.find((c) => Number(c.id) === Number(q.career))?.name ?? '—';

    return {
      id: q.id,
      title: String(q.title ?? '').trim() || 'Sin título',
      description: String(q.description ?? '').trim(),
      typeLabel,
      typeTone,
      careerLabel: String(careerLabel ?? '—').trim() || '—',
      stepCount: Number(q.steps?.length ?? q.step_count ?? 0),
      isActive: Boolean(q.is_active),
      isWizard: Boolean(q.is_preinscripcion_wizard),
    };
  });
}
