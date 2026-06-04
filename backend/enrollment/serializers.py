from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CareerEnrollment, ClassEnrollment, EnrollmentFee
from academic.models import Career, AcademicPeriod, Class
from academic.schedule_source import canonical_assignment_map_for_period, serialize_assignment_schedule

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
    career_id_ro = serializers.IntegerField(source='career.id', read_only=True)
    period_name = serializers.CharField(source='period.name', read_only=True)
    period_id = serializers.PrimaryKeyRelatedField(
        queryset=AcademicPeriod.objects.all(), source='period', write_only=True
    )
    period_id_ro = serializers.IntegerField(source='period.id', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    fee_status = serializers.SerializerMethodField()
    fee_paid = serializers.SerializerMethodField()

    def get_fee_status(self, obj):
        try:
            return obj.fee.status
        except EnrollmentFee.DoesNotExist:
            return None

    def get_fee_paid(self, obj):
        return self.get_fee_status(obj) in ('paid', 'exempted')

    class Meta:
        model = CareerEnrollment
        fields = [
            'id', 'student', 'student_id', 'career_name', 'career_id', 'career_id_ro',
            'period_name', 'period_id', 'period_id_ro', 'status', 'status_display',
            'fee_status', 'fee_paid', 'enrolled_at', 'updated_at',
        ]


class ClassEnrollmentSerializer(serializers.ModelSerializer):
    cls_id = serializers.PrimaryKeyRelatedField(
        queryset=Class.objects.all(), source='cls', write_only=True
    )
    class_id = serializers.IntegerField(source='cls.id', read_only=True)
    subject_name = serializers.CharField(source='cls.subject.name', read_only=True)
    subject_code = serializers.CharField(source='cls.subject.code', read_only=True)
    credits = serializers.IntegerField(source='cls.subject.credits', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    classroom = serializers.SerializerMethodField()
    period_name = serializers.CharField(source='cls.period.name', read_only=True)
    schedules = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    def get_teacher_name(self, obj):
        assignment_map = self.context.get('canonical_assignment_map')
        if assignment_map is None:
            assignment_map = canonical_assignment_map_for_period(obj.cls.period_id, [obj.cls_id])
        assignment = assignment_map.get(obj.cls_id)
        t = assignment.teacher if assignment else obj.cls.teacher
        if not t:
            return ''
        return f"{t.first_name} {t.last_name}".strip() or t.username

    def get_classroom(self, obj):
        return str(obj.cls.classroom) if obj.cls.classroom else ''

    def get_schedules(self, obj):
        assignment_map = self.context.get('canonical_assignment_map')
        if assignment_map is None:
            assignment_map = canonical_assignment_map_for_period(obj.cls.period_id, [obj.cls_id])
        assignment = assignment_map.get(obj.cls_id)
        if not assignment:
            return []
        return [serialize_assignment_schedule(assignment)]

    class Meta:
        model = ClassEnrollment
        fields = [
            'id', 'cls_id', 'class_id', 'subject_name', 'subject_code', 'credits',
            'teacher_name', 'classroom', 'period_name', 'schedules',
            'status', 'status_display', 'enrolled_at',
        ]


class EnrollmentFeeSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = EnrollmentFee
        fields = [
            'id', 'base_amount', 'discount_amount', 'discount_reason',
            'final_amount', 'line_items', 'status', 'status_display', 'paid_at',
            'stripe_payment_intent_id', 'stripe_payment_status',
        ]
        read_only_fields = ['id', 'paid_at', 'status_display', 'stripe_payment_intent_id', 'stripe_payment_status']
