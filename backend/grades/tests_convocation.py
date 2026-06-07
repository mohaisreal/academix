from django.test import TestCase

from academic.models import Career, AcademicPeriod, Subject, Class
from grades.models import Evaluation


class EvaluationFinalGradeFieldTests(TestCase):

    def setUp(self):
        self.career = Career.objects.create(name='Ingeniería', code='ING-GRAD')
        self.period = AcademicPeriod.objects.create(
            name='2026-G',
            code='2026G',
            start_date='2026-01-01',
            end_date='2026-06-30',
        )
        self.subject = Subject.objects.create(name='Álgebra', code='ALG-GRAD', career=self.career)
        self.cls = Class.objects.create(subject=self.subject, period=self.period)

    def test_evaluation_defaults_to_non_final_grade(self):
        evaluation = Evaluation.objects.create(name='Examen parcial', cls=self.cls)

        self.assertFalse(evaluation.is_final_grade)

    def test_evaluation_accepts_final_grade_flag(self):
        evaluation = Evaluation.objects.create(
            name='Examen final',
            cls=self.cls,
            is_final_grade=True,
        )

        self.assertTrue(evaluation.is_final_grade)
