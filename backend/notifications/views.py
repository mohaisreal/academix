from django.conf import settings as django_settings
from django.core.mail import send_mail

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from admissions.permissions import IsManagement
from .models import Notification, UserEmailPreference, SystemSettings, EmailTemplate
from .serializers import (
    NotificationSerializer,
    UserEmailPreferenceSerializer,
    SystemSettingsSerializer,
    EmailTemplateSerializer,
)
from .utils import render_template, wrap_in_email_layout


class NotificationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Notification.objects.filter(user=request.user)
        is_read = request.query_params.get('is_read')
        type_filter = request.query_params.get('type')
        if is_read is not None:
            qs = qs.filter(is_read=(is_read.lower() == 'true'))
        if type_filter:
            qs = qs.filter(type=type_filter)
        return Response(NotificationSerializer(qs, many=True).data)


class MarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            n = Notification.objects.get(pk=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        n.is_read = True
        n.save()
        return Response(NotificationSerializer(n).data)


class MarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return Response({'status': 'all marked as read'})


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'count': count})


class EmailPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    def _serialize(self, pref):
        data = UserEmailPreferenceSerializer(pref).data
        system_settings, _ = SystemSettings.objects.get_or_create(pk=1)
        data['system_email_notifications_enabled'] = (
            system_settings.email_notifications_enabled
        )
        return data

    def get(self, request):
        pref, _ = UserEmailPreference.objects.get_or_create(user=request.user)
        return Response(self._serialize(pref))

    def patch(self, request):
        pref, _ = UserEmailPreference.objects.get_or_create(user=request.user)
        serializer = UserEmailPreferenceSerializer(pref, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        pref = serializer.save()
        return Response(self._serialize(pref))


class SystemSettingsView(APIView):
    permission_classes = [IsManagement]

    def get(self, request):
        settings, _ = SystemSettings.objects.get_or_create(pk=1)
        return Response(SystemSettingsSerializer(settings).data)

    def patch(self, request):
        settings, _ = SystemSettings.objects.get_or_create(pk=1)
        serializer = SystemSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Endpoints de plantillas de correo
# ---------------------------------------------------------------------------

class EmailTemplateListCreateView(APIView):
    """
    GET  /notifications/email-templates/       → list all templates
    POST /notifications/email-templates/       → create a new template
    """
    permission_classes = [IsManagement]

    def get(self, request):
        templates = EmailTemplate.objects.all()
        return Response(EmailTemplateSerializer(templates, many=True).data)

    def post(self, request):
        serializer = EmailTemplateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # preview_context es solo de escritura y no debe llegar a .save()
        serializer.validated_data.pop('preview_context', None)
        template = serializer.save()
        return Response(EmailTemplateSerializer(template).data, status=201)


class EmailTemplateDetailView(APIView):
    """
    GET    /notifications/email-templates/<pk>/  → retrieve single template
    PUT    /notifications/email-templates/<pk>/  → full update
    PATCH  /notifications/email-templates/<pk>/  → partial update
    DELETE /notifications/email-templates/<pk>/  → delete
    """
    permission_classes = [IsManagement]

    def _get_object(self, pk):
        try:
            return EmailTemplate.objects.get(pk=pk)
        except EmailTemplate.DoesNotExist:
            return None

    def get(self, request, pk):
        template = self._get_object(pk)
        if template is None:
            return Response({'error': 'Not found'}, status=404)
        return Response(EmailTemplateSerializer(template).data)

    def put(self, request, pk):
        template = self._get_object(pk)
        if template is None:
            return Response({'error': 'Not found'}, status=404)
        serializer = EmailTemplateSerializer(template, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop('preview_context', None)
        serializer.save()
        return Response(EmailTemplateSerializer(template).data)

    def patch(self, request, pk):
        template = self._get_object(pk)
        if template is None:
            return Response({'error': 'Not found'}, status=404)
        serializer = EmailTemplateSerializer(template, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop('preview_context', None)
        serializer.save()
        return Response(EmailTemplateSerializer(template).data)

    def delete(self, request, pk):
        template = self._get_object(pk)
        if template is None:
            return Response({'error': 'Not found'}, status=404)
        template.delete()
        return Response(status=204)


class EmailTemplatePreviewView(APIView):
    """
    POST /notifications/email-templates/<pk>/preview/

    Body (all fields optional):
        {
            "context": {
                "user_name": "Ada Lovelace",
                "user_email": "ada@example.com",
                "custom_key": "custom_value"
            }
        }

    Response:
        {
            "subject": "<rendered subject string>",
            "html":    "<full HTML email layout>"
        }
    """
    permission_classes = [IsManagement]

    def post(self, request, pk):
        try:
            template = EmailTemplate.objects.get(pk=pk)
        except EmailTemplate.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        extra_context = request.data.get('context', {})
        if not isinstance(extra_context, dict):
            return Response({'error': '"context" must be a JSON object'}, status=400)

        # Built-ins — caller may override any of these
        base_context = {
            'app_name': 'Academix',
            'user_name': request.user.get_full_name() or request.user.username,
            'user_email': request.user.email or '',
            'title': 'Vista previa de notificación',
            'message': 'Este es un mensaje de ejemplo para validar la plantilla.',
            'subject_name': 'Asignatura de ejemplo',
            'evaluation_name': 'Tarea de ejemplo',
            'score': '9.00',
            'max_score': '10.00',
            'sender_name': 'Profesor Ejemplo',
            'message_subject': 'Mensaje de ejemplo',
            'message_preview': 'Este es un extracto del mensaje interno.',
            'material_title': 'Material de ejemplo',
            'uploaded_by': 'Profesor Ejemplo',
            'verification_url': 'http://localhost:4321/verify-email',
        }
        base_context.update(extra_context)

        rendered_subject = render_template(template.subject_template, base_context)
        rendered_body = render_template(template.body_template, base_context)

        system_settings, _ = SystemSettings.objects.get_or_create(pk=1)
        html = wrap_in_email_layout(rendered_body, system_settings)

        return Response({'subject': rendered_subject, 'html': html})


class EmailTemplateSendTestView(APIView):
    """
    POST /notifications/email-templates/<pk>/send-test/

    Sends a rendered test email to the requesting user's address.
    Optionally accepts the same ``context`` dict as the preview endpoint.

    Response:
        { "sent_to": "<email address>" }
    """
    permission_classes = [IsManagement]

    def post(self, request, pk):
        try:
            template = EmailTemplate.objects.get(pk=pk)
        except EmailTemplate.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        recipient = request.user.email
        if not recipient:
            return Response({'error': 'Your account has no email address configured'}, status=400)

        extra_context = request.data.get('context', {})
        if not isinstance(extra_context, dict):
            return Response({'error': '"context" must be a JSON object'}, status=400)

        base_context = {
            'app_name': 'Academix',
            'user_name': request.user.get_full_name() or request.user.username,
            'user_email': recipient,
            'title': 'Email de prueba',
            'message': 'Este es un mensaje de prueba para validar la plantilla.',
            'subject_name': 'Asignatura de ejemplo',
            'evaluation_name': 'Tarea de ejemplo',
            'score': '9.00',
            'max_score': '10.00',
            'sender_name': 'Profesor Ejemplo',
            'message_subject': 'Mensaje de ejemplo',
            'message_preview': 'Este es un extracto del mensaje interno.',
            'material_title': 'Material de ejemplo',
            'uploaded_by': 'Profesor Ejemplo',
            'verification_url': 'http://localhost:4321/verify-email',
        }
        base_context.update(extra_context)

        rendered_subject = render_template(template.subject_template, base_context)
        rendered_body = render_template(template.body_template, base_context)

        system_settings, _ = SystemSettings.objects.get_or_create(pk=1)
        html = wrap_in_email_layout(rendered_body, system_settings)

        # El respaldo de texto plano elimina etiquetas de forma simple; suficiente para un envío de prueba
        import re as _re
        plain_text = _re.sub(r'<[^>]+>', '', rendered_body).strip()

        send_mail(
            subject=f'[Test] {rendered_subject}',
            message=plain_text,
            from_email=django_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            html_message=html,
            fail_silently=False,
        )

        return Response({'sent_to': recipient})
