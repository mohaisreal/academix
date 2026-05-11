from django.db import models
from django.db.models import Q
from django.conf import settings


class CareerEnrollment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('dropped', 'Dropped'),
    ]
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 's'},
        related_name='career_enrollments',
    )
    career = models.ForeignKey(
        'academic.Career', on_delete=models.CASCADE, related_name='enrollments'
    )
    period = models.ForeignKey(
        'academic.AcademicPeriod', on_delete=models.CASCADE, related_name='enrollments'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'career', 'period']
        ordering = ['-enrolled_at']

    def __str__(self):
        return f"{self.student.username} → {self.career.name} ({self.period.name})"


class ClassEnrollment(models.Model):
    STATUS_CHOICES = [
        ('enrolled', 'Enrolled'),
        ('dropped', 'Dropped'),
        ('waitlisted', 'Waitlisted'),
    ]
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 's'},
        related_name='class_enrollments',
    )
    cls = models.ForeignKey(
        'academic.Class', on_delete=models.CASCADE, related_name='enrollments'
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='enrolled')
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'cls']
        ordering = ['-enrolled_at']

    def __str__(self):
        return f"{self.student.username} in {self.cls}"


class EnrollmentFee(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('exempted', 'Exempted'),
        ('failed', 'Fallido'),
    ]
    career_enrollment = models.OneToOneField(
        CareerEnrollment,
        on_delete=models.CASCADE,
        related_name='fee',
    )
    base_amount = models.DecimalField(max_digits=8, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    discount_reason = models.CharField(max_length=200, blank=True)
    final_amount = models.DecimalField(max_digits=8, decimal_places=2)
    line_items = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    paid_at = models.DateTimeField(null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    stripe_payment_status = models.CharField(max_length=20, blank=True, default='')

    class Meta:
        ordering = ['-career_enrollment__enrolled_at']

    def __str__(self):
        return f"Fee for {self.career_enrollment} — {self.status}"


class StudentBenefit(models.Model):
    """
    Bonificaciones del expediente del alumno.
    Gestionadas y verificadas por administración antes de ser aplicadas.
    """
    BENEFIT_CHOICES = [
        ('familia_numerosa_general', 'Familia Numerosa General'),
        ('familia_numerosa_especial', 'Familia Numerosa Especial'),
        ('discapacidad_33', 'Discapacidad ≥ 33%'),
        ('beca_mec', 'Beca MEC'),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 's'},
        related_name='benefits',
    )
    benefit_type = models.CharField(max_length=30, choices=BENEFIT_CHOICES)
    verified = models.BooleanField(
        default=False,
        help_text='Solo los beneficios verificados por administración se aplican al cálculo.',
    )
    valid_until = models.DateField(
        null=True,
        blank=True,
        help_text='Fecha de vencimiento. Nulo = vigencia indefinida (ej: discapacidad).',
    )

    class Meta:
        unique_together = ['student', 'benefit_type']
        ordering = ['benefit_type']

    def __str__(self):
        return f"{self.student.username} — {self.get_benefit_type_display()}"
