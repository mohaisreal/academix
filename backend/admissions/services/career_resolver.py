from admissions.models import AdmissionPreference


def resolve_assigned_preference(application, excluded_preference_ids=None):
    excluded_preference_ids = set(excluded_preference_ids or [])
    return (
        application.preferences.select_related('career')
        .filter(status='admitted')
        .exclude(pk__in=excluded_preference_ids)
        .order_by('preference_order', 'pk')
        .first()
    )
