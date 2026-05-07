from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from users.models import User
from .models import Notification, UserEmailPreference, SystemSettings, EmailTemplate
from .utils import create_notification
from admissions.utils import notify_next_waitlisted


class CreateNotificationEmailTests(TestCase):
    """Tests for create_notification() email gating logic (REQ-NOTIF-01)."""

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
        """Both system and user enabled → email sent."""
        SystemSettings.objects.get_or_create(pk=1, defaults={'email_notifications_enabled': True})
        UserEmailPreference.objects.create(user=self.user, email_enabled=True)

        notif = create_notification(self.user, 'Test', 'Hello', 'info', event_type='test')

        self.assertIsNotNone(notif)
        self.assertEqual(notif.event_type, 'test')
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.kwargs['recipient_list'], ['student1@test.com'])

    @patch('notifications.utils.send_mail')
    def test_user_disabled_no_email(self, mock_send):
        """User opted out → no email."""
        SystemSettings.objects.get_or_create(pk=1, defaults={'email_notifications_enabled': True})
        UserEmailPreference.objects.create(user=self.user, email_enabled=False)

        notif = create_notification(self.user, 'Test', 'Hello')

        self.assertIsNotNone(notif)
        mock_send.assert_not_called()

    @patch('notifications.utils.send_mail')
    def test_system_disabled_no_email(self, mock_send):
        """System disabled → no email even if user enabled."""
        SystemSettings.objects.create(pk=1, email_notifications_enabled=False)
        UserEmailPreference.objects.create(user=self.user, email_enabled=True)

        create_notification(self.user, 'Test', 'Hello')

        mock_send.assert_not_called()

    @patch('notifications.utils.send_mail')
    def test_no_email_address_no_send(self, mock_send):
        """User has no email → no email attempt."""
        self.user.email = ''
        self.user.save()

        create_notification(self.user, 'Test', 'Hello')

        mock_send.assert_not_called()

    @patch('notifications.utils.send_mail')
    def test_send_mail_called_with_fail_silently(self, mock_send):
        """send_mail is called with fail_silently=True so SMTP errors don't crash."""
        SystemSettings.objects.get_or_create(pk=1, defaults={'email_notifications_enabled': True})
        UserEmailPreference.objects.create(user=self.user, email_enabled=True)

        notif = create_notification(self.user, 'Test', 'Hello')

        self.assertIsNotNone(notif)
        self.assertTrue(Notification.objects.filter(pk=notif.pk).exists())
        mock_send.assert_called_once()
        self.assertTrue(mock_send.call_args.kwargs['fail_silently'])

    def test_backward_compat_no_event_type(self):
        """Calling without event_type still works (backward compat)."""
        notif = create_notification(self.user, 'Test', 'Hello', 'info')
        self.assertEqual(notif.event_type, '')

    @patch('notifications.utils.send_mail')
    def test_profile_only_creates_notification_without_email(self, mock_send):
        """Profile-only channel → notification row, no email."""
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
        """Email-only channel → email sent, no profile notification row."""
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
        """Disabled event key → no profile notification and no email."""
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


class EmailPreferenceAPITests(TestCase):
    """Tests for GET/PATCH /api/notifications/email-preferences/ (REQ-NOTIF-02)."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='student2', email='s2@test.com', password='testpass123', role='s'
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_get_auto_creates_preference(self):
        """GET when no row exists → auto-creates with email_enabled=True."""
        self.assertFalse(UserEmailPreference.objects.filter(user=self.user).exists())
        res = self.client.get('/api/notifications/email-preferences/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['email_enabled'])
        self.assertTrue(UserEmailPreference.objects.filter(user=self.user).exists())

    def test_get_returns_existing(self):
        """GET when row exists → returns current value."""
        UserEmailPreference.objects.create(user=self.user, email_enabled=False)
        res = self.client.get('/api/notifications/email-preferences/')
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['email_enabled'])

    def test_patch_updates_preference(self):
        """PATCH updates email_enabled field."""
        UserEmailPreference.objects.create(user=self.user, email_enabled=True)
        res = self.client.patch(
            '/api/notifications/email-preferences/',
            {'email_enabled': False},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['email_enabled'])

    def test_anonymous_gets_401(self):
        """Unauthenticated request → 401."""
        anon = APIClient()
        res = anon.get('/api/notifications/email-preferences/')
        self.assertEqual(res.status_code, 401)


class SystemSettingsAPITests(TestCase):
    """Tests for GET/PATCH /api/notifications/system-settings/ (REQ-NOTIF-03)."""

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
        """Admin GET when no row → auto-creates singleton with default True."""
        res = self.admin_client.get('/api/notifications/system-settings/')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['email_notifications_enabled'])

    def test_admin_toggle_off(self):
        """Admin PATCH to disable."""
        res = self.admin_client.patch(
            '/api/notifications/system-settings/',
            {'email_notifications_enabled': False},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data['email_notifications_enabled'])

    def test_admin_toggle_on(self):
        """Admin PATCH to enable."""
        SystemSettings.objects.create(pk=1, email_notifications_enabled=False)
        res = self.admin_client.patch(
            '/api/notifications/system-settings/',
            {'email_notifications_enabled': True},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['email_notifications_enabled'])

    def test_student_gets_403(self):
        """Non-admin user → 403 Forbidden."""
        res = self.student_client.get('/api/notifications/system-settings/')
        self.assertEqual(res.status_code, 403)

    def test_student_patch_gets_403(self):
        """Non-admin PATCH → 403 Forbidden."""
        res = self.student_client.patch(
            '/api/notifications/system-settings/',
            {'email_notifications_enabled': False},
            format='json',
        )
        self.assertEqual(res.status_code, 403)


class WithdrawNotifyWaitlistIntegrationTest(TestCase):
    """Integration test: withdraw → notify_next_waitlisted → create_notification (S-02)."""

    def setUp(self):
        from academic.models import Career, AcademicPeriod
        from admissions.models import AdmissionApplication
        from datetime import date

        self.career = Career.objects.create(name='CS', code='CS01', total_spots=1)
        self.period = AcademicPeriod.objects.create(
            name='2026-1', code='2026-1', start_date=date(2026, 3, 1), end_date=date(2026, 7, 1)
        )
        self.waitlisted_student = User.objects.create_user(
            username='waitlisted', email='wait@test.com', password='testpass123', role='s'
        )
        AdmissionApplication.objects.create(
            student=self.waitlisted_student,
            career=self.career,
            academic_period=self.period,
            status='waitlisted',
        )
        SystemSettings.objects.get_or_create(pk=1, defaults={'email_notifications_enabled': True})
        UserEmailPreference.objects.create(user=self.waitlisted_student, email_enabled=True)

    @patch('notifications.utils.send_mail')
    def test_notify_next_waitlisted_sends_email(self, mock_send):
        """notify_next_waitlisted() creates notification AND sends email to waitlisted student."""
        notify_next_waitlisted(self.career, self.period)

        # Notificación creada
        notif = Notification.objects.filter(user=self.waitlisted_student).first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.event_type, 'waitlist')
        self.assertIn('plaza', notif.message.lower())

        # Correo enviado
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.kwargs['recipient_list'], ['wait@test.com'])
