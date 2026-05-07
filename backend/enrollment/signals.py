from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import CareerEnrollment


@receiver(post_save, sender=CareerEnrollment)
def assign_student_id_on_first_enrollment(sender, instance, created, **kwargs):
    """
    Generate and assign a permanent student ID (username) the first time a
    student gets a CareerEnrollment.  Only runs when:
      - the enrollment was just created (created=True)
      - the student's username is still their email (contains '@'), meaning no
        ID has been assigned yet
      - this is indeed their first enrollment
    """
    if not created:
        return

    student = instance.student
    if '@' not in student.username:
        return  # ya tiene un identificador permanente de estudiante

    # Comprueba de nuevo que realmente sea la primera matrícula
    if CareerEnrollment.objects.filter(student=student).count() > 1:
        return

    try:
        from notifications.models import SystemSettings
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
        fmt = settings_obj.student_id_format or r'\d{6}'
    except Exception:
        fmt = r'\d{6}'

    from users.serializers import _unique_student_id
    student.username = _unique_student_id(fmt)
    student.save(update_fields=['username'])
