from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from notifications.models import SystemSettings
from notifications.utils import create_notification


def get_waitlist_admission_expiry(now=None):
    now = now or timezone.now()
    system_settings, _ = SystemSettings.objects.get_or_create(pk=1)
    grace_days = system_settings.admission_waitlist_grace_days or getattr(
        settings, 'ADMISSION_WAITLIST_GRACE_DAYS', 7
    )
    return now + timedelta(days=grace_days)


def get_current_admission_period(now=None):
    from academic.models import AcademicPeriod

    now = now or timezone.now()
    return (
        AcademicPeriod.objects.filter(admission_open_date__lte=now, admission_close_date__gte=now)
        .order_by('-admission_open_date')
        .first()
    )


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


def notify_next_waitlisted(career, academic_period, now=None):
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
    now = now or timezone.now()
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
    app.admission_expiry_date = get_waitlist_admission_expiry(now)
    app.save(update_fields=['status', 'assigned_career', 'assigned_preference_order', 'admission_expiry_date', 'updated_at'])

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
