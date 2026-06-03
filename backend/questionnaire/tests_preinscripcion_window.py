from django.test import TestCase
from rest_framework.test import APIClient

from academic.models import AcademicPeriod
from users.models import User
from questionnaire.models import Questionnaire


class PreinscripcionWindowBlockingTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = User.objects.create_user(
            username='student_window', email='student_window@test.com', password='testpass123', role='s', is_active=True,
        )
        self.client.force_authenticate(user=self.student)

    def test_preinscripcion_wizard_rejects_when_no_period_window_is_open(self):
        AcademicPeriod.objects.create(
            name='2026-1', code='2026-1', is_active=True,
            start_date='2026-03-01', end_date='2026-07-31',
            admission_open_date='2025-11-01T09:00:00Z',
            admission_close_date='2025-11-30T23:59:00Z',
        )
        questionnaire = Questionnaire.objects.create(
            title='Preinscripción',
            description='Wizard',
            flow_type='admissions',
            is_active=True,
            is_preinscripcion_wizard=True,
            created_by=self.student,
        )

        response = self.client.post(f'/api/questionnaire/questionnaires/{questionnaire.pk}/start/')

        self.assertEqual(response.status_code, 400)
        self.assertIn('ventana', response.json()['detail'].lower())

    def test_preinscripcion_wizard_allows_when_window_is_open(self):
        AcademicPeriod.objects.create(
            name='2026-1', code='2026-1', is_active=True,
            start_date='2026-03-01', end_date='2026-07-31',
            admission_open_date='2026-01-01T00:00:00Z',
            admission_close_date='2026-12-31T23:59:59Z',
        )
        questionnaire = Questionnaire.objects.create(
            title='Preinscripción',
            description='Wizard',
            flow_type='admissions',
            is_active=True,
            is_preinscripcion_wizard=True,
            created_by=self.student,
        )

        response = self.client.post(f'/api/questionnaire/questionnaires/{questionnaire.pk}/start/')

        self.assertIn(response.status_code, (200, 201))
