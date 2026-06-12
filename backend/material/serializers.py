from rest_framework import serializers
from django.utils.text import get_valid_filename
from .models import Material


class MaterialSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    class_name = serializers.SerializerMethodField()
    uploader_name = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()

    def get_class_name(self, obj):
        return str(obj.cls)

    def get_uploader_name(self, obj):
        return (
            f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}".strip()
            or obj.uploaded_by.username
        )

    def get_download_url(self, obj):
        return f"/material/{obj.pk}/download/" if obj.file else None

    def get_file_name(self, obj):
        if obj.file:
            return get_valid_filename(obj.original_filename or obj.file.name.rsplit('/', 1)[-1])
        return None

    class Meta:
        model = Material
        fields = [
            'id', 'title', 'description', 'cls', 'class_name',
            'uploaded_by', 'uploader_name', 'file', 'file_name', 'download_url', 'url',
            'type', 'type_display', 'created_at',
        ]
        read_only_fields = ['uploaded_by']
