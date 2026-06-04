from datetime import timedelta
from io import StringIO

from django.test import TestCase, override_settings
from django.core.management import call_command
from django.utils import timezone

from academic.models import AcademicPeriod, Career
from admissions.models import AdmissionApplication, AdmissionPreference
from notifications.models import SystemSettings
from admissions.services.career_resolver import resolve_assigned_preference
from admissions.services.expiry_sweep import run_admission_expiry_sweep
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
            admission_close_date=timezone.now() - timedelta(days=1),
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

    def test_resolve_assigned_preference_skips_waitlisted_and_returns_next_admitted(self):
        app = AdmissionApplication.objects.create(
            student=self.student,
            academic_period=self.period,
            status='admitted',
            assigned_career=self.career,
            assigned_preference_order=1,
        )
        first = AdmissionPreference.objects.create(
            application=app,
            career=self.career,
            preference_order=1,
            status='waitlisted',
        )
        next_career = Career.objects.create(name='Derecho', code='DER', duration_years=4)
        second = AdmissionPreference.objects.create(
            application=app,
            career=next_career,
            preference_order=2,
            status='admitted',
        )

        resolved = resolve_assigned_preference(app, excluded_preference_ids=[first.pk])

        self.assertEqual(resolved.pk, second.pk)

    def test_expiry_sweep_rejects_waitlisted_and_reassigns_fallback_career(self):
        SystemSettings.objects.create(pk=1, admission_waitlist_grace_days=0)
        another_career = Career.objects.create(name='Derecho', code='DER', duration_years=4)
        admitted_app = AdmissionApplication.objects.create(
            student=self.student,
            academic_period=self.period,
            status='admitted',
            assigned_career=self.career,
            assigned_preference_order=1,
            admission_expiry_date=timezone.now() - timedelta(minutes=1),
        )
        AdmissionPreference.objects.create(
            application=admitted_app,
            career=self.career,
            preference_order=1,
            status='admitted',
            is_assigned=True,
        )
        fallback_pref = AdmissionPreference.objects.create(
            application=admitted_app,
            career=another_career,
            preference_order=2,
            status='admitted',
        )

        waitlisted_app = AdmissionApplication.objects.create(
            student=User.objects.create_user(
                username='waitstudent2', email='waitstudent2@test.com', password='testpass123', role='s', is_active=True,
            ),
            academic_period=self.period,
            status='waitlisted',
        )
        AdmissionPreference.objects.create(
            application=waitlisted_app,
            career=self.career,
            preference_order=1,
            status='waitlisted',
            waitlist_position=1,
        )

        result = run_admission_expiry_sweep(now=timezone.now())

        admitted_app.refresh_from_db()
        waitlisted_app.refresh_from_db()
        fallback_pref.refresh_from_db()

        self.assertEqual(result['expired'], 0)
        self.assertEqual(result['reassigned'], 1)
        self.assertEqual(result['waitlisted_rejected'], 1)
        self.assertEqual(admitted_app.status, 'admitted')
        self.assertEqual(admitted_app.assigned_career, another_career)
        self.assertEqual(admitted_app.assigned_preference_order, 2)
        self.assertIsNotNone(admitted_app.admission_expiry_date)
        self.assertEqual(fallback_pref.status, 'admitted')
        self.assertEqual(waitlisted_app.status, 'rejected')

    def test_expiry_sweep_expires_without_fallback(self):
        app = AdmissionApplication.objects.create(
            student=User.objects.create_user(
                username='nostudent', email='nostudent@test.com', password='testpass123', role='s', is_active=True,
            ),
            academic_period=self.period,
            status='admitted',
            assigned_career=self.career,
            assigned_preference_order=1,
            admission_expiry_date=timezone.now() - timedelta(minutes=1),
        )
        AdmissionPreference.objects.create(
            application=app,
            career=self.career,
            preference_order=1,
            status='admitted',
            is_assigned=True,
        )

        result = run_admission_expiry_sweep(now=timezone.now())

        app.refresh_from_db()
        self.assertEqual(result['expired'], 1)
        self.assertEqual(app.status, 'expired')
        self.assertIsNone(app.assigned_career)
        self.assertIsNone(app.assigned_preference_order)

    def test_expire_admissions_command_supports_dry_run_without_mutation(self):
        app = AdmissionApplication.objects.create(
            student=User.objects.create_user(
                username='commandstudent', email='commandstudent@test.com', password='testpass123', role='s', is_active=True,
            ),
            academic_period=self.period,
            status='admitted',
            assigned_career=self.career,
            assigned_preference_order=1,
            admission_expiry_date=timezone.now() - timedelta(minutes=1),
        )
        AdmissionPreference.objects.create(
            application=app,
            career=self.career,
            preference_order=1,
            status='admitted',
            is_assigned=True,
        )

        stdout = StringIO()
        call_command('expire_admissions', '--dry-run', stdout=stdout)

        app.refresh_from_db()
        self.assertEqual(app.status, 'admitted')
        self.assertIn("'expired': 0", stdout.getvalue())

    def test_expire_admissions_command_forwards_period_id(self):
        other_period = AcademicPeriod.objects.create(
            name='2026-2', code='2026-2', is_active=False,
            start_date='2026-08-01', end_date='2026-12-31',
            admission_close_date=timezone.now() - timedelta(days=2),
        )
        other_app = AdmissionApplication.objects.create(
            student=User.objects.create_user(
                username='periodstudent', email='periodstudent@test.com', password='testpass123', role='s', is_active=True,
            ),
            academic_period=other_period,
            status='admitted',
            assigned_career=self.career,
            assigned_preference_order=1,
            admission_expiry_date=timezone.now() - timedelta(minutes=1),
        )
        AdmissionPreference.objects.create(
            application=other_app,
            career=self.career,
            preference_order=1,
            status='admitted',
            is_assigned=True,
        )

        stdout = StringIO()
        call_command('expire_admissions', '--period-id', str(other_period.pk), stdout=stdout)

        other_app.refresh_from_db()
        self.assertEqual(other_app.status, 'expired')
