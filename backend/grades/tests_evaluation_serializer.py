"""
Tests for `EvaluationSerializer` validation and warning behavior:

- `min_score <= max_score` is enforced (blocking 400 on violation).
- `min_score` round-trips correctly when valid.
- Lowering `max_score` below an existing recorded `Grade.score` produces a
  non-blocking `warnings` entry in the serialized representation.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework import serializers as drf_serializers

from academic.models import AcademicPeriod, Career, Class, Classroom, Subject
from grades.models import Evaluation, Grade
from grades.serializers import EvaluationSerializer
from users.models import User


def make_career(name='Serializer Career', code='SER'):
    return Career.objects.create(name=name, code=code, duration_years=4)


def make_period(name='2026-SER', code='2026SER'):
    return AcademicPeriod.objects.create(
        name=name, code=code,
        start_date='2026-01-01', end_date='2026-06-30',
        is_active=True,
    )


def make_subject(career, name='Serializer Subject', code='SER-SUB', credits=6):
    return Subject.objects.create(name=name, code=code, career=career, credits=credits)


def make_class(subject, period, teacher=None):
    classroom = Classroom.objects.create(name='Aula SER', building='A', capacity=30, type='lecture')
    return Class.objects.create(
        subject=subject, period=period, teacher=teacher,
        classroom=classroom, max_students=30,
        passing_grade=Decimal('5.00'),
    )


def make_evaluation(cls, name='Eval', max_score=Decimal('100'), min_score=None, **extra):
    return Evaluation.objects.create(
        name=name, cls=cls, type='exam',
        max_score=max_score, min_score=min_score,
        **extra,
    )


class EvaluationSerializerValidationTests(TestCase):
    def setUp(self):
        self.career = make_career()
        self.period = make_period()
        self.subject = make_subject(self.career)
        self.cls = make_class(self.subject, self.period)

    def test_min_score_greater_than_max_score_rejected(self):
        serializer = EvaluationSerializer(data={
            'name': 'Bad threshold',
            'cls': self.cls.id,
            'type': 'exam',
            'max_score': 100,
            'min_score': 120,
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn('min_score', serializer.errors)

    def test_min_score_valid_is_saved_and_serialized(self):
        serializer = EvaluationSerializer(data={
            'name': 'Good threshold',
            'cls': self.cls.id,
            'type': 'exam',
            'max_score': 100,
            'min_score': 60,
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)
        evaluation = serializer.save()

        self.assertEqual(evaluation.min_score, Decimal('60'))
        self.assertEqual(serializer.data['min_score'], '60.00')

    def test_lowering_max_score_below_recorded_grade_returns_warning(self):
        evaluation = make_evaluation(self.cls, name='Lowered', max_score=Decimal('100'))
        student = User.objects.create_user(username='ser_student', password='pass12345', role='s')
        Grade.objects.create(student=student, evaluation=evaluation, score=Decimal('95'))

        serializer = EvaluationSerializer(
            instance=evaluation,
            data={'max_score': 80},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertTrue(len(serializer.data['warnings']) > 0)

    def test_lowering_max_score_with_no_affected_grades_no_warning(self):
        evaluation = make_evaluation(self.cls, name='Lowered No Warning', max_score=Decimal('100'))
        student = User.objects.create_user(username='ser_student2', password='pass12345', role='s')
        Grade.objects.create(student=student, evaluation=evaluation, score=Decimal('70'))

        serializer = EvaluationSerializer(
            instance=evaluation,
            data={'max_score': 80},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()

        self.assertEqual(serializer.data['warnings'], [])
