from academic.models import AcademicPeriod


def get_active_academic_period():
    return AcademicPeriod.objects.filter(is_active=True).order_by('-start_date', '-id').first()
