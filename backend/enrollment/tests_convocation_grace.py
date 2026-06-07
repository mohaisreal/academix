from django.test import TestCase

from users.models import User
from academic.models import Career, AcademicPeriod, Subject
from enrollment.models import ExceptionalConvocationGrace


class ExceptionalConvocationGraceModelTests(TestCase):

    def setUp(self):
        self.student = User.objects.create_user(
            username='student_grace',
            email='student_grace@test.com',
            password='testpass123',
            role='s',
            is_active=True,
        )
        self.grantor = User.objects.create_user(
            username='manager_grace',
            email='manager_grace@test.com',
            password='testpass123',
            role='m',
            is_active=True,
        )
        self.career = Career.objects.create(name='Ingeniería', code='ING-GRACE')
        self.period = AcademicPeriod.objects.create(
            name='2026-GR',
            code='2026GR',
            start_date='2026-01-01',
            end_date='2026-06-30',
        )
        self.subject = Subject.objects.create(name='Cálculo', code='CAL-GRACE', career=self.career)

    def test_grace_unique_for_student_subject_period(self):
        ExceptionalConvocationGrace.objects.create(
            student=self.student,
            subject=self.subject,
            period=self.period,
            granted_by=self.grantor,
            reason='Academic exception',
        )

        with self.assertRaises(Exception):
            ExceptionalConvocationGrace.objects.create(
                student=self.student,
                subject=self.subject,
                period=self.period,
                granted_by=self.grantor,
                reason='Duplicate exception',
            )

    def test_grace_defaults_to_active(self):
        grace = ExceptionalConvocationGrace.objects.create(
            student=self.student,
            subject=self.subject,
            period=self.period,
            granted_by=self.grantor,
            reason='Academic exception',
        )

        self.assertTrue(grace.is_active)
