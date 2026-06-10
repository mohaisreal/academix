"""
Tests for the `EvaluationDetailView` (PATCH/PUT/DELETE) endpoint:

- Only the owning teacher (`cls.teacher == request.user`) can edit, hide, or
  delete an evaluation.
- Non-owning teachers get `404` (mirrors `MarkingView`'s
  `pk=eval_id, cls__teacher=request.user` not-found pattern).
- Students cannot write to this endpoint.
- Unauthenticated requests are rejected.
- Deleting an evaluation cascades to its `Grade` and `EvaluationSubmission`
  records.
- Hiding an evaluation via PATCH (`is_hidden=True`) makes it disappear from
  the student's `my-grades` view (closes the loop deferred from task 2.11).
"""
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from academic.models import AcademicPeriod, Career, Class, Classroom, Subject
from enrollment.models import ClassEnrollment
from grades.models import Evaluation, EvaluationSubmission, Grade
from users.models import User


def make_career(name='CRUD Career', code='CRUD'):
    return Career.objects.create(name=name, code=code, duration_years=4)


def make_period(name='2026-CRUD', code='2026CRUD'):
    return AcademicPeriod.objects.create(
        name=name, code=code,
        start_date='2026-01-01', end_date='2026-06-30',
        is_active=True,
    )


def make_subject(career, name='CRUD Subject', code='CRUD-SUB', credits=6):
    return Subject.objects.create(name=name, code=code, career=career, credits=credits)


def make_class(subject, period, teacher=None):
    classroom = Classroom.objects.create(name='Aula CRUD', building='A', capacity=30, type='lecture')
    return Class.objects.create(
        subject=subject, period=period, teacher=teacher,
        classroom=classroom, max_students=30,
        passing_grade=Decimal('5.00'),
    )


def make_evaluation(cls, name='Eval', max_score=Decimal('100'), **extra):
    return Evaluation.objects.create(
        name=name, cls=cls, type='exam',
        max_score=max_score, due_date=timezone.now(),
        **extra,
    )


class EvaluationDetailViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.career = make_career()
        self.period = make_period()
        self.subject = make_subject(self.career)

        self.owner_teacher = User.objects.create_user(
            username='crud_owner_teacher', password='pass12345', role='t',
        )
        self.other_teacher = User.objects.create_user(
            username='crud_other_teacher', password='pass12345', role='t',
        )
        self.student = User.objects.create_user(
            username='crud_student', password='pass12345', role='s',
        )

        self.cls = make_class(self.subject, self.period, teacher=self.owner_teacher)
        ClassEnrollment.objects.create(student=self.student, cls=self.cls, status='enrolled')

        self.evaluation = make_evaluation(self.cls, name='Original Name', max_score=Decimal('100'))

    def detail_url(self, evaluation_id=None):
        return f'/api/grades/evaluations/{evaluation_id or self.evaluation.id}/'

    # -- 3.8: owning teacher can PATCH ------------------------------------

    def test_owning_teacher_can_patch(self):
        self.client.force_authenticate(user=self.owner_teacher)

        response = self.client.patch(
            self.detail_url(),
            {
                'name': 'Updated Name',
                'max_score': 90,
                'is_hidden': True,
                'min_score': 50,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Name')
        self.assertEqual(response.data['max_score'], '90.00')
        self.assertEqual(response.data['is_hidden'], True)
        self.assertEqual(response.data['min_score'], '50.00')

        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.name, 'Updated Name')
        self.assertTrue(self.evaluation.is_hidden)
        self.assertEqual(self.evaluation.min_score, Decimal('50'))

    # -- 3.10: non-owning teacher cannot PATCH (404) -----------------------

    def test_non_owning_teacher_cannot_patch_returns_404(self):
        self.client.force_authenticate(user=self.other_teacher)

        response = self.client.patch(
            self.detail_url(),
            {'name': 'Hijacked Name'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.name, 'Original Name')

    # -- 3.12: student cannot PATCH (403/404) -------------------------------

    def test_student_cannot_patch_returns_403_or_404(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.patch(
            self.detail_url(),
            {'name': 'Student Edit'},
            format='json',
        )

        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )

        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.name, 'Original Name')

    # -- unauthenticated requests are rejected ------------------------------

    def test_unauthenticated_cannot_patch(self):
        response = self.client.patch(
            self.detail_url(),
            {'name': 'Anon Edit'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_cannot_delete(self):
        response = self.client.delete(self.detail_url())

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # -- 3.14: owning teacher can delete; cascades grades + submissions -----

    def test_owning_teacher_can_delete_cascades_grades_and_submissions(self):
        Grade.objects.create(student=self.student, evaluation=self.evaluation, score=Decimal('80'))
        EvaluationSubmission.objects.create(
            student=self.student,
            evaluation=self.evaluation,
            file=SimpleUploadedFile('submission.txt', b'content', content_type='text/plain'),
        )

        self.client.force_authenticate(user=self.owner_teacher)

        response = self.client.delete(self.detail_url())

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Evaluation.objects.filter(pk=self.evaluation.id).exists())
        self.assertFalse(Grade.objects.filter(evaluation_id=self.evaluation.id).exists())
        self.assertFalse(EvaluationSubmission.objects.filter(evaluation_id=self.evaluation.id).exists())

    def test_non_owning_teacher_cannot_delete_returns_404(self):
        self.client.force_authenticate(user=self.other_teacher)

        response = self.client.delete(self.detail_url())

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Evaluation.objects.filter(pk=self.evaluation.id).exists())

    # -- min_score > max_score is rejected via PATCH (400) -------------------

    def test_patch_with_min_score_greater_than_max_score_returns_400(self):
        self.client.force_authenticate(user=self.owner_teacher)

        response = self.client.patch(
            self.detail_url(),
            {'max_score': 100, 'min_score': 120},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('min_score', response.data)

        self.evaluation.refresh_from_db()
        self.assertIsNone(self.evaluation.min_score)

    # -- lowering max_score below a recorded grade returns a warning --------

    def test_patch_lowering_max_score_below_recorded_grade_returns_warning(self):
        Grade.objects.create(student=self.student, evaluation=self.evaluation, score=Decimal('95'))
        self.client.force_authenticate(user=self.owner_teacher)

        response = self.client.patch(
            self.detail_url(),
            {'max_score': 80},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(len(response.data['warnings']) > 0)

        self.evaluation.refresh_from_db()
        self.assertEqual(self.evaluation.max_score, Decimal('80'))


# ---------------------------------------------------------------------------
# 3.16: deferred from task 2.11 — unhide via PATCH restores visibility
# ---------------------------------------------------------------------------

class EvaluationUnhideViaPatchTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.career = make_career(name='Unhide Career', code='UNH')
        self.period = make_period(name='2026-UNH', code='2026UNH')
        self.subject = make_subject(self.career, name='Unhide Subject', code='UNH-SUB')

        self.teacher = User.objects.create_user(
            username='unhide_teacher', password='pass12345', role='t',
        )
        self.student = User.objects.create_user(
            username='unhide_student', password='pass12345', role='s',
        )

        self.cls = make_class(self.subject, self.period, teacher=self.teacher)
        ClassEnrollment.objects.create(student=self.student, cls=self.cls, status='enrolled')

        self.eval_a = make_evaluation(self.cls, name='Unhide A')
        self.eval_b = make_evaluation(self.cls, name='Unhide B')
        self.eval_c = make_evaluation(self.cls, name='Unhide C')

        Grade.objects.create(student=self.student, evaluation=self.eval_a, score=Decimal('80'))
        Grade.objects.create(student=self.student, evaluation=self.eval_b, score=Decimal('60'))
        Grade.objects.create(student=self.student, evaluation=self.eval_c, score=Decimal('90'))

    def test_hide_then_unhide_via_patch_restores_visibility_and_average(self):
        # Hide B via PATCH.
        self.client.force_authenticate(user=self.teacher)
        hide_response = self.client.patch(
            f'/api/grades/evaluations/{self.eval_b.id}/',
            {'is_hidden': True},
            format='json',
        )
        self.assertEqual(hide_response.status_code, status.HTTP_200_OK)
        self.assertTrue(hide_response.data['is_hidden'])

        self.client.force_authenticate(user=self.student)
        hidden_response = self.client.get('/api/grades/my-grades/')
        self.assertEqual(hidden_response.status_code, status.HTTP_200_OK)
        hidden_names = {e['name'] for e in hidden_response.data[0]['evaluations']}
        self.assertNotIn('Unhide B', hidden_names)
        self.assertEqual(hidden_response.data[0]['average'], 85.0)

        # Unhide B via PATCH.
        self.client.force_authenticate(user=self.teacher)
        unhide_response = self.client.patch(
            f'/api/grades/evaluations/{self.eval_b.id}/',
            {'is_hidden': False},
            format='json',
        )
        self.assertEqual(unhide_response.status_code, status.HTTP_200_OK)
        self.assertFalse(unhide_response.data['is_hidden'])

        self.client.force_authenticate(user=self.student)
        restored_response = self.client.get('/api/grades/my-grades/')
        self.assertEqual(restored_response.status_code, status.HTTP_200_OK)
        restored_names = {e['name'] for e in restored_response.data[0]['evaluations']}
        self.assertIn('Unhide B', restored_names)
        self.assertEqual(len(restored_response.data[0]['evaluations']), 3)
        self.assertEqual(restored_response.data[0]['average'], 76.7)
