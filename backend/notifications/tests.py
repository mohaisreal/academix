from unittest.mock import patch
from importlib import import_module

from django.test import TestCase
from rest_framework.test import APIClient
from django.conf import settings as django_settings
from django.apps import apps as django_apps

from users.models import User
from .models import Notification, UserEmailPreference, SystemSettings, EmailTemplate
from .utils import build_frontend_url, create_notification, wrap_in_email_layout
from admissions.utils import notify_next_waitlisted


class CreateNotificationEmailTests(TestCase):
    """Pruebas de la lógica de compuerta de correo en create_notification() (REQ-NOTIF-01)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='student1', email='student1@test.com', password='testpass123', role='s'
        )
        EmailTemplate.objects.get_or_create(
            name='notification_default',
            defaults={
                'subject_template': '{{title}}',
                'body_template': '<p>{{message}}</p>',
                'description': 'Test fallback template',
                'is_active': True,
            },
        )

    @patch('notifications.utils.send_mail')
    def test_happy_path_sends_email(self, mock_send):
        """Sistema y usuario habilitados → correo enviado."""
        SystemSettings.objects.get_or_create(pk=1, defaults={'email_notifications_enabled': True})
        UserEmailPreference.objects.create(user=self.user, email_enabled=True)

        notif = create_notification(self.user, 'Test', 'Hello', 'info', event_type='test')

        self.assertIsNotNone(notif)
        self.assertEqual(notif.event_type, 'test')
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.kwargs['recipient_list'], ['student1@test.com'])

    @patch('notifications.utils.send_mail')
    def test_user_disabled_no_email(self, mock_send):
        """Usuario desuscripto → sin correo."""
        SystemSettings.objects.get_or_create(pk=1, defaults={'email_notifications_enabled': True})
        UserEmailPreference.objects.create(user=self.user, email_enabled=False)

        notif = create_notification(self.user, 'Test', 'Hello')

        self.assertIsNotNone(notif)
        mock_send.assert_not_called()

    @patch('notifications.utils.send_mail')
    def test_system_disabled_no_email(self, mock_send):
        """Sistema deshabilitado → sin correo aunque el usuario esté habilitado."""
        SystemSettings.objects.create(pk=1, email_notifications_enabled=False)
        UserEmailPreference.objects.create(user=self.user, email_enabled=True)

        create_notification(self.user, 'Test', 'Hello')

        mock_send.assert_not_called()

    @patch('notifications.utils.send_mail')
    def test_no_email_address_no_send(self, mock_send):
        """El usuario no tiene correo → no se intenta enviar email."""
        self.user.email = ''
        self.user.save()

        create_notification(self.user, 'Test', 'Hello')

        mock_send.assert_not_called()

    @patch('notifications.utils.send_mail')
    def test_send_mail_called_with_fail_silently(self, mock_send):
        """send_mail se llama con fail_silently=True para que errores SMTP no rompan el flujo."""
        SystemSettings.objects.get_or_create(pk=1, defaults={'email_notifications_enabled': True})
        UserEmailPreference.objects.create(user=self.user, email_enabled=True)

        notif = create_notification(self.user, 'Test', 'Hello')

        self.assertIsNotNone(notif)
        self.assertTrue(Notification.objects.filter(pk=notif.pk).exists())
        mock_send.assert_called_once()
        self.assertTrue(mock_send.call_args.kwargs['fail_silently'])

    def test_backward_compat_no_event_type(self):
        """Llamar sin event_type sigue funcionando (compatibilidad hacia atrás)."""
        notif = create_notification(self.user, 'Test', 'Hello', 'info')
        self.assertEqual(notif.event_type, '')

    @patch('notifications.utils.send_mail')
    def test_profile_only_creates_notification_without_email(self, mock_send):
        """Canal solo perfil → fila de notificación, sin correo."""
        UserEmailPreference.objects.create(
            user=self.user,
            email_enabled=False,
            delivery_channel='profile',
        )

        notif = create_notification(self.user, 'Profile', 'Only profile')

        self.assertIsNotNone(notif)
        self.assertTrue(Notification.objects.filter(pk=notif.pk).exists())
        mock_send.assert_not_called()

    @patch('notifications.utils.send_mail')
    def test_email_only_sends_without_profile_notification(self, mock_send):
        """Canal solo correo → email enviado, sin fila de notificación en perfil."""
        SystemSettings.objects.get_or_create(pk=1, defaults={'email_notifications_enabled': True})
        UserEmailPreference.objects.create(
            user=self.user,
            email_enabled=True,
            delivery_channel='email',
        )

        notif = create_notification(self.user, 'Email', 'Only email')

        self.assertIsNone(notif)
        self.assertFalse(Notification.objects.filter(user=self.user, title='Email').exists())
        mock_send.assert_called_once()

    @patch('notifications.utils.send_mail')
    def test_disabled_event_suppresses_all_delivery(self, mock_send):
        """Clave de evento deshabilitada → sin notificación de perfil y sin correo."""
        SystemSettings.objects.get_or_create(pk=1, defaults={'email_notifications_enabled': True})
        UserEmailPreference.objects.create(
            user=self.user,
            email_enabled=True,
            delivery_channel='both',
            event_preferences={'grade_recorded': False},
        )

        notif = create_notification(
            self.user,
            'Grade',
            'A grade was recorded',
            event_type='grade_recorded',
        )

        self.assertIsNone(notif)
        self.assertFalse(Notification.objects.filter(user=self.user, title='Grade').exists())
        mock_send.assert_not_called()

    @patch('notifications.utils.send_mail')
    def test_message_received_uses_chat_template_name(self, mock_send):
        SystemSettings.objects.get_or_create(pk=1, defaults={'email_notifications_enabled': True})
        UserEmailPreference.objects.create(user=self.user, email_enabled=True)
        EmailTemplate.objects.update_or_create(
            name='chat_message_received',
            defaults={
                'subject_template': 'Chat: {{sender_name}}',
                'body_template': '<p>{{message_subject}}</p>',
                'description': 'Chat template',
                'is_active': True,
            },
        )

        create_notification(
            self.user,
            'Chat',
            'Hello there',
            event_type='message_received',
            context={'sender_name': 'Alice', 'message_subject': 'Hello'},
        )

        mock_send.assert_called_once()
        self.assertIn('Chat: Alice', mock_send.call_args.kwargs['subject'])


class EmailTemplateBrandingTests(TestCase):
    def setUp(self):
        self.settings = SystemSettings.objects.create(
            pk=1,
            email_header_color='#0f766e',
            email_footer_text='Academix support',
        )

    def test_wrap_in_email_layout_adds_brand_shell(self):
        html = wrap_in_email_layout('<p>Hello</p>', self.settings)
        self.assertIn('Notificaciones oficiales de la plataforma', html)
        self.assertIn('Academix', html)
        self.assertIn('linear-gradient', html)
        self.assertIn('<p>Hello</p>', html)

    def test_build_frontend_url_uses_configured_base(self):
        original = django_settings.FRONTEND_URL
        try:
            django_settings.FRONTEND_URL = 'https://portal.example.edu/'
            self.assertEqual(build_frontend_url('/verify-email'), 'https://portal.example.edu/verify-email')
        finally:
            django_settings.FRONTEND_URL = original

    def test_migration_preserves_custom_template_content(self):
        migration_module = import_module('notifications.migrations.0011_branded_default_email_templates')

        template, _ = EmailTemplate.objects.get_or_create(
            name='notification_default',
            defaults={
                'subject_template': '{{title}}',
                'body_template': '<p>Custom content</p>',
                'description': 'Custom',
                'is_active': True,
            },
        )
        EmailTemplate.objects.filter(pk=template.pk).update(body_template='<p>Custom content</p>')

        migration_module.migrate_default_templates(django_apps, None)

        template = EmailTemplate.objects.get(name='notification_default')
        self.assertEqual(template.body_template, '<p>Custom content</p>')


class EmailTemplatePreviewSendTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='manager1', email='manager@test.com', password='testpass123', role='m'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.template, _ = EmailTemplate.objects.get_or_create(
            name='email_verification',
            defaults={
                'subject_template': '{{title}}',
                'body_template': '<p><a href="{{verification_url}}">Verificar cuenta</a></p>',
                'description': 'Verification template',
                'is_active': True,
            },
        )
        EmailTemplate.objects.filter(pk=self.template.pk).update(
            body_template='<p><a href="{{verification_url}}">Verificar cuenta</a></p>'
        )

    def test_preview_uses_configured_frontend_url(self):
        original = django_settings.FRONTEND_URL
        try:
            django_settings.FRONTEND_URL = 'https://portal.example.edu/'
            res = self.client.post(f'/api/notifications/email-templates/{self.template.pk}/preview/', {}, format='json')
            self.assertEqual(res.status_code, 200)
            self.assertIn('https://portal.example.edu/verify-email', res.data['html'])
            self.assertNotIn('http://localhost:4321', res.data['html'])
        finally:
            django_settings.FRONTEND_URL = original

    @patch('notifications.views.send_mail')
    def test_send_test_uses_configured_frontend_url(self, mock_send):
        original = django_settings.FRONTEND_URL
        try:
            django_settings.FRONTEND_URL = 'https://portal.example.edu/'
            res = self.client.post(f'/api/notifications/email-templates/{self.template.pk}/send-test/', {}, format='json')
            self.assertEqual(res.status_code, 200)
            mock_send.assert_called_once()
            self.assertIn('https://portal.example.edu/verify-email', mock_send.call_args.kwargs['html_message'])
        finally:
            django_settings.FRONTEND_URL = original


class EmailPreferenceAPITests(TestCase):
    """Pruebas de GET/PATCH /api/notifications/email-preferences/ (REQ-NOTIF-02)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='student2', email='s2@test.com', password='testpass123', role='s'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_get_auto_creates_preference(self):
        """GET cuando no existe fila → autogenera con email_enabled=True."""
        self.assertFalse(UserEmailPreference.objects.filter(user=self.user).exists())
        res = self.client.get('/api/notifications/email-preferences/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['email_enabled'])
        self.assertTrue(UserEmailPreference.objects.filter(user=self.user).exists())

    def test_get_returns_existing(self):
        """GET cuando existe fila → devuelve el valor actual."""
        UserEmailPreference.objects.create(user=self.user, email_enabled=False)
        res = self.client.get('/api/notifications/email-preferences/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['email_enabled'])

    def test_patch_updates_preference(self):
        """PATCH actualiza el campo email_enabled."""
        UserEmailPreference.objects.create(user=self.user, email_enabled=True)
        res = self.client.patch(
            '/api/notifications/email-preferences/',
            {'email_enabled': False},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['email_enabled'])

    def test_anonymous_gets_401(self):
        """Solicitud no autenticada → 401."""
        anon = APIClient()
        res = anon.get('/api/notifications/email-preferences/')
        self.assertEqual(res.status_code, 401)


class SystemSettingsAPITests(TestCase):
    """Pruebas de GET/PATCH /api/notifications/system-settings/ (REQ-NOTIF-03)."""

    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin1', email='admin@test.com', password='testpass123', role='a'
        )
        self.student = User.objects.create_user(
            username='student3', email='s3@test.com', password='testpass123', role='s'
        )
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin)
        self.student_client = APIClient()
        self.student_client.force_authenticate(user=self.student)

    def test_admin_get_auto_creates(self):
        """GET de admin cuando no hay fila → autocrea singleton con valor por defecto True."""
        res = self.admin_client.get('/api/notifications/system-settings/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['email_notifications_enabled'])

    def test_admin_toggle_off(self):
        """PATCH de admin para deshabilitar."""
        res = self.admin_client.patch(
            '/api/notifications/system-settings/',
            {'email_notifications_enabled': False},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['email_notifications_enabled'])

    def test_admin_toggle_on(self):
        """PATCH de admin para habilitar."""
        SystemSettings.objects.create(pk=1, email_notifications_enabled=False)
        res = self.admin_client.patch(
            '/api/notifications/system-settings/',
            {'email_notifications_enabled': True},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['email_notifications_enabled'])

    def test_student_gets_403(self):
        """Usuario no admin → 403 Forbidden."""
        res = self.student_client.get('/api/notifications/system-settings/')
        self.assertEqual(res.status_code, 403)

    def test_student_patch_gets_403(self):
        """PATCH de no admin → 403 Forbidden."""
        res = self.student_client.patch(
            '/api/notifications/system-settings/',
            {'email_notifications_enabled': False},
            format='json',
        )
        self.assertEqual(res.status_code, 403)

    def test_admin_patch_accepts_ui_extra_charges_without_client_metadata(self):
        """PATCH acepta payload UI y normaliza excluyendo metadatos de cliente."""
        res = self.admin_client.patch(
            '/api/notifications/system-settings/',
            {
                'enrollment_extra_charges': [
                    {
                        'label': 'Carné universitario',
                        'amount': '12.00',
                        'active': True,
                        'clientId': 'tmp-1',
                        'errors': {'amount': 'legacy'},
                    }
                ]
            },
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res.data['enrollment_extra_charges'],
            [{'label': 'Carné universitario', 'amount': '12.00', 'active': True}],
        )

    def test_admin_can_update_admission_waitlist_grace_days(self):
        res = self.admin_client.patch(
            '/api/notifications/system-settings/',
            {'admission_waitlist_grace_days': 12},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['admission_waitlist_grace_days'], 12)


class WithdrawNotifyWaitlistIntegrationTest(TestCase):
    """Prueba de integración: withdraw → notify_next_waitlisted → create_notification (S-02)."""

    def setUp(self):
        from academic.models import Career, AcademicPeriod
        from admissions.models import AdmissionApplication, AdmissionPreference
        from datetime import date

        self.career = Career.objects.create(name='CS', code='CS01', total_spots=1)
        self.period = AcademicPeriod.objects.create(
            name='2026-1', code='2026-1', start_date=date(2026, 3, 1), end_date=date(2026, 7, 1)
        )
        self.waitlisted_student = User.objects.create_user(
            username='waitlisted', email='wait@test.com', password='testpass123', role='s'
        )
        self.application = AdmissionApplication.objects.create(
            student=self.waitlisted_student,
            academic_period=self.period,
            status='waitlisted',
        )
        AdmissionPreference.objects.create(
            application=self.application,
            career=self.career,
            preference_order=1,
            status='waitlisted',
            waitlist_position=1,
        )
        SystemSettings.objects.get_or_create(pk=1, defaults={'email_notifications_enabled': True})
        UserEmailPreference.objects.create(user=self.waitlisted_student, email_enabled=True)

    @patch('notifications.utils.send_mail')
    def test_notify_next_waitlisted_sends_email(self, mock_send):
        """notify_next_waitlisted() crea notificación Y envía correo al estudiante en lista de espera."""
        notify_next_waitlisted(self.career, self.period)

        # Notificación creada
        notif = Notification.objects.filter(user=self.waitlisted_student).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.event_type, 'waitlist')
        self.assertIn('plaza', notif.message.lower())

        # Correo enviado
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.kwargs['recipient_list'], ['wait@test.com'])
