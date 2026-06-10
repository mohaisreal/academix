from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Message

User = get_user_model()


class UserMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username

    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'profile_image']


class MessageSerializer(serializers.ModelSerializer):
    sender = UserMiniSerializer(read_only=True)
    recipient = UserMiniSerializer(read_only=True)
    recipient_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='recipient', write_only=True
    )
    reply_count = serializers.SerializerMethodField()

    def get_reply_count(self, obj):
        return obj.replies.count()

    class Meta:
        model = Message
        fields = [
            'id', 'sender', 'recipient', 'recipient_id',
            'subject', 'body', 'is_read', 'parent', 'reply_count', 'created_at',
        ]
        read_only_fields = ['sender', 'is_read']


class ThreadLastMessageSerializer(serializers.Serializer):
    """Minimal preview of the most recent message (root or reply) in a thread."""

    id = serializers.IntegerField()
    body = serializers.CharField()
    sender_id = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class ThreadSerializer(serializers.Serializer):
    """
    Unified inbox row: one entry per thread root the requesting user can see,
    ordered newest-first by latest activity (root or any reply).
    """

    id = serializers.IntegerField()
    root_id = serializers.IntegerField()
    other_participant = UserMiniSerializer()
    last_message = ThreadLastMessageSerializer()
    last_activity_at = serializers.DateTimeField()
    unread_count = serializers.IntegerField()
