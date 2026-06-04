from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from admissions.models import AdmissionApplication
from admissions.services.career_resolver import resolve_assigned_preference
from admissions.utils import get_waitlist_admission_expiry


def _reset_preference(pref):
    pref.status = 'rejected'
    pref.is_assigned = False
    pref.waitlist_position = None
    pref.save(update_fields=['status', 'is_assigned', 'waitlist_position'])


def _expire_application(app):
    app.status = 'expired'
    app.assigned_career = None
    app.assigned_preference_order = None
    app.admission_expiry_date = None
    app.save(update_fields=['status', 'assigned_career', 'assigned_preference_order', 'admission_expiry_date', 'updated_at'])


def _reject_application(app):
    app.status = 'rejected'
    app.assigned_career = None
    app.assigned_preference_order = None
    app.admission_expiry_date = None
    app.save(update_fields=['status', 'assigned_career', 'assigned_preference_order', 'admission_expiry_date', 'updated_at'])


def run_admission_expiry_sweep(*, now=None, period_id=None, dry_run=False, batch_size=200):
    now = now or timezone.now()
    result = {'expired': 0, 'reassigned': 0, 'waitlisted_rejected': 0, 'skipped': 0}

    admitted_qs = AdmissionApplication.objects.filter(status='admitted', admission_expiry_date__lte=now)
    if period_id:
        admitted_qs = admitted_qs.filter(academic_period_id=period_id)

    waitlisted_qs = AdmissionApplication.objects.filter(status='waitlisted')
    if period_id:
        waitlisted_qs = waitlisted_qs.filter(academic_period_id=period_id)

    for app in admitted_qs.select_related('assigned_career').prefetch_related('preferences__career')[:batch_size]:
        with transaction.atomic():
            app = AdmissionApplication.objects.select_for_update().get(pk=app.pk)
            if app.status != 'admitted' or not app.admission_expiry_date or app.admission_expiry_date > now:
                result['skipped'] += 1
                continue
            current_pref = app.preferences.filter(status='admitted', career=app.assigned_career).order_by('preference_order', 'pk').first()
            resolved = resolve_assigned_preference(app, excluded_preference_ids=[current_pref.pk] if current_pref else [])
            if resolved is not None and not dry_run:
                if current_pref:
                    _reset_preference(current_pref)
                resolved.status = 'admitted'
                resolved.is_assigned = True
                resolved.waitlist_position = None
                resolved.save(update_fields=['status', 'is_assigned', 'waitlist_position'])
                app.assigned_career = resolved.career
                app.assigned_preference_order = resolved.preference_order
                app.admission_expiry_date = get_waitlist_admission_expiry(now)
                app.save(update_fields=['assigned_career', 'assigned_preference_order', 'admission_expiry_date', 'updated_at'])
                result['reassigned'] += 1
            elif not dry_run:
                if current_pref:
                    _reset_preference(current_pref)
                _expire_application(app)
                result['expired'] += 1

    from notifications.models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    grace_days = settings_obj.admission_waitlist_grace_days
    if grace_days is None:
        grace_days = 7

    for app in waitlisted_qs.select_related('academic_period')[:batch_size]:
        close_date = getattr(app.academic_period, 'admission_close_date', None)
        if not close_date:
            result['skipped'] += 1
            continue
        if close_date + timedelta(days=grace_days) > now:
            continue
        with transaction.atomic():
            app = AdmissionApplication.objects.select_for_update().get(pk=app.pk)
            if app.status != 'waitlisted':
                result['skipped'] += 1
                continue
            if not dry_run:
                app.preferences.filter(status='waitlisted').update(status='rejected', is_assigned=False, waitlist_position=None)
                _reject_application(app)
                result['waitlisted_rejected'] += 1

    return result
