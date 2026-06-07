from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User
from academic.models import Career, AcademicPeriod, Subject, Class
from grades.models import Evaluation, Grade
from enrollment.models import CareerEnrollment, ExceptionalConvocationGrace


class ConvocationEnrollmentEnforcementTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.student = User.objects.create_user(username='student_post', email='student_post@test.com', password='testpass123', role='s', is_active=True)
        self.manager = User.objects.create_user(username='manager_post', email='manager_post@test.com', password='testpass123', role='m', is_active=True)
        self.admin = User.objects.create_user(username='admin_post', email='admin_post@test.com', password='testpass123', role='a', is_active=True)
        self.career = Career.objects.create(name='Ingeniería', code='ING-POST')
        self.period_1 = AcademicPeriod.objects.create(name='2025-1', code='20251POST', start_date='2025-01-01', end_date='2025-06-30')
        self.period_2 = AcademicPeriod.objects.create(name='2025-2', code='20252POST', start_date='2025-07-01', end_date='2025-12-31')
        self.subject = Subject.objects.create(name='Álgebra', code='ALG-POST', career=self.career, max_convocations=1)
        self.cls_prev = Class.objects.create(subject=self.subject, period=self.period_1)
        self.cls_target = Class.objects.create(subject=self.subject, period=self.period_2)
        self.final_eval = Evaluation.objects.create(name='Final', cls=self.cls_prev, is_final_grade=True)
        Grade.objects.create(student=self.student, evaluation=self.final_eval, score='3.0')
        CareerEnrollment.objects.create(student=self.student, career=self.career, period=self.period_2, status='pending')

    def test_blocked_post_is_rejected_before_schedule_and_capacity(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/enrollment/class-enrollments/', {'class_id': self.cls_target.id}, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['code'], 'convocation_blocked')
        self.assertEqual(response.data['convocation_eligibility'], 'blocked')

    def test_manager_can_grant_and_revoke_grace_for_target_period(self):
        self.client.force_authenticate(user=self.manager)
        grant_response = self.client.post(
            f'/api/enrollment/students/{self.student.id}/convocation-graces/',
            {'subject_id': self.subject.id, 'period_id': self.period_2.id, 'reason': 'Exception approved'},
            format='json',
        )

        self.assertEqual(grant_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(grant_response.data['convocation_eligibility'], 'extraordinary-grace')
        self.assertTrue(ExceptionalConvocationGrace.objects.filter(student=self.student, subject=self.subject, period=self.period_2, is_active=True).exists())

        grace_id = grant_response.data['grace']['id']
        revoke_response = self.client.patch(
            f'/api/enrollment/convocation-graces/{grace_id}/',
            {'is_active': False},
            format='json',
        )

        self.assertEqual(revoke_response.status_code, status.HTTP_200_OK)
        self.assertFalse(ExceptionalConvocationGrace.objects.get(pk=grace_id).is_active)

    def test_admin_can_grant_grace_and_get_exceptional_cases_context(self):
        self.client.force_authenticate(user=self.admin)
        get_response = self.client.get(f'/api/enrollment/students/{self.student.id}/exceptional-cases/?period={self.period_2.id}')

        self.assertEqual(get_response.status_code, status.HTTP_200_OK)
        self.assertEqual(get_response.data['period']['id'], self.period_2.id)
        self.assertEqual(get_response.data['career']['id'], self.career.id)
        self.assertGreaterEqual(len(get_response.data['subjects']), 1)

        grant_response = self.client.post(
            f'/api/enrollment/students/{self.student.id}/convocation-graces/',
            {'subject_id': self.subject.id, 'period_id': self.period_2.id, 'reason': 'Exception approved by admin'},
            format='json',
        )

        self.assertEqual(grant_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(grant_response.data['convocation_eligibility'], 'extraordinary-grace')

    def test_unauthorized_user_cannot_grant_grace(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            f'/api/enrollment/students/{self.student.id}/convocation-graces/',
            {'subject_id': self.subject.id, 'period_id': self.period_2.id, 'reason': 'Exception approved'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
