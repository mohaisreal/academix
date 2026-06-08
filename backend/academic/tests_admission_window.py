"""
Pruebas TDD para los campos de ventana de admisión en AcademicPeriod.
Fase RED: escritas antes de cambios en modelo/serializador.
"""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User
from academic.models import AcademicPeriod
from academic.serializers import AcademicPeriodSerializer


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def make_manager():
    user = User.objects.create_user(
        username='mgr_window', email='mgr@test.com', password='testpass123', is_active=True,
    )
    user.role = 'm'
    user.save()
    return user


def make_period(**kwargs):
    defaults = dict(
        name='Test Period', code='TP2026',
        start_date='2026-01-01', end_date='2026-06-30',
    )
    defaults.update(kwargs)
    return AcademicPeriod.objects.create(**defaults)


# ---------------------------------------------------------------------------
# Pruebas de modelos
# ---------------------------------------------------------------------------

class AcademicPeriodAdmissionWindowModelTests(TestCase):

    def test_admission_open_date_field_exists_and_is_nullable(self):
        """AcademicPeriod DEBE tener admission_open_date como DateTimeField anulable."""
        period = make_period()
        self.assertIsNone(period.admission_open_date)

    def test_admission_close_date_field_exists_and_is_nullable(self):
        """AcademicPeriod DEBE tener admission_close_date como DateTimeField anulable."""
        period = make_period()
        self.assertIsNone(period.admission_close_date)

    def test_admission_window_can_be_set(self):
        """Ambos campos datetime DEBEN aceptar y persistir valores datetime."""
        period = make_period(
            admission_open_date='2026-01-15T09:00:00Z',
            admission_close_date='2026-02-28T23:59:00Z',
        )
        period.refresh_from_db()
        self.assertIsNotNone(period.admission_open_date)
        self.assertIsNotNone(period.admission_close_date)

    def test_admission_window_can_coexist_with_academic_dates(self):
        """Los campos de ventana de admisión son independientes de start_date/end_date."""
        period = make_period(
            start_date='2026-01-01', end_date='2026-06-30',
            admission_open_date='2025-11-01T00:00:00Z',
            admission_close_date='2025-12-31T23:59:59Z',
        )
        period.refresh_from_db()
        self.assertEqual(str(period.start_date), '2026-01-01')
        self.assertIsNotNone(period.admission_open_date)


# ---------------------------------------------------------------------------
# Pruebas de serializadores
# ---------------------------------------------------------------------------

class AcademicPeriodSerializerAdmissionWindowTests(TestCase):

    def test_serializer_includes_admission_open_date(self):
        """AcademicPeriodSerializer DEBE exponer admission_open_date."""
        period = make_period(admission_open_date='2026-01-15T09:00:00Z')
        data = AcademicPeriodSerializer(period).data
        self.assertIn('admission_open_date', data)
        self.assertIsNotNone(data['admission_open_date'])

    def test_serializer_includes_admission_close_date(self):
        """AcademicPeriodSerializer DEBE exponer admission_close_date."""
        period = make_period(admission_close_date='2026-02-28T23:59:00Z')
        data = AcademicPeriodSerializer(period).data
        self.assertIn('admission_close_date', data)
        self.assertIsNotNone(data['admission_close_date'])

    def test_serializer_returns_null_when_dates_not_set(self):
        """El serializador DEBE devolver null para fechas de admisión no definidas (sin omitir la clave)."""
        period = make_period()
        data = AcademicPeriodSerializer(period).data
        self.assertIn('admission_open_date', data)
        self.assertIn('admission_close_date', data)
        self.assertIsNone(data['admission_open_date'])
        self.assertIsNone(data['admission_close_date'])

    def test_serializer_accepts_admission_dates_on_write(self):
        """El serializador DEBE aceptar admission_open_date y admission_close_date al crear."""
        payload = {
            'name': 'Write Test Period', 'code': 'WTP2026',
            'start_date': '2026-01-01', 'end_date': '2026-06-30',
            'admission_open_date': '2025-11-01T09:00:00Z',
            'admission_close_date': '2025-12-15T23:59:00Z',
        }
        serializer = AcademicPeriodSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        period = serializer.save()
        self.assertIsNotNone(period.admission_open_date)
        self.assertIsNotNone(period.admission_close_date)


# ---------------------------------------------------------------------------
# Pruebas de endpoints de API
# ---------------------------------------------------------------------------

class AcademicPeriodAPIAdmissionWindowTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.manager = make_manager()
        self.client.force_authenticate(user=self.manager)

    def test_api_list_returns_admission_window_fields(self):
        """GET /api/academic/periods/ DEBE incluir fechas de admisión en la respuesta."""
        make_period(
            admission_open_date='2026-01-15T09:00:00Z',
            admission_close_date='2026-02-28T23:59:00Z',
        )
        res = self.client.get('/api/academic/periods/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        # Gestiona tanto respuestas paginadas {"results": [...]} como listas simples
        periods = data.get('results', data) if isinstance(data, dict) else data
        self.assertGreater(len(periods), 0)
        self.assertIn('admission_open_date', periods[0])
        self.assertIn('admission_close_date', periods[0])

    def test_api_create_period_with_admission_window(self):
        """POST /api/academic/periods/ DEBE guardar datetimes de la ventana de admisión."""
        payload = {
            'name': 'Spring 2026', 'code': 'SP2026',
            'start_date': '2026-01-01', 'end_date': '2026-06-30',
            'admission_open_date': '2025-11-01T09:00:00Z',
            'admission_close_date': '2025-12-15T23:59:00Z',
        }
        res = self.client.post('/api/academic/periods/', payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.json()
        self.assertIsNotNone(data['admission_open_date'])
        self.assertIsNotNone(data['admission_close_date'])

    def test_api_list_filters_by_is_active(self):
        make_period(code='OLD-AP', is_active=False)
        active_period = make_period(code='NEW-AP', is_active=True)

        res = self.client.get('/api/academic/periods/', {'is_active': 'true'})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        periods = data.get('results', data) if isinstance(data, dict) else data
        self.assertEqual([item['id'] for item in periods], [active_period.id])
