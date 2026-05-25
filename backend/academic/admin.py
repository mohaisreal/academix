from django.contrib import admin
from .models import (
    Career,
    Subject,
    Department,
    AcademicPeriod,
    Classroom,
    Class,
    ClassSchedule,
    MatriculaConfig,
    TimeSlot,
    TimetableRun,
    ScheduleAssignment,
    ConstraintViolation,
)

admin.site.register(Career)
admin.site.register(Subject)
admin.site.register(Department)
admin.site.register(AcademicPeriod)
admin.site.register(Classroom)
admin.site.register(Class)
admin.site.register(ClassSchedule)
admin.site.register(MatriculaConfig)
admin.site.register(TimeSlot)
admin.site.register(TimetableRun)
admin.site.register(ScheduleAssignment)
admin.site.register(ConstraintViolation)
