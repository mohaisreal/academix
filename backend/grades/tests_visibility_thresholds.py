"""
Tests for evaluation visibility (`is_hidden`) and per-evaluation thresholds
(`min_score`), and their effect on the four student-facing read paths:
MyGradesView, MyFileView, MySubjectsView.current_grade and
calculate_student_progress.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from academic.models import AcademicPeriod, Career, Class, Classroom, Subject
from enrollment.models import ClassEnrollment
from enrollment.services import calculate_student_progress
from grades.models import Evaluation, Grade
from users.models import User


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------

def make_student(username='vis_student', email='vis_student@test.com'):
    user = User.objects.create_user(username=username, email=email, password='pass12345')
    user.role = 's'
    user.save()
    return user


def make_teacher(username='vis_teacher', email='vis_teacher@test.com'):
    user = User.objects.create_user(username=username, email=email, password='pass12345')
    user.role = 't'
    user.save()
    return user


def make_career(name='Visibility Career', code='VIS'):
    return Career.objects.create(name=name, code=code, duration_years=4)


def make_period(name='2026-VIS', code='2026VIS'):
    return AcademicPeriod.objects.create(
        name=name, code=code,
        start_date='2026-01-01', end_date='2026-06-30',
        is_active=True,
    )


def make_subject(career, name='Visibility Subject', code='VIS-SUB', credits=6):
    return Subject.objects.create(name=name, code=code, career=career, credits=credits)


def make_class(subject, period, teacher=None, passing_grade=Decimal('5.00')):
    classroom = Classroom.objects.create(name='Aula VIS', building='A', capacity=30, type='lecture')
    return Class.objects.create(
        subject=subject, period=period, teacher=teacher,
        classroom=classroom, max_students=30,
        passing_grade=passing_grade,
    )


def make_evaluation(cls, name='Eval', max_score=Decimal('100'), weight=Decimal('100'), is_hidden=False, min_score=None, **extra):
    return Evaluation.objects.create(
        name=name, cls=cls, type='exam',
        max_score=max_score, weight=weight,
        is_hidden=is_hidden, min_score=min_score,
        **extra,
    )


def make_grade(student, evaluation, score):
    return Grade.objects.create(student=student, evaluation=evaluation, score=Decimal(str(score)))


def make_class_enrollment(student, cls, status='enrolled'):
    return ClassEnrollment.objects.create(student=student, cls=cls, status=status)


# ---------------------------------------------------------------------------
# Phase 1: model fields
# ---------------------------------------------------------------------------

class EvaluationModelFieldsTests(TestCase):
    def setUp(self):
        self.career = make_career()
        self.period = make_period()
        self.subject = make_subject(self.career)
        self.cls = make_class(self.subject, self.period)

    def test_is_hidden_defaults_to_false(self):
        ev = make_evaluation(self.cls)
        self.assertFalse(ev.is_hidden)

    def test_min_score_defaults_to_none(self):
        ev = make_evaluation(self.cls)
        self.assertIsNone(ev.min_score)

    def test_visible_manager_excludes_hidden_evaluations(self):
        visible_ev = make_evaluation(self.cls, name='Visible', is_hidden=False)
        hidden_ev = make_evaluation(self.cls, name='Hidden', is_hidden=True)

        visible_ids = set(Evaluation.objects.visible().values_list('id', flat=True))

        self.assertIn(visible_ev.id, visible_ids)
        self.assertNotIn(hidden_ev.id, visible_ids)


# ---------------------------------------------------------------------------
# Phase 2.1-2.2: MyGradesView visibility
# ---------------------------------------------------------------------------

class MyGradesViewVisibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = make_student()
        self.teacher = make_teacher()
        self.career = make_career()
        self.period = make_period()
        self.subject = make_subject(self.career)
        self.cls = make_class(self.subject, self.period, teacher=self.teacher)
        make_class_enrollment(self.student, self.cls)

        self.eval_a = make_evaluation(self.cls, name='A', due_date=timezone.now())
        self.eval_b = make_evaluation(self.cls, name='B', due_date=timezone.now())
        self.eval_c = make_evaluation(self.cls, name='C', due_date=timezone.now())

        make_grade(self.student, self.eval_a, score=80)
        make_grade(self.student, self.eval_b, score=60)
        make_grade(self.student, self.eval_c, score=90)

    def test_all_evaluations_visible_by_default(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.get('/api/grades/my-grades/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        evals = response.data[0]['evaluations']
        self.assertEqual(len(evals), 3)
        self.assertEqual(response.data[0]['average'], 7.67)
        self.assertIsNone(response.data[0]['evaluations'][0]['evaluation_passed'])

    def test_min_score_marks_only_that_evaluation_as_passed_or_failed(self):
        self.eval_a.min_score = Decimal('70')
        self.eval_a.save(update_fields=['min_score'])

        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/grades/my-grades/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        evals = {e['name']: e for e in response.data[0]['evaluations']}
        self.assertTrue(evals['A']['evaluation_passed'])
        self.assertIsNone(evals['B']['evaluation_passed'])

    def test_hiding_an_evaluation_excludes_it_and_recomputes_average(self):
        self.eval_b.is_hidden = True
        self.eval_b.save(update_fields=['is_hidden'])

        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/grades/my-grades/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        evals = response.data[0]['evaluations']
        eval_names = {e['name'] for e in evals}
        self.assertNotIn('B', eval_names)
        self.assertEqual(len(evals), 2)
        self.assertEqual(response.data[0]['average'], 8.5)

    def test_unhiding_an_evaluation_restores_visibility_and_average(self):
        # Hide B first.
        self.eval_b.is_hidden = True
        self.eval_b.save(update_fields=['is_hidden'])

        self.client.force_authenticate(user=self.student)
        hidden_response = self.client.get('/api/grades/my-grades/')
        self.assertEqual(hidden_response.status_code, status.HTTP_200_OK)
        hidden_names = {e['name'] for e in hidden_response.data[0]['evaluations']}
        self.assertNotIn('B', hidden_names)
        self.assertEqual(hidden_response.data[0]['average'], 8.5)

        # Unhide B (Phase 3 will expose this via PATCH; PR1 verifies the
        # visibility predicate itself reacts correctly to is_hidden=False).
        self.eval_b.is_hidden = False
        self.eval_b.save(update_fields=['is_hidden'])

        restored_response = self.client.get('/api/grades/my-grades/')
        self.assertEqual(restored_response.status_code, status.HTTP_200_OK)
        restored_names = {e['name'] for e in restored_response.data[0]['evaluations']}
        self.assertIn('B', restored_names)
        self.assertEqual(len(restored_response.data[0]['evaluations']), 3)
        self.assertEqual(restored_response.data[0]['average'], 7.67)


# ---------------------------------------------------------------------------
# Phase 2.3-2.4: MyFileView visibility
# ---------------------------------------------------------------------------

class MyFileViewVisibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = make_student(username='file_student', email='file_student@test.com')
        self.teacher = make_teacher(username='file_teacher', email='file_teacher@test.com')
        self.career = make_career(name='File Career', code='FILE')
        self.period = make_period(name='2026-FILE', code='2026FILE')
        self.subject = make_subject(self.career, name='File Subject', code='FILE-SUB')
        self.cls = make_class(self.subject, self.period, teacher=self.teacher)
        make_class_enrollment(self.student, self.cls)

        self.eval_a = make_evaluation(self.cls, name='File A', max_score=Decimal('100'))
        self.eval_b = make_evaluation(self.cls, name='File B', max_score=Decimal('100'))

        make_grade(self.student, self.eval_a, score=80)
        make_grade(self.student, self.eval_b, score=60)

        from enrollment.models import CareerEnrollment
        CareerEnrollment.objects.create(student=self.student, career=self.career, period=self.period, status='active')

    def test_my_file_includes_all_grades_by_default(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.get('/api/grades/my-file/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['overall_gpa'], 7.0)
        self.assertEqual(response.data['periods'][0]['subjects'][0]['final_grade'], 7.0)

    def test_hiding_an_evaluation_recomputes_final_grade_and_overall_gpa(self):
        self.eval_b.is_hidden = True
        self.eval_b.save(update_fields=['is_hidden'])

        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/grades/my-file/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['overall_gpa'], 8.0)
        self.assertEqual(response.data['periods'][0]['subjects'][0]['final_grade'], 8.0)


# ---------------------------------------------------------------------------
# Phase 2.5-2.6: MySubjectsView.current_grade visibility
# ---------------------------------------------------------------------------

class MySubjectsCurrentGradeVisibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = make_student(username='subj_student', email='subj_student@test.com')
        self.teacher = make_teacher(username='subj_teacher', email='subj_teacher@test.com')
        self.career = make_career(name='Subjects Career', code='SUBJ')
        self.period = make_period(name='2026-SUBJ', code='2026SUBJ')
        self.subject = make_subject(self.career, name='Subjects Subject', code='SUBJ-SUB')
        self.cls = make_class(self.subject, self.period, teacher=self.teacher)
        make_class_enrollment(self.student, self.cls)

        self.eval_a = make_evaluation(self.cls, name='Subj A', max_score=Decimal('100'))
        self.eval_b = make_evaluation(self.cls, name='Subj B', max_score=Decimal('100'))

        make_grade(self.student, self.eval_a, score=80)
        make_grade(self.student, self.eval_b, score=60)

    def test_current_grade_reflects_all_visible_evaluations(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.get('/api/enrollment/my-subjects/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['current_grade'], 7.0)

    def test_hiding_an_evaluation_recomputes_current_grade(self):
        self.eval_b.is_hidden = True
        self.eval_b.save(update_fields=['is_hidden'])

        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/enrollment/my-subjects/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['results'][0]['current_grade'], 8.0)


# ---------------------------------------------------------------------------
# Phase 2.7-2.8: calculate_student_progress visibility
# ---------------------------------------------------------------------------

class CalculateStudentProgressVisibilityTests(TestCase):
    def setUp(self):
        self.student = make_student(username='progress_student', email='progress_student@test.com')
        self.career = make_career(name='Progress Career', code='PROG')
        self.period = make_period(name='2026-PROG', code='2026PROG')
        self.subject = make_subject(self.career, name='Progress Subject', code='PROG-SUB', credits=6)
        self.cls = make_class(self.subject, self.period, passing_grade=Decimal('5.00'))
        make_class_enrollment(self.student, self.cls)

        # Two evaluations weighted 50/50; eval_a passes (8/10), eval_b fails badly (2/10).
        # Combined weighted average = (8*50 + 2*50) / 100 = 5.0 -> exactly meets passing_grade.
        self.eval_a = make_evaluation(self.cls, name='Progress A', max_score=Decimal('10'), weight=Decimal('50'))
        self.eval_b = make_evaluation(self.cls, name='Progress B', max_score=Decimal('10'), weight=Decimal('50'))

        make_grade(self.student, self.eval_a, score=8)
        make_grade(self.student, self.eval_b, score=2)

    def test_progress_uses_both_evaluations_by_default(self):
        result = calculate_student_progress(self.student, self.career)

        # (8*50 + 2*50) / 100 = 5.0 == passing_grade(5.00) -> passed
        self.assertEqual(result['ects_completed'], 6)
        self.assertAlmostEqual(result['percentage'], 2.5)  # 6/240 * 100

    def test_hiding_failing_evaluation_recomputes_progress_using_only_visible(self):
        self.eval_b.is_hidden = True
        self.eval_b.save(update_fields=['is_hidden'])

        result = calculate_student_progress(self.student, self.career)

        # Only eval_a remains: weighted average = 8.0 >= passing_grade(5.00) -> passed
        self.assertEqual(result['ects_completed'], 6)
        self.assertAlmostEqual(result['percentage'], 2.5)

    def test_hiding_passing_evaluation_can_drop_progress_to_zero(self):
        # Hide the evaluation that was keeping the average above passing_grade.
        self.eval_a.is_hidden = True
        self.eval_a.save(update_fields=['is_hidden'])

        result = calculate_student_progress(self.student, self.career)

        # Only eval_b remains: weighted average = 2.0 < passing_grade(5.00) -> not passed
        self.assertEqual(result['ects_completed'], 0)
        self.assertEqual(result['percentage'], 0.0)

    def test_class_passing_grade_controls_progress_not_hardcoded_50(self):
        self.cls.passing_grade = Decimal('7.00')
        self.cls.save(update_fields=['passing_grade'])

        result = calculate_student_progress(self.student, self.career)

        self.assertEqual(result['ects_completed'], 0)
        self.assertEqual(result['percentage'], 0.0)


# ---------------------------------------------------------------------------
# Phase 2.9-2.10: EvaluationListCreateView owner vs student visibility
# ---------------------------------------------------------------------------

class EvaluationListCreateOwnerVisibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = make_student(username='owner_student', email='owner_student@test.com')
        self.owner_teacher = make_teacher(username='owner_teacher', email='owner_teacher@test.com')
        self.career = make_career(name='Owner Career', code='OWN')
        self.period = make_period(name='2026-OWN', code='2026OWN')
        self.subject = make_subject(self.career, name='Owner Subject', code='OWN-SUB')
        self.cls = make_class(self.subject, self.period, teacher=self.owner_teacher)
        make_class_enrollment(self.student, self.cls)

        self.visible_eval = make_evaluation(self.cls, name='Owner Visible', is_hidden=False)
        self.hidden_eval = make_evaluation(self.cls, name='Owner Hidden', is_hidden=True)

    def test_owning_teacher_sees_hidden_evaluation(self):
        self.client.force_authenticate(user=self.owner_teacher)

        response = self.client.get(f'/api/grades/evaluations/?class={self.cls.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {ev['name'] for ev in response.data['results']}
        self.assertIn('Owner Visible', names)
        self.assertIn('Owner Hidden', names)

    def test_student_does_not_see_hidden_evaluation_via_evaluations_endpoint(self):
        self.client.force_authenticate(user=self.student)

        response = self.client.get(f'/api/grades/evaluations/?class={self.cls.id}')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = {ev['name'] for ev in response.data['results']}
        self.assertIn('Owner Visible', names)
        self.assertNotIn('Owner Hidden', names)
