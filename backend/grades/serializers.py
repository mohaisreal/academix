from rest_framework import serializers
from .models import Evaluation, EvaluationSubmission, Grade


class EvaluationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    grades_count = serializers.SerializerMethodField()

    def get_grades_count(self, obj):
        return obj.grades.count()

    class Meta:
        model = Evaluation
        fields = [
            'id', 'name', 'cls', 'type', 'type_display',
            'max_score', 'min_score', 'due_date', 'allows_file_submission',
            'is_hidden', 'description', 'grades_count', 'created_at',
        ]

    def validate(self, attrs):
        max_score = attrs.get('max_score', getattr(self.instance, 'max_score', None))
        min_score = attrs.get('min_score', getattr(self.instance, 'min_score', None))

        if min_score is not None and max_score is not None and min_score > max_score:
            raise serializers.ValidationError({
                'min_score': 'min_score no puede ser mayor que max_score.',
            })

        self._warnings = []
        if self.instance is not None and 'max_score' in attrs:
            new_max_score = attrs['max_score']
            affected = self.instance.grades.filter(score__gt=new_max_score)
            if affected.exists():
                self._warnings.append(
                    f'max_score ({new_max_score}) es menor que {affected.count()} '
                    f'nota(s) ya registrada(s); esas notas ahora superan el máximo.'
                )

        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['warnings'] = getattr(self, '_warnings', [])
        return data


class EvaluationSubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    evaluation_name = serializers.CharField(source='evaluation.name', read_only=True)

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip() or obj.student.username

    class Meta:
        model = EvaluationSubmission
        fields = ['id', 'student', 'student_name', 'evaluation', 'evaluation_name', 'file', 'submitted_at']


class GradeSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    evaluation_name = serializers.CharField(source='evaluation.name', read_only=True)
    percentage = serializers.SerializerMethodField()
    evaluation_passed = serializers.SerializerMethodField()

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip() or obj.student.username

    def get_percentage(self, obj):
        if obj.evaluation.max_score and obj.evaluation.max_score > 0:
            return round(float(obj.score) / float(obj.evaluation.max_score) * 100, 1)
        return 0

    def get_evaluation_passed(self, obj):
        if obj.evaluation.min_score is None:
            return None
        return obj.score >= obj.evaluation.min_score

    class Meta:
        model = Grade
        fields = [
            'id', 'student', 'student_name', 'evaluation', 'evaluation_name',
            'score', 'percentage', 'evaluation_passed', 'feedback', 'graded_by', 'graded_at', 'updated_at',
        ]
