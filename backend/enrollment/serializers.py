from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CareerEnrollment, ClassEnrollment
from academic.models import Career, AcademicPeriod, Class

User = get_user_model()


class StudentBasicSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name',
                  'email', 'phone', 'profile_image']


class CareerEnrollmentSerializer(serializers.ModelSerializer):
    student = StudentBasicSerializer(read_only=True)
    student_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role='s'), source='student', write_only=True
    )
    career_name = serializers.CharField(source='career.name', read_only=True)
    career_id = serializers.PrimaryKeyRelatedField(
        queryset=Career.objects.all(), source='career', write_only=True
    )
    period_name = serializers.CharField(source='period.name', read_only=True)
    period_id = serializers.PrimaryKeyRelatedField(
        queryset=AcademicPeriod.objects.all(), source='period', write_only=True
    )
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = CareerEnrollment
        fields = [
            'id', 'student', 'student_id', 'career_name', 'career_id',
            'period_name', 'period_id', 'status', 'status_display',
            'enrolled_at', 'updated_at',
        ]


class ClassEnrollmentSerializer(serializers.ModelSerializer):
    cls_id = serializers.PrimaryKeyRelatedField(
        queryset=Class.objects.all(), source='cls', write_only=True
    )
    subject_name = serializers.CharField(source='cls.subject.name', read_only=True)
    subject_code = serializers.CharField(source='cls.subject.code', read_only=True)
    credits = serializers.IntegerField(source='cls.subject.credits', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    classroom = serializers.SerializerMethodField()
    period_name = serializers.CharField(source='cls.period.name', read_only=True)
    schedules = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    def get_teacher_name(self, obj):
        t = obj.cls.teacher
        if not t:
            return ''
        return f"{t.first_name} {t.last_name}".strip() or t.username

    def get_classroom(self, obj):
        return str(obj.cls.classroom) if obj.cls.classroom else ''

    def get_schedules(self, obj):
        return [
            {
                'day_name': s.get_day_of_week_display(),
                'start_time': s.start_time.strftime('%H:%M'),
                'end_time': s.end_time.strftime('%H:%M'),
            }
            for s in obj.cls.schedules.all()
        ]

    class Meta:
        model = ClassEnrollment
        fields = [
            'id', 'cls_id', 'subject_name', 'subject_code', 'credits',
            'teacher_name', 'classroom', 'period_name', 'schedules',
            'status', 'status_display', 'enrolled_at',
        ]
