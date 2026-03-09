from django.db import models
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
