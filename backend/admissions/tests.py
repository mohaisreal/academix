from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User
from academic.models import Career, AcademicPeriod
from admissions.models import AdmissionApplication, AdmissionPreference


class AdmissionApplicationTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.student = User.objects.create_user(
            username='student1', email='student1@test.com',
            password='testpass123', role='s', is_active=True,
        )
        self.manager = User.objects.create_user(
            username='manager1', email='manager1@test.com',
            password='testpass123', role='m', is_active=True,
        )
        self.career = Career.objects.create(
            name='Ingeniería Informática', code='II', duration_years=4,
        )
        self.period = AcademicPeriod.objects.create(
            name='2026-1', code='2026-1', is_active=True,
            start_date='2026-03-01', end_date='2026-07-31',
        )

    def test_student_can_create_application(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/admissions/applications/', {
            'career_id': self.career.pk,
            'academic_period_id': self.period.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'draft')

    def test_student_cannot_create_duplicate_application(self):
        AdmissionApplication.objects.create(
            student=self.student, academic_period=self.period,
            status='submitted',
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/admissions/applications/', {
            'career_id': self.career.pk,
            'academic_period_id': self.period.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_management_cannot_create_application(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post('/api/admissions/applications/', {
            'career_id': self.career.pk,
            'academic_period_id': self.period.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_can_submit_draft_application(self):
        app = AdmissionApplication.objects.create(
            student=self.student, academic_period=self.period,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.patch(f'/api/admissions/applications/{app.pk}/submit/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'submitted')

    def test_student_cannot_submit_already_submitted(self):
        app = AdmissionApplication.objects.create(
            student=self.student, academic_period=self.period,
            status='submitted',
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.patch(f'/api/admissions/applications/{app.pk}/submit/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_management_can_resolve_as_admitted(self):
        app = AdmissionApplication.objects.create(
            student=self.student, academic_period=self.period,
            status='under_review',
        )
        AdmissionPreference.objects.create(
            application=app,
            career=self.career,
            preference_order=1,
        )
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            f'/api/admissions/applications/{app.pk}/definitive-resolve/',
            {'status': 'admitted', 'preference_order': 1, 'notes': 'Aprobado'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'admitted')

    def test_confirm_is_idempotent_for_already_confirmed_application(self):
        app = AdmissionApplication.objects.create(
            student=self.student,
            academic_period=self.period,
            assigned_career=self.career,
            status='confirmed',
        )
        self.client.force_authenticate(user=self.student)

        response = self.client.patch(f'/api/admissions/applications/{app.pk}/confirm/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'confirmed')

    def test_student_cannot_confirm_after_admission_expiry(self):
        app = AdmissionApplication.objects.create(
            student=self.student,
            academic_period=self.period,
            assigned_career=self.career,
            status='admitted',
            admission_expiry_date=timezone.now() - timedelta(days=1),
        )
        self.client.force_authenticate(user=self.student)

        response = self.client.patch(f'/api/admissions/applications/{app.pk}/confirm/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        app.refresh_from_db()
        self.assertEqual(app.status, 'expired')

    def test_publish_ranking_sets_expiry_for_admitted_application(self):
        self.career.total_spots = 1
        self.career.save(update_fields=['total_spots'])
        app = AdmissionApplication.objects.create(
            student=self.student,
            academic_period=self.period,
            status='submitted',
            admission_score=Decimal('11.500'),
        )
        AdmissionPreference.objects.create(
            application=app,
            career=self.career,
            preference_order=1,
        )

        self.client.force_authenticate(user=self.manager)
        draft_response = self.client.post('/api/admissions/applications/generate-ranking/', {
            'academic_period_id': self.period.pk,
            'career_id': self.career.pk,
            'score_source': 'admission_score',
            'publish': False,
        }, format='json')
        self.assertEqual(draft_response.status_code, status.HTTP_200_OK)

        response = self.client.post('/api/admissions/applications/publish-ranking/', {
            'academic_period_id': self.period.pk,
            'career_id': self.career.pk,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        app.refresh_from_db()
        self.assertEqual(app.status, 'admitted')
        self.assertIsNotNone(app.admission_expiry_date)

    def test_student_cannot_access_all_applications(self):
        """Un estudiante no puede ver las solicitudes de otro estudiante."""
        other_student = User.objects.create_user(
            username='student2', email='student2@test.com',
            password='testpass123', role='s', is_active=True,
        )
        AdmissionApplication.objects.create(
            student=other_student, academic_period=self.period,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/admissions/applications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # El estudiante solo ve sus propias solicitudes (ninguna en este caso)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 0)

    def test_generate_ranking_draft_does_not_publish_real_results(self):
        self.career.total_spots = 1
        self.career.save(update_fields=['total_spots'])
        second_student = User.objects.create_user(
            username='student2', email='student2@test.com',
            password='testpass123', role='s', is_active=True,
        )
        first_app = AdmissionApplication.objects.create(
            student=self.student,
            academic_period=self.period,
            status='submitted',
            admission_score=Decimal('12.000'),
        )
        second_app = AdmissionApplication.objects.create(
            student=second_student,
            academic_period=self.period,
            status='submitted',
            admission_score=Decimal('10.000'),
        )
        first_pref = AdmissionPreference.objects.create(
            application=first_app,
            career=self.career,
            preference_order=1,
        )
        second_pref = AdmissionPreference.objects.create(
            application=second_app,
            career=self.career,
            preference_order=1,
        )

        self.client.force_authenticate(user=self.manager)
        draft_response = self.client.post('/api/admissions/applications/generate-ranking/', {
            'academic_period_id': self.period.pk,
            'career_id': self.career.pk,
            'score_source': 'admission_score',
            'publish': False,
        }, format='json')

        self.assertEqual(draft_response.status_code, status.HTTP_200_OK)
        self.assertFalse(draft_response.data['published'])

        first_app.refresh_from_db()
        second_app.refresh_from_db()
        first_pref.refresh_from_db()
        second_pref.refresh_from_db()

        self.assertEqual(first_app.status, 'submitted')
        self.assertEqual(second_app.status, 'submitted')
        self.assertIsNone(first_app.assigned_career)
        self.assertIsNone(second_app.assigned_career)
        self.assertEqual(first_pref.status, 'pending')
        self.assertEqual(second_pref.status, 'pending')
        self.assertIsNone(first_pref.published_at)
        self.assertIsNone(second_pref.published_at)
        self.assertIsNone(first_pref.rank_position)
        self.assertIsNone(second_pref.rank_position)
        self.assertEqual(first_pref.draft_result_status, 'admitted')
        self.assertEqual(second_pref.draft_result_status, 'waitlisted')

        publish_response = self.client.post('/api/admissions/applications/publish-ranking/', {
            'academic_period_id': self.period.pk,
            'career_id': self.career.pk,
        }, format='json')

        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)
        self.assertEqual(publish_response.data['published'], 2)

        first_app.refresh_from_db()
        second_app.refresh_from_db()
        first_pref.refresh_from_db()
        second_pref.refresh_from_db()

        self.assertEqual(first_app.status, 'admitted')
        self.assertEqual(second_app.status, 'waitlisted')
        self.assertEqual(first_pref.status, 'admitted')
        self.assertEqual(second_pref.status, 'waitlisted')
        self.assertEqual(first_pref.rank_position, 1)
        self.assertEqual(second_pref.waitlist_position, 1)
        self.assertIsNotNone(first_pref.published_at)
        self.assertIsNone(first_pref.draft_result_status)
        self.assertIsNone(second_pref.draft_result_status)

    def test_completed_admission_keeps_seat_when_ranking_is_regenerated(self):
        """Una matrícula completada ocupa plaza; solo una renuncia libera asiento."""
        self.career.total_spots = 1
        self.career.save(update_fields=['total_spots'])
        waitlisted_student = User.objects.create_user(
            username='waitlisted1', email='waitlisted1@test.com',
            password='testpass123', role='s', is_active=True,
        )
        completed_app = AdmissionApplication.objects.create(
            student=self.student,
            academic_period=self.period,
            status='completed',
            assigned_career=self.career,
            assigned_preference_order=1,
            admission_score=Decimal('12.000'),
        )
        waitlisted_app = AdmissionApplication.objects.create(
            student=waitlisted_student,
            academic_period=self.period,
            status='waitlisted',
            admission_score=Decimal('14.000'),
        )
        completed_pref = AdmissionPreference.objects.create(
            application=completed_app,
            career=self.career,
            preference_order=1,
            status='admitted',
            is_assigned=True,
            ranking_score=Decimal('12.000'),
            rank_position=1,
        )
        waitlisted_pref = AdmissionPreference.objects.create(
            application=waitlisted_app,
            career=self.career,
            preference_order=1,
            status='waitlisted',
            ranking_score=Decimal('14.000'),
            rank_position=2,
            waitlist_position=1,
        )

        self.client.force_authenticate(user=self.manager)
        response = self.client.post('/api/admissions/applications/generate-ranking/', {
            'academic_period_id': self.period.pk,
            'career_id': self.career.pk,
            'score_source': 'admission_score',
            'publish': True,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['locked_seats'], 1)
        self.assertEqual(response.data['available_spots'], 0)

        completed_pref.refresh_from_db()
        waitlisted_pref.refresh_from_db()
        waitlisted_app.refresh_from_db()

        self.assertEqual(completed_pref.status, 'admitted')
        self.assertEqual(waitlisted_pref.status, 'waitlisted')
        self.assertEqual(waitlisted_pref.waitlist_position, 1)
        self.assertEqual(waitlisted_app.status, 'waitlisted')

    def test_withdraw_promotes_waitlisted_career_without_touching_other_program_waitlist(self):
        """Una renuncia libera solo la carrera afectada y conserva la espera de otras carreras."""
        self.career.total_spots = 1
        self.career.save(update_fields=['total_spots'])

        other_career = Career.objects.create(
            name='Derecho Test', code='DTEST', duration_years=4, is_active=True,
        )

        promoted_student = User.objects.create_user(
            username='promoted_waitlist', email='promoted@test.com',
            password='testpass123', role='s', is_active=True,
        )
        other_waitlisted_student = User.objects.create_user(
            username='other_waitlist', email='other_waitlist@test.com',
            password='testpass123', role='s', is_active=True,
        )

        admitted_app = AdmissionApplication.objects.create(
            student=self.student,
            academic_period=self.period,
            status='admitted',
            assigned_career=self.career,
            assigned_preference_order=1,
        )
        AdmissionPreference.objects.create(
            application=admitted_app,
            career=self.career,
            preference_order=1,
            status='admitted',
            is_assigned=True,
            waitlist_position=None,
        )
        AdmissionPreference.objects.create(
            application=admitted_app,
            career=other_career,
            preference_order=2,
            status='waitlisted',
            waitlist_position=1,
        )

        promoted_app = AdmissionApplication.objects.create(
            student=promoted_student,
            academic_period=self.period,
            status='waitlisted',
        )
        AdmissionPreference.objects.create(
            application=promoted_app,
            career=self.career,
            preference_order=1,
            status='waitlisted',
            waitlist_position=1,
        )

        other_waitlisted_app = AdmissionApplication.objects.create(
            student=other_waitlisted_student,
            academic_period=self.period,
            status='waitlisted',
        )
        AdmissionPreference.objects.create(
            application=other_waitlisted_app,
            career=other_career,
            preference_order=1,
            status='waitlisted',
            waitlist_position=1,
        )

        self.client.force_authenticate(user=self.student)
        response = self.client.patch(
            f'/api/admissions/applications/{admitted_app.pk}/withdraw/',
            {},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        admitted_app.refresh_from_db()
        promoted_app.refresh_from_db()
        other_waitlisted_app.refresh_from_db()

        self.assertEqual(admitted_app.status, 'withdrawn')
        self.assertEqual(promoted_app.status, 'admitted')
        self.assertEqual(promoted_app.assigned_career, self.career)
        self.assertEqual(other_waitlisted_app.status, 'waitlisted')
