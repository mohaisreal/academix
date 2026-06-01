from notifications.utils import create_notification


def compact_waitlist_positions(career, academic_period):
    """
    Recalcula las posiciones de espera publicadas para una carrera/periodo.
    Las solicitudes retiradas, admitidas o rechazadas quedan fuera de la lista.
    """
    from admissions.models import AdmissionPreference

    remaining = AdmissionPreference.objects.filter(
        career=career,
        application__academic_period=academic_period,
        status='waitlisted',
    ).order_by('waitlist_position', 'rank_position', '-ranking_score', 'application__submission_date')

    for index, pref in enumerate(remaining, start=1):
        if pref.waitlist_position != index:
            pref.waitlist_position = index
            pref.save(update_fields=['waitlist_position'])


def notify_next_waitlisted(career, academic_period):
    """
    Promueve y notifica al primer estudiante en lista de espera para la
    carrera/periodo dado.
    """
    from admissions.models import AdmissionPreference

    next_pref = (
        AdmissionPreference.objects.select_related('application__student', 'career')
        .filter(
            career=career,
            application__academic_period=academic_period,
            status='waitlisted',
        )
        .order_by('waitlist_position', 'rank_position', '-ranking_score', 'application__submission_date')
        .first()
    )

    if not next_pref:
        return None

    app = next_pref.application
    next_pref.status = 'admitted'
    next_pref.waitlist_position = None
    next_pref.is_assigned = True
    next_pref.save(update_fields=['status', 'waitlist_position', 'is_assigned'])

    admitted_pref = (
        app.preferences
        .filter(status='admitted')
        .order_by('preference_order')
        .first()
    )
    app.status = 'admitted'
    app.assigned_career = admitted_pref.career if admitted_pref else career
    app.assigned_preference_order = admitted_pref.preference_order if admitted_pref else next_pref.preference_order
    app.save(update_fields=['status', 'assigned_career', 'assigned_preference_order', 'updated_at'])

    # Compactar posiciones restantes para que la lista sea realmente fluctuante.
    compact_waitlist_positions(career, academic_period)

    create_notification(
        user=app.student,
        title='Plaza disponible',
        message=f'Se ha liberado una plaza para {career.name}. Tu solicitud pasa a admitida.',
        notif_type='info',
        event_type='waitlist',
    )
    return next_pref
