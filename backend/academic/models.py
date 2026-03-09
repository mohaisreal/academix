from django.db import models
from django.conf import settings


class Career(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    duration_years = models.PositiveSmallIntegerField(default=4)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class Subject(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    career = models.ForeignKey(Career, on_delete=models.CASCADE, related_name='subjects')
    credits = models.PositiveSmallIntegerField(default=3)
    description = models.TextField(blank=True)
    hours_per_week = models.PositiveSmallIntegerField(default=4)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class AcademicPeriod(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
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
