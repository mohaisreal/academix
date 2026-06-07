from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User
from academic.models import Career, AcademicPeriod, Subject


class CareerAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='manager', password='pass12345', role='m')
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
        self.subject = Subject.objects.create(name='Base', code='ADM-1', career=self.career)

    def test_list_subjects_filters_shared_career_relations(self):
        shared_career = Career.objects.create(name='Ingeniería', code='ING')
        self.subject.careers.add(shared_career)
        another = Subject.objects.create(name='Other', code='ADM-2', career=self.career)
        another.careers.add(shared_career)

        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/academic/subjects/', {'career': shared_career.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = response.data['results']
        self.assertEqual({row['id'] for row in payload}, {self.subject.id, another.id})

    def test_list_careers_returns_200_and_serializer_fields(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/academic/careers/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['results'])
        row = response.data['results'][0]
        self.assertIn('subjects_count', row)
        self.assertIn('available_spots', row)
        self.assertIn('convocation_eligibility', row)

    def test_list_subjects_exposes_shared_careers_for_frontend(self):
        shared_career = Career.objects.create(name='Ingeniería', code='ING')
        self.subject.careers.add(shared_career)

        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/academic/subjects/', {'career': shared_career.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data['results'][0]
        self.assertIn('careers', row)
        self.assertGreaterEqual(len(row['careers']), 1)

    def test_career_payload_can_attach_subjects_through_shared_relationship(self):
        other_subject = Subject.objects.create(name='Other', code='ADM-2', career=self.career)

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            f'/api/academic/careers/{self.career.id}/',
            {'subject_ids': [self.subject.id, other_subject.id]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(set(self.career.subjects.values_list('id', flat=True)), {self.subject.id, other_subject.id})

    def test_list_careers_exposes_subject_ids_for_edit_modal(self):
        shared_subject = Subject.objects.create(name='Shared', code='ADM-3', career=self.career)
        other_career = Career.objects.create(name='Ingeniería', code='ING')
        shared_subject.careers.add(self.career, other_career)

        self.client.force_authenticate(user=self.user)

        response = self.client.get('/api/academic/careers/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = next(item for item in response.data['results'] if item['id'] == self.career.id)
        self.assertIn('subjects', row)
        self.assertEqual(set(row['subjects']), {shared_subject.id})
