from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Career, Subject, AcademicPeriod, Classroom, Class, ClassSchedule

User = get_user_model()


class TeacherBasicSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name',
                  'email', 'phone', 'profile_image']


class CareerSerializer(serializers.ModelSerializer):
    subjects_count = serializers.SerializerMethodField()

    def get_subjects_count(self, obj):
        return obj.subjects.filter(is_active=True).count()

    class Meta:
        model = Career
        fields = ['id', 'name', 'code', 'description', 'duration_years',
                  'is_active', 'subjects_count', 'created_at', 'updated_at']


class SubjectSerializer(serializers.ModelSerializer):
    career_name = serializers.CharField(source='career.name', read_only=True)

    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'career', 'career_name', 'credits',
                  'description', 'hours_per_week', 'is_active']


class AcademicPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicPeriod
        fields = ['id', 'name', 'code', 'start_date', 'end_date', 'is_active']


class ClassroomSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Classroom
        fields = ['id', 'name', 'building', 'capacity', 'type', 'type_display']


class ClassScheduleSerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = ClassSchedule
        fields = ['id', 'day_of_week', 'day_name', 'start_time', 'end_time']


class ClassSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    subject_id = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(), source='subject', write_only=True
    )
    teacher = TeacherBasicSerializer(read_only=True)
    teacher_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='t'), source='teacher',
        write_only=True, required=False, allow_null=True
    )
    period = AcademicPeriodSerializer(read_only=True)
    period_id = serializers.PrimaryKeyRelatedField(
        queryset=AcademicPeriod.objects.all(), source='period', write_only=True
    )
    classroom = ClassroomSerializer(read_only=True)
    classroom_id = serializers.PrimaryKeyRelatedField(
        queryset=Classroom.objects.all(), source='classroom',
        write_only=True, required=False, allow_null=True
    )
    schedules = ClassScheduleSerializer(many=True, read_only=True)
    enrolled_count = serializers.SerializerMethodField()

    def get_enrolled_count(self, obj):
        return obj.enrollments.filter(status='enrolled').count() if hasattr(obj, 'enrollments') else 0

    class Meta:
        model = Class
        fields = [
            'id', 'subject', 'subject_id', 'teacher', 'teacher_id',
            'period', 'period_id', 'classroom', 'classroom_id',
            'max_students', 'schedules', 'enrolled_count', 'created_at',
        ]
