type EnrollmentClassLike = {
  schedule_available?: boolean;
  schedule_unavailable_reason?: string | null;
  schedules?: Array<{ assignment_id?: number | null; source?: string; day_name?: string; day?: string; start_time?: string; end_time?: string }>;
};

export function getEnrollmentClassAvailability(cls: EnrollmentClassLike) {
  if (typeof cls.schedule_available === 'boolean') {
    return {
      available: cls.schedule_available,
      reason: cls.schedule_available ? null : (cls.schedule_unavailable_reason ?? 'schedule_unavailable'),
    };
  }

  const hasCanonicalSchedule = (cls.schedules ?? []).some(
    (schedule) => !!schedule.assignment_id || schedule.source === 'generated',
  );
  return {
    available: hasCanonicalSchedule,
    reason: hasCanonicalSchedule ? null : 'schedule_unavailable',
  };
}

export function getEnrollmentClassAction({ cls, isEnrolled, isFull, isCompleted }: {
  cls: EnrollmentClassLike;
  isEnrolled: boolean;
  isFull: boolean;
  isCompleted: boolean;
}) {
  const availability = getEnrollmentClassAvailability(cls);
  if (isCompleted) return { key: 'none', label: '', disabled: true };
  if (isEnrolled) return { key: 'unenroll', label: 'Quitar', disabled: false };
  if (!availability.available) return { key: 'unavailable', label: 'Sin horario disponible', disabled: true };
  if (isFull) return { key: 'full', label: 'Clase completa', disabled: true };
  return { key: 'enroll', label: 'Seleccionar', disabled: false };
}

export function getScheduleSummaryLabel(schedules: EnrollmentClassLike['schedules'] = []) {
  return schedules
    .map((s) => `${s.day_name ?? s.day ?? ''} ${s.start_time ?? ''}${s.end_time ? `–${s.end_time}` : ''}`.trim())
    .filter(Boolean)
    .join(' · ');
}
