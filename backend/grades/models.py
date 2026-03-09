from django.db import models
from django.conf import settings


class Evaluation(models.Model):
    TYPE_CHOICES = [
        ('exam', 'Exam'),
        ('assignment', 'Assignment'),
        ('quiz', 'Quiz'),
        ('project', 'Project'),
        ('participation', 'Participation'),
    ]
    name = models.CharField(max_length=200)
    cls = models.ForeignKey('academic.Class', on_delete=models.CASCADE, related_name='evaluations')
    type = models.CharField(max_length=15, choices=TYPE_CHOICES, default='assignment')
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    due_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.cls})"


class Grade(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 's'},
        related_name='grades',
    )
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='grades')
    score = models.DecimalField(max_digits=6, decimal_places=2)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='graded_by_grades',
    )
    graded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['student', 'evaluation']

    def __str__(self):
        return f"{self.student.username} - {self.evaluation.name}: {self.score}"
