from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User
from academic.models import Career, AcademicPeriod, Subject, Classroom, Class


def make_period(code='2026', name='2026'):
    return AcademicPeriod.objects.create(
        name=name,
        code=code,
        start_date='2026-01-01',
        end_date='2026-12-31',
        is_active=True,
    )


def make_teacher(username='teacher', role='t'):
    return User.objects.create_user(username=username, password='pass12345', role=role)


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


class ClassGradingPolicyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.teacher = make_teacher('owner')
        self.other_teacher = make_teacher('intruder')
        self.manager = User.objects.create_user(username='manager2', password='pass12345', role='m')
        self.career = Career.objects.create(name='Policy Career', code='POL')
        self.period = make_period(code='2026-POL', name='2026-POL')
        self.subject = Subject.objects.create(name='Policy Subject', code='POL-1', career=self.career)
        self.classroom = Classroom.objects.create(name='Room 1', building='B', capacity=20, type='lecture')
        self.cls = Class.objects.create(
            subject=self.subject,
            teacher=self.teacher,
            period=self.period,
            classroom=self.classroom,
            max_students=20,
            passing_grade=Decimal('5.00'),
        )

    def test_class_defaults_show_final_grade_to_students(self):
        self.assertTrue(self.cls.show_final_grade_to_students)

    def test_teacher_owner_can_update_grading_policy(self):
        self.client.force_authenticate(user=self.teacher)

        response = self.client.patch(
            f'/api/academic/classes/{self.cls.id}/grading-policy/',
            {
                'passing_grade': '6.50',
                'show_final_grade_to_students': False,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.cls.refresh_from_db()
        self.assertEqual(self.cls.passing_grade, Decimal('6.50'))
        self.assertFalse(self.cls.show_final_grade_to_students)
        self.assertEqual(response.data['passing_grade'], '6.50')
        self.assertFalse(response.data['show_final_grade_to_students'])

    def test_non_owner_cannot_update_grading_policy(self):
        self.client.force_authenticate(user=self.other_teacher)

        response = self.client.patch(
            f'/api/academic/classes/{self.cls.id}/grading-policy/',
            {'passing_grade': '7.00', 'show_final_grade_to_students': False},
            format='json',
        )

        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))


class FinalGradeResolverTests(TestCase):
    def setUp(self):
        self.teacher = make_teacher('resolver_teacher')
        self.student = User.objects.create_user(username='resolver_student', password='pass12345', role='s')
        self.career = Career.objects.create(name='Resolver Career', code='RES')
        self.period = make_period(code='2026-RES', name='2026-RES')
        self.subject = Subject.objects.create(name='Resolver Subject', code='RES-1', career=self.career)
        self.classroom = Classroom.objects.create(name='Room 2', building='B', capacity=20, type='lecture')
        self.cls = Class.objects.create(
            subject=self.subject,
            teacher=self.teacher,
            period=self.period,
            classroom=self.classroom,
            max_students=20,
            passing_grade=Decimal('5.00'),
            show_final_grade_to_students=False,
        )

    def test_resolver_reports_visibility_and_pass_status(self):
        from grades.models import Evaluation, Grade
        from grades.services import resolve_class_final_grade

        evaluation = Evaluation.objects.create(
            name='Final',
            cls=self.cls,
            type='exam',
            max_score=Decimal('100'),
            weight=Decimal('100'),
            is_final_grade=True,
        )
        Grade.objects.create(student=self.student, evaluation=evaluation, score=Decimal('7.50'))

        resolved = resolve_class_final_grade(self.student, self.cls)

        self.assertEqual(resolved['final_grade'], Decimal('7.50'))
        self.assertEqual(resolved['source'], 'final_grade')
        self.assertTrue(resolved['passed'])
        self.assertFalse(resolved['final_grade_visible'])

    def test_resolver_prefers_latest_final_grade(self):
        from django.utils import timezone
        from grades.models import Evaluation, Grade
        from grades.services import resolve_class_final_grade

        first = Evaluation.objects.create(
            name='Final 1', cls=self.cls, type='exam', max_score=Decimal('100'), weight=Decimal('100'), is_final_grade=True
        )
        second = Evaluation.objects.create(
            name='Final 2', cls=self.cls, type='exam', max_score=Decimal('100'), weight=Decimal('100'), is_final_grade=True
        )
        g1 = Grade.objects.create(student=self.student, evaluation=first, score=Decimal('6.00'))
        g2 = Grade.objects.create(student=self.student, evaluation=second, score=Decimal('8.00'))
        Grade.objects.filter(pk=g1.pk).update(graded_at=timezone.now() - timedelta(days=1))
        Grade.objects.filter(pk=g2.pk).update(graded_at=timezone.now())

        resolved = resolve_class_final_grade(self.student, self.cls)

        self.assertEqual(resolved['final_grade'], Decimal('8.00'))
