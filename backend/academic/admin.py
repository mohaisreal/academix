from django.contrib import admin
from .models import Career, Subject, AcademicPeriod, Classroom, Class, ClassSchedule, MatriculaConfig

admin.site.register(Career)
admin.site.register(Subject)
admin.site.register(AcademicPeriod)
admin.site.register(Classroom)
admin.site.register(Class)
admin.site.register(ClassSchedule)
admin.site.register(MatriculaConfig)
