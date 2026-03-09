from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    time_ago = serializers.SerializerMethodField()

    def get_time_ago(self, obj):
        now = timezone.now()
        diff = now - obj.created_at
        if diff < timedelta(minutes=1):
            return 'just now'
        elif diff < timedelta(hours=1):
            return f"{int(diff.seconds / 60)} min ago"
        elif diff < timedelta(days=1):
            return f"{int(diff.seconds / 3600)} hr ago"
        else:
            return f"{diff.days} days ago"

    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'type', 'type_display', 'is_read', 'time_ago', 'created_at']
