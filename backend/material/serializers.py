from rest_framework import serializers
from .models import Material


class MaterialSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    class_name = serializers.SerializerMethodField()
    uploader_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    def get_class_name(self, obj):
        return str(obj.cls)

    def get_uploader_name(self, obj):
        return (
            f"{obj.uploaded_by.first_name} {obj.uploaded_by.last_name}".strip()
            or obj.uploaded_by.username
        )

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    class Meta:
        model = Material
        fields = [
            'id', 'title', 'description', 'cls', 'class_name',
            'uploaded_by', 'uploader_name', 'file', 'file_url', 'url',
            'type', 'type_display', 'created_at',
        ]
        read_only_fields = ['uploaded_by']
