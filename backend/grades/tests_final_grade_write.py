from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from academic.models import AcademicPeriod, Career, Class, Classroom, Subject
from enrollment.models import ClassEnrollment
from grades.models import Evaluation, Grade
from grades.services import resolve_class_final_grade, get_or_create_final_grade_evaluation
from users.models import User


def make_class(teacher, *, name='Class', code='CLS'):
    career = Career.objects.create(name='Career', code=f'{code}-C', duration_years=4)
    period = AcademicPeriod.objects.create(
        name='2026',
        code=f'{code}-P',
        start_date='2026-01-01',
        end_date='2026-06-30',
        is_active=True,
    )
    subject = Subject.objects.create(name=name, code=code, career=career, credits=6)
    classroom = Classroom.objects.create(name='A1', building='B', capacity=30, type='lecture')
    return Class.objects.create(
        subject=subject,
        period=period,
        teacher=teacher,
        classroom=classroom,
        max_students=30,
        passing_grade=Decimal('5.00'),
    )


class FinalGradeWriteApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.teacher = User.objects.create_user(username='teacher', password='pass12345', role='t')
        self.other_teacher = User.objects.create_user(username='other', password='pass12345', role='t')
        self.student = User.objects.create_user(username='student', password='pass12345', role='s')
        self.other_student = User.objects.create_user(username='otherstudent', password='pass12345', role='s')
        self.cls = make_class(self.teacher)
        ClassEnrollment.objects.create(student=self.student, cls=self.cls, status='enrolled')
        ClassEnrollment.objects.create(student=self.other_student, cls=self.cls, status='enrolled')

    def url(self, class_id=None, student_id=None):
        class_id = class_id or self.cls.id
        student_id = student_id or self.student.id
        return f'/api/grades/classes/{class_id}/students/{student_id}/final-grade/'

    def test_teacher_can_set_final_grade_and_reuse_singleton(self):
        self.client.force_authenticate(user=self.teacher)

        response = self.client.put(self.url(), {'score': '8.5'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['source'], 'final_grade')
        self.assertEqual(response.data['final_grade'], '8.50')
        self.assertEqual(response.data['score'], '8.50')

        self.assertEqual(Evaluation.objects.filter(cls=self.cls, is_final_grade=True).count(), 1)
        grade = Grade.objects.get(student=self.student, evaluation__cls=self.cls, evaluation__is_final_grade=True)
        self.assertEqual(grade.score, Decimal('8.50'))
        self.assertEqual(resolve_class_final_grade(self.student, self.cls)['final_grade'], Decimal('8.50'))

        response2 = self.client.put(self.url(student_id=self.other_student.id), {'score': 6}, format='json')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Evaluation.objects.filter(cls=self.cls, is_final_grade=True).count(), 1)

    def test_teacher_can_edit_existing_final_grade(self):
        self.client.force_authenticate(user=self.teacher)
        self.client.put(self.url(), {'score': 8.5}, format='json')
        first = Grade.objects.get(student=self.student, evaluation__cls=self.cls, evaluation__is_final_grade=True)

        response = self.client.put(self.url(), {'score': 9.0}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        first.refresh_from_db()
        self.assertEqual(first.score, Decimal('9.00'))
        self.assertEqual(resolve_class_final_grade(self.student, self.cls)['final_grade'], Decimal('9.00'))

    def test_teacher_can_clear_final_grade_without_touching_other_students(self):
        self.client.force_authenticate(user=self.teacher)
        self.client.put(self.url(), {'score': 8.5}, format='json')
        self.client.put(self.url(student_id=self.other_student.id), {'score': 6.0}, format='json')
        Grade.objects.create(
            student=self.student,
            evaluation=Evaluation.objects.create(name='Task', cls=self.cls, type='assignment'),
            score=Decimal('6.20'),
        )

        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Grade.objects.filter(student=self.student, evaluation__cls=self.cls, evaluation__is_final_grade=True).exists())
        self.assertTrue(Grade.objects.filter(student=self.other_student, evaluation__cls=self.cls, evaluation__is_final_grade=True).exists())
        self.assertEqual(resolve_class_final_grade(self.student, self.cls)['source'], 'weighted_average')

    def test_teacher_can_clear_legacy_duplicate_final_grade_and_return_fallback(self):
        legacy_primary = Evaluation.objects.create(name='Legacy final A', cls=self.cls, type='exam', is_final_grade=True)
        Evaluation.objects.create(name='Legacy final B', cls=self.cls, type='exam', is_final_grade=True)
        Grade.objects.create(student=self.student, evaluation=legacy_primary, score=Decimal('8.50'))
        Grade.objects.create(
            student=self.student,
            evaluation=Evaluation.objects.create(name='Task', cls=self.cls, type='assignment', weight=Decimal('1')),
            score=Decimal('6.00'),
        )

        self.client.force_authenticate(user=self.teacher)

        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Grade.objects.filter(student=self.student, evaluation__cls=self.cls, evaluation__is_final_grade=True).exists())
        self.assertEqual(response.data['source'], 'weighted_average')
        self.assertEqual(response.data['final_grade'], '0.60')

    def test_out_of_range_score_is_rejected(self):
        self.client.force_authenticate(user=self.teacher)

        response = self.client.put(self.url(), {'score': 12}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Evaluation.objects.filter(cls=self.cls, is_final_grade=True).exists())
        self.assertFalse(Grade.objects.filter(student=self.student).exists())

    def test_non_owner_teacher_gets_404_and_student_gets_403(self):
        self.client.force_authenticate(user=self.other_teacher)
        response = self.client.put(self.url(), {'score': 7}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_authenticate(user=self.student)
        response = self.client.put(self.url(), {'score': 7}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_or_create_final_grade_evaluation_is_duplicate_safe(self):
        Evaluation.objects.create(name='Legacy final A', cls=self.cls, type='exam', is_final_grade=True)
        Evaluation.objects.create(name='Legacy final B', cls=self.cls, type='exam', is_final_grade=True)

        evaluation, created = get_or_create_final_grade_evaluation(self.cls)

        self.assertFalse(created)
        self.assertEqual(evaluation.name, 'Legacy final A')
        self.assertEqual(Evaluation.objects.filter(cls=self.cls, is_final_grade=True).count(), 2)

    def test_delete_uses_canonical_final_grade_when_duplicates_exist(self):
        canonical = Evaluation.objects.create(name='Legacy final A', cls=self.cls, type='exam', is_final_grade=True)
        Evaluation.objects.create(name='Legacy final B', cls=self.cls, type='exam', is_final_grade=True)
        Grade.objects.create(student=self.student, evaluation=canonical, score=Decimal('8.25'))

        self.client.force_authenticate(user=self.teacher)

        response = self.client.delete(self.url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Grade.objects.filter(student=self.student, evaluation=canonical).exists())
