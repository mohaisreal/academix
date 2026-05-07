from django.db import models
from django.conf import settings


class Career(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    duration_years = models.PositiveSmallIntegerField(default=4)
    total_spots = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code', 'name']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Subject(models.Model):
    SUBJECT_TYPE_CHOICES = [
        ('basica', 'Formación Básica'),
        ('obligatoria', 'Obligatoria'),
        ('optativa', 'Optativa'),
        ('practicas', 'Prácticas Externas'),
        ('tfg', 'TFG / TFM'),
    ]

    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    career = models.ForeignKey(Career, on_delete=models.CASCADE, related_name='subjects')
    credits = models.PositiveSmallIntegerField(default=3)
    credit_price_first_enrollment = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=16.00,
        help_text='Precio por crédito para la 1ª matrícula de esta asignatura.',
    )
    credit_price_second_enrollment = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=28.00,
        help_text='Precio por crédito para la 2ª matrícula de esta asignatura.',
    )
    credit_price_third_enrollment = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=45.00,
        help_text='Precio por crédito para la 3ª matrícula de esta asignatura.',
    )
    credit_price_fourth_or_more_enrollment = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=60.00,
        help_text='Precio por crédito para la 4ª matrícula o posteriores de esta asignatura.',
    )
    subject_type = models.CharField(
        max_length=12,
        choices=SUBJECT_TYPE_CHOICES,
        default='obligatoria',
    )
    description = models.TextField(blank=True)
    hours_per_week = models.PositiveSmallIntegerField(default=4)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_credit_price_for_attempt(self, attempt_number):
        attempt = min(max(int(attempt_number or 1), 1), 4)
        if attempt == 1:
            return self.credit_price_first_enrollment
        if attempt == 2:
            return self.credit_price_second_enrollment
        if attempt == 3:
            return self.credit_price_third_enrollment
        return self.credit_price_fourth_or_more_enrollment


class AcademicPeriod(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    enrollment_modification_deadline = models.DateField(null=True, blank=True)
    admission_open_date = models.DateTimeField(null=True, blank=True)
    admission_close_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-start_date']


class Classroom(models.Model):
    TYPE_CHOICES = [
        ('lecture', 'Lecture Hall'),
        ('lab', 'Laboratory'),
        ('seminar', 'Seminar Room'),
    ]
    name = models.CharField(max_length=100)
    building = models.CharField(max_length=100)
    capacity = models.PositiveSmallIntegerField()
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='lecture')

    def __str__(self):
        return f"{self.name} ({self.building})"


class Class(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='classes')
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'role': 't'},
        related_name='teaching_classes',
    )
    period = models.ForeignKey(AcademicPeriod, on_delete=models.CASCADE, related_name='classes')
    classroom = models.ForeignKey(Classroom, on_delete=models.SET_NULL, null=True, blank=True)
    max_students = models.PositiveSmallIntegerField(default=30)
    passing_grade = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=5.00,
        help_text='Nota mínima para superar la asignatura (0.00–10.00)',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject.name} - {self.period.name}"


class ClassSchedule(models.Model):
    DAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]
    cls = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='schedules')
    day_of_week = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.cls} - {self.get_day_of_week_display()} {self.start_time}"


class MatriculaConfig(models.Model):
    """
    Tabla de precios por crédito ECTS según el número de intento de matrícula.
    attempt_number=4 representa '4ª matrícula o más'.
    """
    attempt_number = models.PositiveSmallIntegerField(
        unique=True,
        help_text='Número de matrícula. El valor 4 representa "4ª o más".',
    )
    label = models.CharField(max_length=50)
    price_per_credit = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['attempt_number']

    def __str__(self):
        return f"{self.label} — {self.price_per_credit} €/crédito"
