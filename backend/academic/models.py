from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator


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
    department = models.ForeignKey(
        'Department',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subjects',
    )
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
    max_convocations = models.PositiveSmallIntegerField(
        default=6,
        validators=[MinValueValidator(1)],
        help_text='Número máximo de convocatorias fallidas permitidas antes de bloquear la matrícula.',
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


class Department(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    teacher = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 't'},
        related_name='department',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code', 'name']

    def __str__(self):
        return f"{self.code} - {self.name}"


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
    is_generated_by_timetable = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.subject.name} - {self.period.name}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['period', 'subject'],
                name='unique_period_subject_class',
            ),
        ]


class ClassSchedule(models.Model):
    DAY_CHOICES = [
        (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'),
        (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo'),
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


class TimeSlot(models.Model):
    DAY_CHOICES = ClassSchedule.DAY_CHOICES

    period = models.ForeignKey(AcademicPeriod, on_delete=models.CASCADE, related_name='time_slots')
    day_of_week = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['day_of_week', 'start_time']
        constraints = [
            models.UniqueConstraint(
                fields=['period', 'day_of_week', 'start_time', 'end_time'],
                name='unique_period_timeslot',
            ),
        ]

    def clean(self):
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            from django.core.exceptions import ValidationError
            raise ValidationError({'end_time': 'End time must be after start time.'})

    def __str__(self):
        return f"{self.period.code} {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"


class TimetableRun(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('completed', 'Completed'),
        ('partial', 'Partial'),
        ('failed', 'Failed'),
        ('published', 'Published'),
    ]

    period = models.ForeignKey(AcademicPeriod, on_delete=models.CASCADE, related_name='timetable_runs')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='draft')
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class ScheduleAssignment(models.Model):
    SOURCE_CHOICES = [
        ('generated', 'Generated'),
        ('manual', 'Manual'),
    ]

    run = models.ForeignKey(TimetableRun, on_delete=models.CASCADE, related_name='assignments')
    cls = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='schedule_assignments')
    slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='assignments')
    classroom = models.ForeignKey(Classroom, null=True, blank=True, on_delete=models.SET_NULL)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_schedule_assignments',
    )
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='generated')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['run', 'cls', 'slot'], name='unique_run_class_slot'),
            models.UniqueConstraint(fields=['run', 'slot', 'classroom'], name='unique_run_slot_classroom'),
            models.UniqueConstraint(fields=['run', 'slot', 'teacher'], name='unique_run_slot_teacher'),
        ]


class ConstraintViolation(models.Model):
    SEVERITY_CHOICES = [
        ('hard', 'Hard'),
        ('soft', 'Soft'),
    ]

    run = models.ForeignKey(TimetableRun, on_delete=models.CASCADE, related_name='violations')
    assignment = models.ForeignKey(
        ScheduleAssignment,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='violations',
    )
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    reason = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class SchedulingConstraint(models.Model):
    KIND_CHOICES = [
        ('teacher_unavailable', 'Teacher unavailable'),
        ('classroom_unavailable', 'Classroom unavailable'),
        ('career_unavailable', 'Career unavailable'),
    ]
    SCOPE_CHOICES = [
        ('global', 'Global'),
        ('period', 'Period'),
    ]

    kind = models.CharField(max_length=24, choices=KIND_CHOICES)
    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES, default='period')
    period = models.ForeignKey(AcademicPeriod, null=True, blank=True, on_delete=models.CASCADE, related_name='constraints')
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name='scheduling_constraints')
    classroom = models.ForeignKey(Classroom, null=True, blank=True, on_delete=models.CASCADE, related_name='scheduling_constraints')
    career = models.ForeignKey(Career, null=True, blank=True, on_delete=models.CASCADE, related_name='scheduling_constraints')
    day_of_week = models.PositiveSmallIntegerField(choices=ClassSchedule.DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['kind', 'day_of_week', 'start_time']

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError({'end_time': 'End time must be after start time.'})
        if self.scope == 'period' and not self.period_id:
            raise ValidationError({'period': 'Period is required when scope is period.'})
        if self.scope == 'global' and self.period_id:
            raise ValidationError({'period': 'Global constraints cannot be bound to a period.'})

        if self.kind == 'teacher_unavailable' and not self.teacher_id:
            raise ValidationError({'teacher': 'Teacher is required for teacher_unavailable.'})
        if self.kind == 'classroom_unavailable' and not self.classroom_id:
            raise ValidationError({'classroom': 'Classroom is required for classroom_unavailable.'})
        if self.kind == 'career_unavailable' and not self.career_id:
            raise ValidationError({'career': 'Career is required for career_unavailable.'})
