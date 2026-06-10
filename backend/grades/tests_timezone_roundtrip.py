"""
Tests for the `due_date` timezone round-trip: a teacher entering
2026-06-15 11:44 must see the same wall-clock time back, both via the
serialized API representation and via `timezone.localtime`.
"""
from datetime import datetime

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from academic.models import AcademicPeriod, Career, Class, Classroom, Subject
from grades.models import Evaluation
from grades.serializers import EvaluationSerializer


class EvaluationDueDateRoundTripTests(TestCase):
    def setUp(self):
        self.career = Career.objects.create(name='TZ Career', code='TZ', duration_years=4)
        self.period = AcademicPeriod.objects.create(
            name='2026-TZ', code='2026TZ',
            start_date='2026-01-01', end_date='2026-06-30', is_active=True,
        )
        self.subject = Subject.objects.create(name='TZ Subject', code='TZ-SUB', career=self.career, credits=6)
        self.classroom = Classroom.objects.create(name='Aula TZ', building='A', capacity=30, type='lecture')
        self.cls = Class.objects.create(
            subject=self.subject, period=self.period,
            classroom=self.classroom, max_students=30,
        )

    def test_due_date_round_trips_to_the_same_local_wall_clock(self):
        local_dt = timezone.make_aware(datetime(2026, 6, 15, 11, 44), timezone.get_current_timezone())
        evaluation = Evaluation.objects.create(
            name='TZ Eval', cls=self.cls, type='exam', due_date=local_dt,
        )

        # localtime() representation must read 11:44 in the institution's timezone.
        local_repr = timezone.localtime(evaluation.due_date)
        self.assertEqual(local_repr.strftime('%H:%M'), '11:44')

        # The serialized API representation must also carry 11:44 as the local
        # wall-clock component (regardless of the offset suffix DRF appends).
        request = APIRequestFactory().get('/')
        serialized = EvaluationSerializer(evaluation, context={'request': request}).data
        serialized_due_date = serialized['due_date']
        self.assertIsNotNone(serialized_due_date)

        parsed = datetime.fromisoformat(serialized_due_date)
        self.assertEqual(parsed.strftime('%H:%M'), '11:44')
