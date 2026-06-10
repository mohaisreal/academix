from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from academic.models import AcademicPeriod, Career, Class, Subject
from enrollment.models import ClassEnrollment
from grades.models import Evaluation, EvaluationSubmission
from grades.services import get_or_create_final_grade_evaluation
from users.models import User


class EvaluationSubmissionApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = User.objects.create_user(username='student_eval', password='pass12345', role='s')
        self.other_student = User.objects.create_user(username='other_student_eval', password='pass12345', role='s')
        self.teacher = User.objects.create_user(username='teacher_eval', password='pass12345', role='t')
        self.career = Career.objects.create(name='Engineering', code='ENG-EVAL')
        self.period = AcademicPeriod.objects.create(
            name='2026-A', code='2026EVAL', start_date='2026-01-01', end_date='2026-06-30', is_active=True
        )
        self.subject = Subject.objects.create(name='Databases', code='DB-EVAL', career=self.career)
        self.cls = Class.objects.create(subject=self.subject, period=self.period, teacher=self.teacher)
        ClassEnrollment.objects.create(student=self.student, cls=self.cls, status='enrolled')
        self.evaluation = Evaluation.objects.create(
            name='Project 1',
            cls=self.cls,
            type='assignment',
            due_date=timezone.now() + timezone.timedelta(days=2),
            allows_file_submission=True,
        )

    def _upload(self, user=None, evaluation=None):
        self.client.force_authenticate(user=user or self.student)
        upload = SimpleUploadedFile('submission.txt', b'hello world', content_type='text/plain')
        return self.client.post(
            f'/api/grades/evaluations/{(evaluation or self.evaluation).id}/submissions/',
            {'file': upload},
            format='multipart',
        )

    def test_evaluation_serializer_exposes_datetime_and_file_submission_flag(self):
        self.assertIsNotNone(self.evaluation.due_date)
        self.assertTrue(self.evaluation.allows_file_submission)

    def test_student_can_upload_submission(self):
        response = self._upload()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['evaluation'], self.evaluation.id)
        self.assertEqual(EvaluationSubmission.objects.count(), 1)
        self.assertTrue(EvaluationSubmission.objects.filter(student=self.student, evaluation=self.evaluation).exists())

    def test_pending_state_is_authoritative_before_deadline(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.get('/api/grades/my-grades/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        evaluation_data = response.data[0]['evaluations'][0]
        self.assertEqual(evaluation_data['submission_status'], 'pending')
        self.assertEqual(evaluation_data['submission_label'], 'Pendiente')
        self.assertTrue(evaluation_data['upload_allowed'])

    def test_late_state_is_authoritative_after_deadline(self):
        self.evaluation.due_date = timezone.now() - timezone.timedelta(days=1)
        self.evaluation.save(update_fields=['due_date'])
        self.client.force_authenticate(user=self.student)

        response = self.client.get('/api/grades/my-grades/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        evaluation_data = response.data[0]['evaluations'][0]
        self.assertEqual(evaluation_data['submission_status'], 'late')
        self.assertEqual(evaluation_data['submission_label'], 'Fuera de plazo')
        self.assertFalse(evaluation_data['upload_allowed'])

    def test_upload_before_deadline_sets_submitted_state(self):
        response = self._upload()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(user=self.student)
        grades_response = self.client.get('/api/grades/my-grades/')

        evaluation_data = grades_response.data[0]['evaluations'][0]
        self.assertEqual(evaluation_data['submission_status'], 'submitted')
        self.assertEqual(evaluation_data['submission_label'], 'Entregado')
        self.assertIsNotNone(evaluation_data['submitted_at'])
        self.assertIsNotNone(evaluation_data['submission_file_url'])
        self.assertTrue(evaluation_data['submission_file_url'].startswith('http://testserver'))
        self.assertTrue(evaluation_data['submission_file_name'].endswith('.txt'))

    def test_duplicate_submission_is_rejected(self):
        EvaluationSubmission.objects.create(
            student=self.student,
            evaluation=self.evaluation,
            file=SimpleUploadedFile('existing.txt', b'existing', content_type='text/plain'),
        )
        self.client.force_authenticate(user=self.student)

        upload = SimpleUploadedFile('submission.txt', b'hello world', content_type='text/plain')
        response = self.client.post(
            f'/api/grades/evaluations/{self.evaluation.id}/submissions/',
            {'file': upload},
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Submission already exists')

    def test_upload_after_deadline_is_rejected(self):
        self.evaluation.due_date = timezone.now() - timezone.timedelta(days=1)
        self.evaluation.save(update_fields=['due_date'])

        response = self._upload()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'Submission deadline has passed')

    def test_submission_requires_opt_in_flag(self):
        self.evaluation.allows_file_submission = False
        self.evaluation.save(update_fields=['allows_file_submission'])
        response = self._upload()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['error'], 'File submissions are not allowed for this evaluation')

    def test_teacher_marking_payload_exposes_submission_metadata(self):
        submission = EvaluationSubmission.objects.create(
            student=self.student,
            evaluation=self.evaluation,
            file=SimpleUploadedFile('existing.txt', b'existing', content_type='text/plain'),
        )
        self.client.force_authenticate(user=self.teacher)

        response = self.client.get(f'/api/grades/marking/{self.evaluation.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student_row = response.data['students'][0]
        self.assertEqual(student_row['submission_status'], 'submitted')
        self.assertEqual(student_row['submitted_at'], submission.submitted_at.isoformat())
        self.assertIsNotNone(student_row['submission_file_url'])
        self.assertTrue(student_row['submission_file_url'].startswith('http://testserver'))
        self.assertTrue(student_row['submission_file_name'].endswith('.txt'))

    def test_non_owner_cannot_view_marking_submission_details(self):
        other_teacher = User.objects.create_user(username='other_teacher', password='pass12345', role='t')
        self.client.force_authenticate(user=other_teacher)

        response = self.client.get(f'/api/grades/marking/{self.evaluation.id}/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_full_grading_flow_exposes_uploaded_submission_and_marked_grade(self):
        submit_response = self._upload()

        self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(user=self.teacher)
        mark_response = self.client.post(
            f'/api/grades/marking/{self.evaluation.id}/',
            {'student_id': self.student.id, 'score': 88, 'feedback': 'Great work'},
            format='json',
        )

        self.assertEqual(mark_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(mark_response.data['student_name'], self.student.username)
        self.assertEqual(mark_response.data['percentage'], 88.0)

        self.client.force_authenticate(user=self.student)
        grades_response = self.client.get('/api/grades/my-grades/')

        self.assertEqual(grades_response.status_code, status.HTTP_200_OK)
        self.assertEqual(grades_response.data[0]['evaluations'][0]['score'], 88.0)
        self.assertEqual(grades_response.data[0]['evaluations'][0]['feedback'], 'Great work')
        self.assertEqual(grades_response.data[0]['evaluations'][0]['percentage'], 88.0)
        self.assertEqual(grades_response.data[0]['evaluations'][0]['graded_at'] is not None, True)

    def test_teacher_files_endpoint_groups_students_by_class_for_final_grade_editing(self):
        other_subject = Subject.objects.create(name='Networks', code='NET-EVAL', career=self.career)
        other_cls = Class.objects.create(subject=other_subject, period=self.period, teacher=self.teacher)
        ClassEnrollment.objects.create(student=self.student, cls=other_cls, status='enrolled')
        ClassEnrollment.objects.create(student=self.other_student, cls=other_cls, status='enrolled')
        get_or_create_final_grade_evaluation(self.cls)
        get_or_create_final_grade_evaluation(other_cls)
        self.client.force_authenticate(user=self.teacher)

        response = self.client.get('/api/grades/files/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student_row = next(row for row in response.data if row['id'] == self.student.id)
        self.assertEqual(student_row['student_name'], 'student_eval')
        self.assertEqual(len(student_row['classes']), 2)
        self.assertEqual({row['id'] for row in student_row['classes']}, {self.cls.id, other_cls.id})
