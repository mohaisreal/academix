from datetime import timedelta

from django.test import TestCase, override_settings
from django.utils import timezone

from academic.models import AcademicPeriod, Career
from admissions.models import AdmissionApplication, AdmissionPreference
from notifications.models import SystemSettings
from admissions.utils import get_waitlist_admission_expiry, notify_next_waitlisted
from users.models import User


class AdmissionFlowUtilsTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='waitstudent', email='waitstudent@test.com', password='testpass123', role='s', is_active=True,
        )
        self.career = Career.objects.create(name='Ingeniería', code='ING', duration_years=4)
        self.period = AcademicPeriod.objects.create(
            name='2026-1', code='2026-1', is_active=True,
            start_date='2026-03-01', end_date='2026-07-31',
        )

    def test_get_waitlist_admission_expiry_uses_persisted_system_setting_days(self):
        now = timezone.now()

        SystemSettings.objects.create(pk=1, admission_waitlist_grace_days=4)

        with override_settings(ADMISSION_WAITLIST_GRACE_DAYS=3):
            expiry = get_waitlist_admission_expiry(now)

        self.assertEqual(expiry, now + timedelta(days=4))

    def test_notify_next_waitlisted_applies_waitlist_grace_period(self):
        app = AdmissionApplication.objects.create(
            student=self.student,
            academic_period=self.period,
            status='waitlisted',
        )
        pref = AdmissionPreference.objects.create(
            application=app,
            career=self.career,
            preference_order=1,
            status='waitlisted',
            waitlist_position=1,
        )

        now = timezone.now()
        SystemSettings.objects.create(pk=1, admission_waitlist_grace_days=5)
        with override_settings(ADMISSION_WAITLIST_GRACE_DAYS=3):
            promoted = notify_next_waitlisted(self.career, self.period, now=now)

        self.assertIsNotNone(promoted)
        pref.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual(pref.status, 'admitted')
        self.assertEqual(app.status, 'admitted')
        self.assertEqual(app.admission_expiry_date, now + timedelta(days=5))
