from django.test import TestCase

from users.models import User
from academic.models import Career, AcademicPeriod, Subject, Class
from grades.models import Evaluation, Grade
from enrollment.models import ExceptionalConvocationGrace
from enrollment.services import resolve_convocation_eligibility


class ConvocationEligibilityServiceTests(TestCase):

    def setUp(self):
        self.student = User.objects.create_user(
            username='student_elig',
            email='student_elig@test.com',
            password='testpass123',
            role='s',
            is_active=True,
        )
        self.manager = User.objects.create_user(
            username='manager_elig',
            email='manager_elig@test.com',
            password='testpass123',
            role='m',
            is_active=True,
        )
        self.career = Career.objects.create(name='Ingeniería', code='ING-ELIG')
        self.period_1 = AcademicPeriod.objects.create(name='2025-1', code='20251', start_date='2025-01-01', end_date='2025-06-30')
        self.period_2 = AcademicPeriod.objects.create(name='2025-2', code='20252', start_date='2025-07-01', end_date='2025-12-31')
        self.subject = Subject.objects.create(name='Álgebra', code='ALG-ELIG', career=self.career, max_convocations=2)
        self.class_1 = Class.objects.create(subject=self.subject, period=self.period_1)
        self.class_2 = Class.objects.create(subject=self.subject, period=self.period_2)
        self.final_eval_p1 = Evaluation.objects.create(name='Final P1', cls=self.class_1, is_final_grade=True)
        self.non_final_eval_p1 = Evaluation.objects.create(name='Partial P1', cls=self.class_1, is_final_grade=False)
        self.final_eval_p2 = Evaluation.objects.create(name='Final P2', cls=self.class_2, is_final_grade=True)

    def test_counts_only_previous_period_final_failures(self):
        Grade.objects.create(student=self.student, evaluation=self.final_eval_p1, score='4.0')
        Grade.objects.create(student=self.student, evaluation=self.non_final_eval_p1, score='1.0')
        Grade.objects.create(student=self.student, evaluation=self.final_eval_p2, score='4.0')

        result = resolve_convocation_eligibility(self.student, self.subject, self.period_2)

        self.assertEqual(result['failed_convocations'], 1)
        self.assertEqual(result['convocation_eligibility'], 'allowed')

    def test_blocks_when_failed_count_reaches_limit_without_grace(self):
        other_period = AcademicPeriod.objects.create(name='2024-2', code='20242', start_date='2024-07-01', end_date='2024-12-31')
        class_prev = Class.objects.create(subject=self.subject, period=other_period)
        final_eval_prev = Evaluation.objects.create(name='Final prev', cls=class_prev, is_final_grade=True)
        Grade.objects.create(student=self.student, evaluation=final_eval_prev, score='3.0')
        Grade.objects.create(student=self.student, evaluation=self.final_eval_p1, score='3.5')

        result = resolve_convocation_eligibility(self.student, self.subject, self.period_2)

        self.assertEqual(result['failed_convocations'], 2)
        self.assertEqual(result['convocation_eligibility'], 'blocked')
        self.assertEqual(result['convocation_block_reason'], 'limit_reached')

    def test_grace_overrides_block_only_for_target_period(self):
        other_period = AcademicPeriod.objects.create(name='2024-2', code='20242', start_date='2024-07-01', end_date='2024-12-31')
        class_prev = Class.objects.create(subject=self.subject, period=other_period)
        final_eval_prev = Evaluation.objects.create(name='Final prev', cls=class_prev, is_final_grade=True)
        Grade.objects.create(student=self.student, evaluation=final_eval_prev, score='3.0')
        Grade.objects.create(student=self.student, evaluation=self.final_eval_p1, score='3.5')
        ExceptionalConvocationGrace.objects.create(
            student=self.student,
            subject=self.subject,
            period=self.period_2,
            granted_by=self.manager,
            reason='Approved exception',
        )

        result = resolve_convocation_eligibility(self.student, self.subject, self.period_2)

        self.assertEqual(result['convocation_eligibility'], 'extraordinary-grace')
        self.assertEqual(result['failed_convocations'], 2)

    def test_grace_does_not_apply_to_other_subject_or_later_period(self):
        other_subject = Subject.objects.create(name='Cálculo', code='CAL-ELIG', career=self.career, max_convocations=2)
        other_subject_class = Class.objects.create(subject=other_subject, period=self.period_1)
        other_subject_eval = Evaluation.objects.create(name='Final other', cls=other_subject_class, is_final_grade=True)
        Grade.objects.create(student=self.student, evaluation=other_subject_eval, score='3.0')

        Grade.objects.create(student=self.student, evaluation=self.final_eval_p1, score='3.0')
        final_eval_p2 = Evaluation.objects.create(name='Final P2 extra', cls=self.class_2, is_final_grade=True)
        Grade.objects.create(student=self.student, evaluation=final_eval_p2, score='3.0')
        ExceptionalConvocationGrace.objects.create(
            student=self.student,
            subject=self.subject,
            period=self.period_2,
            granted_by=self.manager,
            reason='Approved exception',
        )

        other_subject_result = resolve_convocation_eligibility(self.student, other_subject, self.period_2)
        later_period = AcademicPeriod.objects.create(
            name='2026-1',
            code='20261',
            start_date='2026-01-01',
            end_date='2026-06-30',
        )
        later_period_result = resolve_convocation_eligibility(self.student, self.subject, later_period)

        self.assertEqual(other_subject_result['convocation_eligibility'], 'allowed')
        self.assertEqual(later_period_result['convocation_eligibility'], 'blocked')
