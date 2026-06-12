from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from academic.models import Career, AcademicPeriod, Class, Subject
from enrollment.models import ClassEnrollment
from users.models import User
from .models import Material


class MaterialDownloadTests(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(username='teacher', password='pass12345', role='t')
        self.other_teacher = User.objects.create_user(username='other', password='pass12345', role='t')
        self.student = User.objects.create_user(username='student', password='pass12345', role='s')
        self.period = AcademicPeriod.objects.create(
            name='2026', code='2026', start_date='2026-01-01', end_date='2026-12-31', is_active=True,
        )
        self.career = Career.objects.create(name='Engineering')
        self.subject = Subject.objects.create(name='Math', code='MATH-1', career=self.career)
        self.cls = Class.objects.create(subject=self.subject, teacher=self.teacher, period=self.period)
        ClassEnrollment.objects.create(student=self.student, cls=self.cls, status='enrolled')

    def _create_material(self, uploaded_by):
        return Material.objects.create(
            title='Lesson Plan',
            description='',
            cls=self.cls,
            uploaded_by=uploaded_by,
            file=SimpleUploadedFile('Lesson Plan.pdf', b'pdf-bytes', content_type='application/pdf'),
            original_filename='Lesson Plan.pdf',
            type='document',
        )

    def test_student_download_gets_attachment_with_original_filename(self):
        material = self._create_material(self.teacher)
        self.client.force_authenticate(user=self.student)

        response = self.client.get(f'/api/material/{material.id}/download/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertIn('Lesson_Plan.pdf', response['Content-Disposition'])
        self.assertEqual(response.getvalue(), b'pdf-bytes')

    def test_serializer_exposes_relative_download_url(self):
        material = self._create_material(self.teacher)
        self.client.force_authenticate(user=self.student)

        response = self.client.get('/api/material/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data[0]
        self.assertEqual(item['download_url'], f'/material/{material.id}/download/')

    def test_own_teacher_can_download_other_teacher_is_hidden(self):
        material = self._create_material(self.teacher)

        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(f'/api/material/{material.id}/download/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(user=self.other_teacher)
        denied = self.client.get(f'/api/material/{material.id}/download/')
        self.assertEqual(denied.status_code, status.HTTP_404_NOT_FOUND)

    def test_missing_file_returns_not_found(self):
        material = self._create_material(self.teacher)
        material.file.delete(save=False)

        self.client.force_authenticate(user=self.student)
        response = self.client.get(f'/api/material/{material.id}/download/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
