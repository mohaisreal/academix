from django.test import TestCase
from rest_framework.test import APIClient

from users.models import User
from questionnaire.models import Questionnaire


class QuestionnaireSearchPaginationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='manager_q', email='manager_q@test.com', password='testpass123', role='m', is_active=True)
        self.client.force_authenticate(user=self.user)
        Questionnaire.objects.create(title='Ingreso medicina', description='Filtro alpha', flow_type='admissions', is_active=True, created_by=self.user)
        Questionnaire.objects.create(title='Matrícula base', description='Beta', flow_type='enrollment', is_active=True, created_by=self.user)

    def test_questionnaire_list_filters_by_search(self):
        response = self.client.get('/api/questionnaire/questionnaires/?search=alpha&page=1')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['results'][0]['title'], 'Ingreso medicina')
