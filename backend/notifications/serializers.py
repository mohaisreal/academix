from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from .models import (
    Notification,
    UserEmailPreference,
    SystemSettings,
    EmailTemplate,
    NOTIFICATION_EVENT_DEFINITIONS,
    default_event_preferences,
)


class NotificationSerializer(serializers.ModelSerializer):
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    notification_type = serializers.CharField(source='type', read_only=True)
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
        fields = [
            'id',
            'title',
            'message',
            'type',
            'notification_type',
            'type_display',
            'event_type',
            'is_read',
            'time_ago',
            'created_at',
        ]


class UserEmailPreferenceSerializer(serializers.ModelSerializer):
    available_events = serializers.SerializerMethodField()

    def get_available_events(self, obj):
        return NOTIFICATION_EVENT_DEFINITIONS

    def validate_event_preferences(self, value):
        if value in (None, ''):
            return {}
        if not isinstance(value, dict):
            raise serializers.ValidationError('event_preferences must be an object.')

        allowed = set(default_event_preferences().keys())
        invalid = sorted(set(value.keys()) - allowed)
        if invalid:
            raise serializers.ValidationError(
                f"Unsupported notification event(s): {', '.join(invalid)}"
            )

        normalized = {}
        for key, enabled in value.items():
            if not isinstance(enabled, bool):
                raise serializers.ValidationError(
                    f"Preference '{key}' must be true or false."
                )
            normalized[key] = enabled
        return normalized

    def update(self, instance, validated_data):
        incoming_events = validated_data.pop('event_preferences', None)
        delivery_channel = validated_data.get('delivery_channel')
        email_enabled = validated_data.get('email_enabled', None)

        # Mantén sincronizados email_enabled heredado y el nuevo canal de entrega.
        if delivery_channel is not None and email_enabled is None:
            validated_data['email_enabled'] = delivery_channel in ('email', 'both')
        elif email_enabled is not None and delivery_channel is None:
            validated_data['delivery_channel'] = 'both' if email_enabled else 'profile'

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if incoming_events is not None:
            merged = default_event_preferences()
            merged.update(instance.event_preferences or {})
            merged.update(incoming_events)
            instance.event_preferences = merged

        instance.save()
        return instance

    def to_representation(self, instance):
        # No expongas JSON parcial a la interfaz; devuelve siempre el mapa completo de decisiones.
        data = super().to_representation(instance)
        merged = default_event_preferences()
        merged.update(instance.event_preferences or {})
        data['event_preferences'] = merged
        if not instance.email_enabled and data.get('delivery_channel') in ('email', 'both'):
            data['delivery_channel'] = 'profile'
        return data

    class Meta:
        model = UserEmailPreference
        fields = [
            'notifications_enabled',
            'email_enabled',
            'delivery_channel',
            'theme',
            'event_preferences',
            'available_events',
        ]
        read_only_fields = ['available_events']


class SystemSettingsSerializer(serializers.ModelSerializer):
    def validate_enrollment_extra_charges(self, value):
        if value in (None, ''):
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError('enrollment_extra_charges must be a list.')

        normalized = []
        for idx, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                raise serializers.ValidationError(f'Extra charge #{idx} must be an object.')

            label = str(item.get('label', '')).strip()
            if not label:
                raise serializers.ValidationError(f'Extra charge #{idx} requires a label.')

            try:
                amount = serializers.DecimalField(max_digits=8, decimal_places=2).to_internal_value(
                    item.get('amount', '0')
                )
            except serializers.ValidationError as exc:
                raise serializers.ValidationError(f'Extra charge #{idx} has an invalid amount.') from exc

            if amount < 0:
                raise serializers.ValidationError(f'Extra charge #{idx} amount cannot be negative.')

            normalized.append({
                'label': label,
                'amount': str(amount),
                'active': bool(item.get('active', True)),
            })
        return normalized

    class Meta:
        model = SystemSettings
        fields = [
            'email_notifications_enabled',
            'student_id_format',
            'admission_public_dni_mask_regex',
            'admission_public_dni_mask_replacement',
            'school_insurance_fee',
            'transcript_opening_fee',
            'enrollment_extra_charges',
        ]


class EmailTemplateSerializer(serializers.ModelSerializer):
    """
    Full CRUD serializer for EmailTemplate.

    For preview, pass a `preview_context` dict (write-only) containing
    key/value pairs to substitute into the template before rendering.
    This field is ignored on create/update — it is only consumed by
    EmailTemplatePreviewView.
    """
    preview_context = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        write_only=True,
        required=False,
        help_text=(
            "Key/value pairs used to render a preview of the template. "
            "Sent only to the /preview/ endpoint; ignored on create/update."
        ),
    )

    class Meta:
        model = EmailTemplate
        fields = [
            'id',
            'name',
            'subject_template',
            'body_template',
            'description',
            'is_active',
            'updated_at',
            'preview_context',
        ]
        read_only_fields = ['id', 'updated_at']
