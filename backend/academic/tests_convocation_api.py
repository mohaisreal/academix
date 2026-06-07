from django.test import TestCase
from rest_framework.test import APIClient

from users.models import User
from academic.models import Career, AcademicPeriod, Subject, Class
from grades.models import Evaluation, Grade


class CareerConvocationApiTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.student = User.objects.create_user(
            username='student_api',
            email='student_api@test.com',
            password='testpass123',
            role='s',
            is_active=True,
        )
        self.career = Career.objects.create(name='Ingeniería', code='ING-API')
        self.period_1 = AcademicPeriod.objects.create(name='2025-1', code='20251API', start_date='2025-01-01', end_date='2025-06-30')
        self.period_2 = AcademicPeriod.objects.create(name='2025-2', code='20252API', start_date='2025-07-01', end_date='2025-12-31')
        self.subject = Subject.objects.create(name='Álgebra', code='ALG-API', career=self.career, max_convocations=1)
        self.class_prev = Class.objects.create(subject=self.subject, period=self.period_1)
        self.class_target = Class.objects.create(subject=self.subject, period=self.period_2)
        self.eval_prev = Evaluation.objects.create(name='Final prev', cls=self.class_prev, is_final_grade=True)
        Grade.objects.create(student=self.student, evaluation=self.eval_prev, score='3.0')
        self.client.force_authenticate(user=self.student)

    def test_classes_by_career_exposes_convocation_fields(self):
        response = self.client.get(f'/api/academic/careers/{self.career.id}/classes/?period={self.period_2.id}')

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(len(payload), 1)
        row = next(item for item in payload if item['id'] == self.class_target.id)
        self.assertEqual(row['convocation_eligibility'], 'blocked')
        self.assertEqual(row['failed_convocations'], 1)
        self.assertEqual(row['max_convocations'], 1)
        self.assertEqual(row['convocation_block_reason'], 'limit_reached')
