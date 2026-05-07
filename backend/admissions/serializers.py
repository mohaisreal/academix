import os

from rest_framework import serializers
from academic.models import Career, AcademicPeriod
from .models import AdmissionApplication, AdmissionPreference, AdmissionDocument


class AdmissionPreferenceSerializer(serializers.ModelSerializer):
    career_name = serializers.CharField(source='career.name', read_only=True)
    career_code = serializers.CharField(source='career.code', read_only=True)
    career_id_ro = serializers.IntegerField(source='career.id', read_only=True)
    career_id = serializers.PrimaryKeyRelatedField(
        source='career',
        queryset=Career.objects.all(),
        write_only=True,
    )

    class Meta:
        model = AdmissionPreference
        fields = [
            'id', 'career_id', 'career_id_ro', 'career_name', 'career_code',
            'preference_order', 'is_assigned',
            'status', 'ranking_score', 'rank_position',
            'waitlist_position', 'published_at',
        ]
        read_only_fields = [
            'is_assigned', 'status', 'ranking_score',
            'rank_position', 'waitlist_position', 'published_at',
        ]


class AdmissionDocumentSerializer(serializers.ModelSerializer):
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    file_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = AdmissionDocument
        fields = [
            'id', 'document_type', 'document_type_display',
            'file', 'file_name', 'status', 'status_display',
            'rejection_reason', 'uploaded_at',
        ]
        read_only_fields = ['status', 'rejection_reason', 'uploaded_at', 'status_display', 'document_type_display', 'file_name']

    def get_file_name(self, obj):
        return os.path.basename(obj.file.name) if obj.file else None


class AdmissionApplicationSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    access_route_display = serializers.CharField(source='get_access_route_display', read_only=True)
    academic_period_id = serializers.PrimaryKeyRelatedField(
        source='academic_period',
        queryset=AcademicPeriod.objects.all(),
        write_only=True,
    )
    academic_period_name = serializers.CharField(source='academic_period.name', read_only=True)
    academic_period_id_ro = serializers.IntegerField(source='academic_period.id', read_only=True)
    student_name = serializers.SerializerMethodField()
    student_email = serializers.EmailField(source='student.email', read_only=True)
    assigned_career_name = serializers.CharField(source='assigned_career.name', read_only=True)
    assigned_career_id = serializers.IntegerField(source='assigned_career.id', read_only=True)
    preferences = AdmissionPreferenceSerializer(many=True, read_only=True)
    documents = AdmissionDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = AdmissionApplication
        fields = [
            'id', 'student_name', 'student_email',
            'academic_period_id', 'academic_period_name', 'academic_period_id_ro',
            'access_route', 'access_route_display',
            'bachillerato_grade', 'evau_obligatory_grade',
            'evau_voluntary_subjects', 'admission_score',
            'assigned_career_name', 'assigned_career_id', 'assigned_preference_order',
            'status', 'status_display',
            'submission_date', 'admission_expiry_date',
            'notes', 'preferences', 'documents',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'status', 'submission_date', 'admission_expiry_date',
            'admission_score', 'assigned_career_name', 'assigned_career_id',
            'assigned_preference_order', 'created_at', 'updated_at',
        ]

    def get_student_name(self, obj):
        return obj.student.get_full_name() or obj.student.username


class AdmissionApplicationListSerializer(serializers.ModelSerializer):
    """Serializer liviano para listas."""
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    access_route_display = serializers.CharField(source='get_access_route_display', read_only=True)
    academic_period_name = serializers.CharField(source='academic_period.name', read_only=True)
    academic_period_id_ro = serializers.IntegerField(source='academic_period.id', read_only=True)
    assigned_career_name = serializers.CharField(source='assigned_career.name', read_only=True)
    assigned_career_id = serializers.IntegerField(source='assigned_career.id', read_only=True)
    student_name = serializers.SerializerMethodField()
    student_email = serializers.EmailField(source='student.email', read_only=True)
    preferences_count = serializers.SerializerMethodField()
    preferences = AdmissionPreferenceSerializer(many=True, read_only=True)

    class Meta:
        model = AdmissionApplication
        fields = [
            'id', 'student_name', 'student_email',
            'academic_period_name', 'academic_period_id_ro',
            'access_route', 'access_route_display',
            'admission_score',
            'assigned_career_name', 'assigned_career_id', 'assigned_preference_order',
            'status', 'status_display',
            'submission_date', 'created_at',
            'preferences_count', 'preferences',
        ]

    def get_student_name(self, obj):
        return obj.student.get_full_name() or obj.student.username

    def get_preferences_count(self, obj):
        return obj.preferences.count()
