from django.db import models
from django.conf import settings


class EvaluationQuerySet(models.QuerySet):
    def visible(self):
        """Evaluations not hidden from students (the single visibility predicate)."""
        return self.filter(is_hidden=False)


class Evaluation(models.Model):
    TYPE_CHOICES = [
        ('exam', 'Exam'),
        ('assignment', 'Assignment'),
        ('project', 'Project'),
        ('participation', 'Participation'),
    ]
    name = models.CharField(max_length=200)
    cls = models.ForeignKey('academic.Class', on_delete=models.CASCADE, related_name='evaluations')
    type = models.CharField(max_length=15, choices=TYPE_CHOICES, default='assignment')
    is_final_grade = models.BooleanField(
        default=False,
        help_text='Indica si esta evaluación representa la nota final que cuenta para convocatorias.',
    )
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100,
        help_text='Peso porcentual en la nota final (0–100). La suma de todos los pesos de una clase debe ser 100.',
    )
    due_date = models.DateTimeField(null=True, blank=True)
    allows_file_submission = models.BooleanField(default=False)
    description = models.TextField(blank=True)
    is_hidden = models.BooleanField(
        default=False,
        help_text='Si está oculta, la evaluación y su nota son invisibles para los estudiantes; solo la ve el profesor que la creó.',
    )
    min_score = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text='Nota mínima para aprobar esta evaluación. Si se define, esta nota determina si la tarea está aprobada o suspensa.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = models.Manager.from_queryset(EvaluationQuerySet)()

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


class EvaluationSubmission(models.Model):
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        limit_choices_to={'role': 's'},
        related_name='evaluation_submissions',
    )
    evaluation = models.ForeignKey(Evaluation, on_delete=models.CASCADE, related_name='submissions')
    file = models.FileField(upload_to='evaluation_submissions/%Y/%m/')
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['student', 'evaluation']

    def __str__(self):
        return f"{self.student.username} → {self.evaluation.name}"
