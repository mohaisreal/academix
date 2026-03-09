from rest_framework import serializers
from .models import Evaluation, Grade


class EvaluationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    grades_count = serializers.SerializerMethodField()

    def get_grades_count(self, obj):
        return obj.grades.count()

    class Meta:
        model = Evaluation
        fields = [
            'id', 'name', 'cls', 'type', 'type_display',
            'max_score', 'due_date', 'description', 'grades_count', 'created_at',
        ]


class GradeSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    evaluation_name = serializers.CharField(source='evaluation.name', read_only=True)
    percentage = serializers.SerializerMethodField()

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip() or obj.student.username

    def get_percentage(self, obj):
        if obj.evaluation.max_score and obj.evaluation.max_score > 0:
            return round(float(obj.score) / float(obj.evaluation.max_score) * 100, 1)
        return 0

    class Meta:
        model = Grade
        fields = [
            'id', 'student', 'student_name', 'evaluation', 'evaluation_name',
            'score', 'percentage', 'feedback', 'graded_by', 'graded_at', 'updated_at',
        ]
