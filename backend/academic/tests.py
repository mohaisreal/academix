from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User
from academic.models import Career, AcademicPeriod, Subject


class CareerAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='student', password='pass12345', role='s')
        self.period = AcademicPeriod.objects.create(
            name='2026',
            code='2026',
            start_date='2026-01-01',
            end_date='2026-12-31',
            is_active=True,
        )
        self.career = Career.objects.create(
            name='Administración',
            code='ADM',
            duration_years=4,
            total_spots=50,
        )
        Subject.objects.create(name='Base', code='ADM-1', career=self.career)

    def test_list_careers_returns_200_and_serializer_fields(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/academic/careers/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['results'])
        row = response.data['results'][0]
        self.assertIn('subjects_count', row)
        self.assertIn('available_spots', row)
        self.assertIn('convocation_eligibility', row)
