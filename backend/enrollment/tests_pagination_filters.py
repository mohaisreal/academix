from django.test import TestCase
from rest_framework.test import APIClient

from users.models import User
from academic.models import Career, AcademicPeriod
from enrollment.models import CareerEnrollment


class EnrollmentManagementPaginationFiltersTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(username='manager_pf', email='manager_pf@test.com', password='testpass123', role='m', is_active=True)
        self.client.force_authenticate(user=self.manager)
        self.student_a = User.objects.create_user(username='student_pa', email='student_pa@test.com', password='testpass123', role='s', is_active=True)
        self.student_b = User.objects.create_user(username='student_pb', email='student_pb@test.com', password='testpass123', role='s', is_active=True)
        self.career_a = Career.objects.create(name='Ingeniería', code='INGP', duration_years=4)
        self.career_b = Career.objects.create(name='Historia', code='HISP', duration_years=4)
        self.period = AcademicPeriod.objects.create(name='2026-P', code='2026P', is_active=True, start_date='2026-01-01', end_date='2026-06-30')

    def test_management_endpoint_filters_by_status_and_career(self):
        CareerEnrollment.objects.create(student=self.student_a, career=self.career_a, period=self.period, status='active')
        CareerEnrollment.objects.create(student=self.student_b, career=self.career_b, period=self.period, status='pending')

        response = self.client.get(f'/api/enrollment/management/?status=active&career={self.career_a.id}&page=1')
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['count'], 1)
        self.assertEqual(payload['results'][0]['status'], 'active')
