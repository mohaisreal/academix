from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from academic.models import AcademicPeriod, Career, Class, Subject
from enrollment.models import CareerEnrollment, ClassEnrollment
from grades.models import Evaluation, Grade
from users.models import User


class PeriodScopedGradesViewsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = User.objects.create_user(username='student_period', password='pass12345', role='s')
        self.career = Career.objects.create(name='Ingeniería', code='ING-PER')

        self.old_period = AcademicPeriod.objects.create(
            name='2025-A', code='2025A', start_date='2025-01-01', end_date='2025-06-30', is_active=False
        )
        self.new_period = AcademicPeriod.objects.create(
            name='2026-A', code='2026A', start_date='2026-01-01', end_date='2026-06-30', is_active=True
        )

        self.old_subject = Subject.objects.create(name='Historia', code='HIS-PER', career=self.career)
        self.new_subject = Subject.objects.create(name='Física', code='FIS-PER', career=self.career)

        self.old_class = Class.objects.create(subject=self.old_subject, period=self.old_period)
        self.new_class = Class.objects.create(subject=self.new_subject, period=self.new_period)

        CareerEnrollment.objects.create(student=self.student, career=self.career, period=self.old_period, status='active')
        CareerEnrollment.objects.create(student=self.student, career=self.career, period=self.new_period, status='active')
        ClassEnrollment.objects.create(student=self.student, cls=self.old_class, status='enrolled')
        ClassEnrollment.objects.create(student=self.student, cls=self.new_class, status='enrolled')

        self.old_eval = Evaluation.objects.create(name='Parcial viejo', cls=self.old_class, max_score=10)
        self.new_eval = Evaluation.objects.create(name='Parcial nuevo', cls=self.new_class, max_score=10)
        Grade.objects.create(student=self.student, evaluation=self.old_eval, score=6)
        Grade.objects.create(student=self.student, evaluation=self.new_eval, score=9)

    def test_my_grades_uses_active_period_only(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.get('/api/grades/my-grades/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['subject_code'], 'FIS-PER')

    def test_my_file_keeps_historical_periods(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.get('/api/grades/my-file/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([period['period_name'] for period in response.data['periods']], ['2026-A', '2025-A'])

    def test_my_grades_returns_empty_when_no_active_period(self):
        self.new_period.is_active = False
        self.new_period.save(update_fields=['is_active'])

        self.client.force_authenticate(user=self.student)

        response = self.client.get('/api/grades/my-grades/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])


class StatisticsPeriodScopingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(username='manager_stats', password='pass12345', role='m')
        self.career = Career.objects.create(name='Ingeniería', code='ING-STATS')
        self.old_period = AcademicPeriod.objects.create(
            name='2025-A', code='2025ASTATS', start_date='2025-01-01', end_date='2025-06-30', is_active=False
        )
        self.new_period = AcademicPeriod.objects.create(
            name='2026-A', code='2026ASTATS', start_date='2026-01-01', end_date='2026-06-30', is_active=True
        )
        self.old_subject = Subject.objects.create(name='Historia', code='HIS-STATS', career=self.career)
        self.new_subject = Subject.objects.create(name='Física', code='FIS-STATS', career=self.career)
        self.old_class = Class.objects.create(subject=self.old_subject, period=self.old_period)
        self.new_class = Class.objects.create(subject=self.new_subject, period=self.new_period)
        self.old_student = User.objects.create_user(username='student_old_stats', password='pass12345', role='s')
        self.new_student = User.objects.create_user(username='student_new_stats', password='pass12345', role='s')
        CareerEnrollment.objects.create(student=self.old_student, career=self.career, period=self.old_period, status='active')
        CareerEnrollment.objects.create(student=self.new_student, career=self.career, period=self.new_period, status='active')
        ClassEnrollment.objects.create(student=self.old_student, cls=self.old_class, status='enrolled')
        ClassEnrollment.objects.create(student=self.new_student, cls=self.new_class, status='enrolled')
        old_eval = Evaluation.objects.create(name='Parcial viejo', cls=self.old_class, max_score=10)
        new_eval = Evaluation.objects.create(name='Parcial nuevo', cls=self.new_class, max_score=10)
        Grade.objects.create(student=self.old_student, evaluation=old_eval, score=2)
        Grade.objects.create(student=self.new_student, evaluation=new_eval, score=9)
        self.active_teacher = User.objects.create_user(username='teacher_stats', password='pass12345', role='t')
        Class.objects.create(subject=Subject.objects.create(name='Química', code='QUI-STATS', career=self.career), period=self.new_period, teacher=self.active_teacher)

    def test_statistics_scopes_to_active_period(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.get('/api/grades/statistics/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['kpis']['active_classes'], 2)
        self.assertEqual(response.data['kpis']['platform_gpa'], 9.0)
        self.assertEqual(response.data['career_stats'][0]['avg_gpa'], 9.0)
        self.assertEqual(response.data['career_stats'][0]['classes'], 2)
        self.assertEqual(response.data['career_stats'][0]['student_count'], 1)
        self.assertEqual(response.data['enrolment_by_status'].get('active'), 1)
