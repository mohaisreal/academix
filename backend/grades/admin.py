from django.contrib import admin
from .models import Evaluation, EvaluationSubmission, Grade


@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ['name', 'cls', 'type', 'max_score', 'min_score', 'is_hidden', 'due_date']
    list_filter = ['type', 'is_hidden', 'is_final_grade']


admin.site.register(Grade)
admin.site.register(EvaluationSubmission)
