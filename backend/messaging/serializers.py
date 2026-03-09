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
