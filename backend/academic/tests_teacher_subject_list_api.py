"""
Updated tests for the teacher-subject-selection decisions list endpoint.

Changes from original:
- Removed all TeacherSubjectEligibility imports, fixtures, and test class (model is gone).
- Updated role='d' fixtures to role='m' (management) — 'd' is not a valid role.
- TeacherSubjectDecision now references offerings, not subjects directly.
- Decision value changed from 'selected' → 'pending' (new default).
"""
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from academic.models import (
    AcademicPeriod,
    Career,
    Department,
    Subject,
    SubjectOffering,
    TeacherSubjectDecision,
)
from users.models import User


DECISIONS_URL = '/api/academic/teacher-subject-selection/decisions/'
REVIEW_URL_TEMPLATE = '/api/academic/teacher-subject-selection/decisions/{pk}/review/'


def review_url(pk):
    return REVIEW_URL_TEMPLATE.format(pk=pk)


class TeacherSubjectDecisionListViewTests(TestCase):
    """Tests for GET /api/academic/teacher-subject-selection/decisions/"""

    def setUp(self):
        self.client = APIClient()

        # Active period
        self.period = AcademicPeriod.objects.create(
            name='2026',
            code='2026',
            start_date='2026-01-01',
            end_date='2026-12-31',
            is_active=True,
        )
        # Other period (for filter tests)
        self.other_period = AcademicPeriod.objects.create(
            name='2025',
            code='2025',
            start_date='2025-01-01',
            end_date='2025-12-31',
            is_active=False,
        )

        # Users — no 'd' role; use 'm' for management-like reviewers
        self.teacher = User.objects.create_user(
            username='teacher-list', password='pass12345', role='t'
        )
        self.other_teacher = User.objects.create_user(
            username='teacher-other-list', password='pass12345', role='t'
        )
        self.manager = User.objects.create_user(
            username='manager-list', password='pass12345', role='m'
        )
        self.other_manager = User.objects.create_user(
            username='manager-other-list', password='pass12345', role='m'
        )
        self.student = User.objects.create_user(
            username='student-list', password='pass12345', role='s'
        )

        # Departments
        self.career = Career.objects.create(name='Career List', code='CAR-LIST')
        self.dept_a = Department.objects.create(
            name='Dept A List', code='DPTA-LIST',
        )
        self.dept_b = Department.objects.create(
            name='Dept B List', code='DPTB-LIST',
        )

        # Subjects
        self.subject_a = Subject.objects.create(
            name='Subject A List', code='SUBA-LIST', career=self.career, department=self.dept_a
        )
        self.subject_b = Subject.objects.create(
            name='Subject B List', code='SUBB-LIST', career=self.career, department=self.dept_b
        )

        # Offerings
        self.offering_a = SubjectOffering.objects.create(
            subject=self.subject_a,
            period=self.period,
            department=self.dept_a,
            max_students=30,
            is_active=True,
        )
        self.offering_b = SubjectOffering.objects.create(
            subject=self.subject_b,
            period=self.period,
            department=self.dept_b,
            max_students=30,
            is_active=True,
        )

        # Decision for teacher on offering_a (active period)
        self.decision = TeacherSubjectDecision.objects.create(
            teacher=self.teacher,
            offering=self.offering_a,
            period=self.period,
            decision='pending',
        )

        # Decision for other_teacher on offering_b
        self.other_decision = TeacherSubjectDecision.objects.create(
            teacher=self.other_teacher,
            offering=self.offering_b,
            period=self.period,
            decision='pending',
        )

    # ------------------------------------------------------------------
    # Task 1.2
    # ------------------------------------------------------------------
    def test_manager_gets_all_decisions(self):
        """Manager receives HTTP 200 and sees all decision rows."""
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(DECISIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        ids = [d['id'] for d in response.data]
        self.assertIn(self.decision.id, ids)
        self.assertIn(self.other_decision.id, ids)

    # ------------------------------------------------------------------
    # Task 1.3
    # ------------------------------------------------------------------
    def test_teacher_gets_only_own_decisions(self):
        """Teacher receives HTTP 200 and sees only their own rows."""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(DECISIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [d['id'] for d in response.data]
        self.assertIn(self.decision.id, ids)
        self.assertNotIn(self.other_decision.id, ids)

    # ------------------------------------------------------------------
    # Task 1.5
    # ------------------------------------------------------------------
    def test_student_forbidden_on_decisions(self):
        """Student receives HTTP 403."""
        self.client.force_authenticate(user=self.student)
        response = self.client.get(DECISIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ------------------------------------------------------------------
    # Task 1.6
    # ------------------------------------------------------------------
    def test_unauthenticated_decisions_returns_401(self):
        """Unauthenticated request receives HTTP 401."""
        response = self.client.get(DECISIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ------------------------------------------------------------------
    # Task 1.7
    # ------------------------------------------------------------------
    def test_period_filter_on_decisions(self):
        """Manager filters by another (non-active) period — expects empty list."""
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(DECISIONS_URL, {'period': self.other_period.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    # ------------------------------------------------------------------
    # Task 1.8
    # ------------------------------------------------------------------
    def test_teacher_filter_on_decisions(self):
        """Manager filters by a specific teacher — sees only that teacher's rows."""
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(DECISIONS_URL, {'teacher': self.teacher.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [d['id'] for d in response.data]
        self.assertIn(self.decision.id, ids)
        self.assertNotIn(self.other_decision.id, ids)


class TeacherSubjectDecisionReviewViewTests(TestCase):
    """
    Tests for PATCH /api/academic/teacher-subject-selection/decisions/<pk>/review/

    The frontend (subject-decisions.astro) sends `{'action': 'approved' | 'rejected'}`,
    NOT `{'decision': ...}`. The view must translate `action` -> `decision` before
    handing data to the serializer; passing raw request.data silently drops the
    unrecognized `action` key under partial=True, leaving `decision` unchanged.
    """

    def setUp(self):
        self.client = APIClient()

        self.period = AcademicPeriod.objects.create(
            name='2026-review',
            code='2026-rev',
            start_date='2026-01-01',
            end_date='2026-12-31',
            is_active=True,
        )

        self.teacher = User.objects.create_user(
            username='teacher-review', password='pass12345', role='t'
        )
        self.manager = User.objects.create_user(
            username='manager-review', password='pass12345', role='m'
        )

        self.career = Career.objects.create(name='Career Review', code='CAR-REVIEW')
        self.dept = Department.objects.create(
            name='Dept Review', code='DPT-REVIEW',
        )
        self.subject = Subject.objects.create(
            name='Subject Review', code='SUB-REVIEW', career=self.career, department=self.dept
        )
        self.offering = SubjectOffering.objects.create(
            subject=self.subject,
            period=self.period,
            department=self.dept,
            max_students=30,
            is_active=True,
        )

        self.decision = TeacherSubjectDecision.objects.create(
            teacher=self.teacher,
            offering=self.offering,
            period=self.period,
            decision='selected',
        )

    def test_manager_approve_sets_decision_approved(self):
        """PATCH with {'action': 'approved'} updates decision to 'approved'."""
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            review_url(self.decision.pk), {'action': 'approved'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        self.decision.refresh_from_db()
        self.assertEqual(self.decision.decision, 'approved')
        self.assertEqual(self.decision.decided_by, self.manager)

    def test_manager_reject_sets_decision_rejected(self):
        """PATCH with {'action': 'rejected'} updates decision to 'rejected'."""
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            review_url(self.decision.pk), {'action': 'rejected'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        self.decision.refresh_from_db()
        self.assertEqual(self.decision.decision, 'rejected')
        self.assertEqual(self.decision.decided_by, self.manager)

    def test_review_invalid_action_returns_400(self):
        """PATCH with an unrecognized action returns 400 and leaves decision unchanged."""
        self.client.force_authenticate(user=self.manager)
        response = self.client.patch(
            review_url(self.decision.pk), {'action': 'banana'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

        self.decision.refresh_from_db()
        self.assertEqual(self.decision.decision, 'selected')

    def test_teacher_cannot_review_decision(self):
        """Teacher (role='t') is forbidden from calling the review endpoint."""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.patch(
            review_url(self.decision.pk), {'action': 'approved'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.decision.refresh_from_db()
        self.assertEqual(self.decision.decision, 'selected')
