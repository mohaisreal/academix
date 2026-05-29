from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Career,
    Subject,
    Department,
    AcademicPeriod,
    Classroom,
    Class,
    ClassSchedule,
    TimeSlot,
    TimetableRun,
    ScheduleAssignment,
    ConstraintViolation,
    SchedulingConstraint,
)
from .schedule_source import serialize_assignment_schedule

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
    available_spots = serializers.SerializerMethodField()

    def get_subjects_count(self, obj):
        return obj.subjects.filter(is_active=True).count()

    def get_available_spots(self, obj):
        from enrollment.models import CareerEnrollment
        from academic.models import AcademicPeriod
        active_period = AcademicPeriod.objects.filter(is_active=True).order_by('-start_date').first()
        if not active_period:
            return obj.total_spots
        enrolled = CareerEnrollment.objects.filter(
            career=obj,
            period=active_period,
            status='active',
        ).count()
        return max(0, obj.total_spots - enrolled)

    class Meta:
        model = Career
        fields = ['id', 'name', 'code', 'description', 'duration_years',
                  'total_spots', 'available_spots', 'is_active', 'subjects_count',
                  'created_at', 'updated_at']


class SubjectSerializer(serializers.ModelSerializer):
    career_name = serializers.CharField(source='career.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_teacher_name = serializers.SerializerMethodField()

    def get_department_teacher_name(self, obj):
        department = getattr(obj, 'department', None)
        teacher = getattr(department, 'teacher', None) if department else None
        if not teacher:
            return None
        return f"{teacher.first_name} {teacher.last_name}".strip() or teacher.username

    class Meta:
        model = Subject
        fields = ['id', 'name', 'code', 'career', 'career_name', 'credits',
                  'department', 'department_name', 'department_teacher_name',
                  'credit_price_first_enrollment',
                  'credit_price_second_enrollment',
                  'credit_price_third_enrollment',
                  'credit_price_fourth_or_more_enrollment',
                  'subject_type', 'description', 'hours_per_week', 'is_active']


class DepartmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    subjects_count = serializers.SerializerMethodField()

    def get_teacher_name(self, obj):
        if not obj.teacher:
            return None
        return f"{obj.teacher.first_name} {obj.teacher.last_name}".strip() or obj.teacher.username

    def get_subjects_count(self, obj):
        return obj.subjects.filter(is_active=True).count()

    class Meta:
        model = Department
        fields = ['id', 'name', 'code', 'description', 'teacher', 'teacher_name', 'subjects_count', 'is_active', 'created_at', 'updated_at']


class AcademicPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicPeriod
        fields = ['id', 'name', 'code', 'start_date', 'end_date',
                  'enrollment_modification_deadline',
                  'admission_open_date', 'admission_close_date',
                  'is_active']

    def validate(self, attrs):
        start = attrs.get('admission_open_date', getattr(self.instance, 'admission_open_date', None))
        end = attrs.get('admission_close_date', getattr(self.instance, 'admission_close_date', None))
        if start and end and start >= end:
            raise serializers.ValidationError({
                'admission_close_date': 'La fecha de cierre de admisión debe ser posterior a la fecha de apertura.'
            })
        return attrs


class ClassroomSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)

    class Meta:
        model = Classroom
        fields = ['id', 'name', 'building', 'capacity', 'type', 'type_display']


class ClassScheduleSerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)
    cls_id = serializers.PrimaryKeyRelatedField(
        queryset=Class.objects.all(),
        source='cls',
        write_only=True,
        required=False,
    )
    class_id = serializers.IntegerField(source='cls.id', read_only=True)

    class Meta:
        model = ClassSchedule
        fields = ['id', 'cls_id', 'class_id', 'day_of_week', 'day_name', 'start_time', 'end_time']

    def validate(self, attrs):
        if self.instance is None and not attrs.get('cls'):
            raise serializers.ValidationError({'cls_id': 'Class is required when creating a schedule.'})
        start = attrs.get('start_time', getattr(self.instance, 'start_time', None))
        end = attrs.get('end_time', getattr(self.instance, 'end_time', None))
        if start and end and start >= end:
            raise serializers.ValidationError({'end_time': 'End time must be after start time.'})
        return attrs


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
    schedules = serializers.SerializerMethodField()
    schedule_source = serializers.SerializerMethodField()
    schedule_available = serializers.SerializerMethodField()
    schedule_unavailable_reason = serializers.SerializerMethodField()
    enrolled_count = serializers.SerializerMethodField()
    available_spots = serializers.SerializerMethodField()

    def get_enrolled_count(self, obj):
        return obj.enrollments.filter(status='enrolled').count() if hasattr(obj, 'enrollments') else 0

    def get_available_spots(self, obj):
        from enrollment.models import ClassEnrollment
        enrolled = ClassEnrollment.objects.filter(cls=obj, status='enrolled').count()
        # Usa la capacidad más restrictiva: la capacidad del aula si está asignada,
        # en caso contrario, usa max_students como respaldo (siempre tiene default=30).
        if obj.classroom and obj.classroom.capacity:
            capacity = min(obj.classroom.capacity, obj.max_students)
        else:
            capacity = obj.max_students or 30
        return max(0, capacity - enrolled)

    def _published_assignments(self, obj):
        assignments = getattr(obj, 'published_schedule_assignments', None)
        if assignments is None:
            assignments = list(
                obj.schedule_assignments.filter(run__status='published').select_related('slot', 'run').order_by('-run__created_at', '-id')
            )
        period_match = [a for a in assignments if a.run.period_id == obj.period_id]
        return sorted(period_match, key=lambda a: (a.slot.day_of_week, a.slot.start_time, a.id))

    def get_schedules(self, obj):
        assignments = self._published_assignments(obj)
        return [serialize_assignment_schedule(assignment) for assignment in assignments]

    def get_schedule_source(self, obj):
        return 'generated'

    def get_schedule_available(self, obj):
        return len(self._published_assignments(obj)) > 0

    def get_schedule_unavailable_reason(self, obj):
        return None if self.get_schedule_available(obj) else 'schedule_unavailable'

    class Meta:
        model = Class
        fields = [
            'id', 'subject', 'subject_id', 'teacher', 'teacher_id',
            'period', 'period_id', 'classroom', 'classroom_id',
            'max_students', 'passing_grade', 'schedules', 'schedule_source', 'schedule_available',
            'schedule_unavailable_reason', 'enrolled_count', 'available_spots', 'created_at',
        ]


class TimeSlotSerializer(serializers.ModelSerializer):
    day_name = serializers.CharField(source='get_day_of_week_display', read_only=True)

    class Meta:
        model = TimeSlot
        fields = ['id', 'period', 'day_of_week', 'day_name', 'start_time', 'end_time']

    def validate(self, attrs):
        start = attrs.get('start_time', getattr(self.instance, 'start_time', None))
        end = attrs.get('end_time', getattr(self.instance, 'end_time', None))
        if start and end and start >= end:
            raise serializers.ValidationError({'end_time': 'End time must be after start time.'})
        return attrs


class TimetableRunSerializer(serializers.ModelSerializer):
    period_name = serializers.CharField(source='period.name', read_only=True)
    assignments_count = serializers.SerializerMethodField()

    class Meta:
        model = TimetableRun
        fields = ['id', 'period', 'period_name', 'status', 'metadata', 'assignments_count', 'created_at', 'updated_at']
        read_only_fields = ['status', 'metadata', 'created_at', 'updated_at']

    def get_assignments_count(self, obj):
        return obj.assignments.count()


class ScheduleAssignmentSerializer(serializers.ModelSerializer):
    period = serializers.IntegerField(source='run.period_id', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    classroom_name = serializers.SerializerMethodField()
    timeslot_day_name = serializers.CharField(source='slot.get_day_of_week_display', read_only=True)
    timeslot_start_time = serializers.TimeField(source='slot.start_time', read_only=True)
    timeslot_end_time = serializers.TimeField(source='slot.end_time', read_only=True)
    subject_name = serializers.CharField(source='cls.subject.name', read_only=True)
    subject_code = serializers.CharField(source='cls.subject.code', read_only=True)
    career_id = serializers.IntegerField(source='cls.subject.career_id', read_only=True)
    career_code = serializers.CharField(source='cls.subject.career.code', read_only=True)
    career_name = serializers.CharField(source='cls.subject.career.name', read_only=True)

    def get_teacher_name(self, obj):
        if not obj.teacher:
            return None
        full_name = f"{obj.teacher.first_name} {obj.teacher.last_name}".strip()
        return full_name or obj.teacher.username

    def get_classroom_name(self, obj):
        if not obj.classroom:
            return None
        return obj.classroom.name

    class Meta:
        model = ScheduleAssignment
        fields = [
            'id', 'run', 'period', 'cls', 'slot', 'classroom', 'teacher',
            'teacher_name', 'classroom_name',
            'timeslot_day_name', 'timeslot_start_time', 'timeslot_end_time',
            'subject_name', 'subject_code', 'career_id', 'career_code', 'career_name',
            'source', 'created_at',
        ]


class ConstraintViolationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConstraintViolation
        fields = ['id', 'run', 'assignment', 'severity', 'reason', 'metadata', 'created_at']


class SchedulingConstraintSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchedulingConstraint
        fields = ['id', 'kind', 'scope', 'period', 'teacher', 'classroom', 'career', 'day_of_week', 'start_time', 'end_time', 'is_active', 'metadata', 'created_at', 'updated_at']

    def validate(self, attrs):
        base = {
            'kind': getattr(self.instance, 'kind', None),
            'scope': getattr(self.instance, 'scope', 'period'),
            'period': getattr(self.instance, 'period', None),
            'teacher': getattr(self.instance, 'teacher', None),
            'classroom': getattr(self.instance, 'classroom', None),
            'career': getattr(self.instance, 'career', None),
            'day_of_week': getattr(self.instance, 'day_of_week', None),
            'start_time': getattr(self.instance, 'start_time', None),
            'end_time': getattr(self.instance, 'end_time', None),
            'is_active': getattr(self.instance, 'is_active', True),
            'metadata': getattr(self.instance, 'metadata', {}),
        }
        instance = SchedulingConstraint(**{**base, **attrs})
        instance.clean()
        return attrs
