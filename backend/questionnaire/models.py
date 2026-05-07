from django.conf import settings
from django.db import models


class Questionnaire(models.Model):
    FLOW_TYPE_CHOICES = [
        ('admissions', 'Admissions'),
        ('enrollment', 'Enrollment'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    flow_type = models.CharField(max_length=20, choices=FLOW_TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    is_preinscripcion_wizard = models.BooleanField(
        default=False,
        help_text='Si está marcado, este cuestionario reemplaza el asistente estático de preinscripción.',
    )
    career = models.ForeignKey(
        'academic.Career',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='questionnaires',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name='created_questionnaires',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        career_suffix = f' [{self.career.name}]' if self.career else ' [generic]'
        return f'{self.title}{career_suffix} ({self.flow_type})'


class QuestionnaireStep(models.Model):
    questionnaire = models.ForeignKey(
        Questionnaire,
        on_delete=models.CASCADE,
        related_name='steps',
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.questionnaire.title} — Step {self.order}: {self.title}'


class Question(models.Model):
    QUESTION_TYPE_CHOICES = [
        # Standard inputs
        ('text', 'Text'),
        ('textarea', 'Textarea'),
        ('email', 'Email'),
        ('tel', 'Phone'),
        ('number', 'Number'),
        ('date', 'Date'),
        # Choice inputs
        ('select', 'Select'),
        ('radio', 'Radio'),
        ('checkbox', 'Checkbox'),
        # Special
        ('file_upload', 'File Upload'),
        ('career_select', 'Career Select'),
        ('subject_select', 'Subject Select'),
        ('stripe_payment', 'Stripe Payment'),
        ('info', 'Info'),
    ]

    step = models.ForeignKey(
        QuestionnaireStep,
        on_delete=models.CASCADE,
        related_name='questions',
    )
    label = models.CharField(max_length=500)
    help_text = models.TextField(blank=True)
    question_type = models.CharField(max_length=30, choices=QUESTION_TYPE_CHOICES)
    is_required = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    depends_on = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='dependents',
    )
    depends_on_value = models.CharField(max_length=255, blank=True)
    # Configuración adicional por tipo de pregunta.
    # stripe_payment:  {"amount": 800.00, "currency": "eur", "description": "..."}
    # file_upload:     {"accepted_types": ["pdf", "jpg"], "max_size_mb": 10}
    # subject_select:  {"allow_past_years": true, "max_selections": 8}
    # info:            {"content": "<p>HTML content</p>"}
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'[{self.question_type}] {self.label[:80]}'


class QuestionOption(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='options',
    )
    label = models.CharField(max_length=255)
    value = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.label} ({self.value})'


class QuestionnaireResponse(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
    ]

    questionnaire = models.ForeignKey(
        Questionnaire,
        on_delete=models.PROTECT,
        related_name='responses',
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='questionnaire_responses',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    current_step = models.PositiveIntegerField(default=0)
    admission = models.ForeignKey(
        'admissions.AdmissionApplication',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='questionnaire_responses',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.student} → {self.questionnaire.title} ({self.status})'


class QuestionAnswer(models.Model):
    STRIPE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    ]

    response = models.ForeignKey(
        QuestionnaireResponse,
        on_delete=models.CASCADE,
        related_name='answers',
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name='answers',
    )
    text_value = models.TextField(blank=True, default='')
    file_value = models.FileField(
        upload_to='questionnaire_answers/',
        null=True,
        blank=True,
    )
    # Para respuestas de selección múltiple, arrays de titulaciones/asignaturas, etc.
    json_value = models.JSONField(null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    stripe_payment_status = models.CharField(
        max_length=20,
        choices=STRIPE_STATUS_CHOICES,
        blank=True,
    )

    class Meta:
        unique_together = [('response', 'question')]

    def __str__(self):
        return f'Answer to "{self.question.label[:60]}" by {self.response.student}'
