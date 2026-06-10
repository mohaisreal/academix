"""
Tests for SubjectOffering CRUD, activation, teacher selection, management review,
and timetabling gate.

TDD: Tests are written BEFORE the implementing code.
"""
import json
import os

from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient

from academic.models import (
    AcademicPeriod,
    Career,
    Department,
    Subject,
    TeacherSubjectDecision,
)
from users.models import User


# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------
OFFERINGS_URL = '/api/academic/offerings/'
DECISIONS_URL = '/api/academic/teacher-subject-selection/decisions/'
REVIEW_URL_TEMPLATE = '/api/academic/teacher-subject-selection/decisions/{pk}/review/'


def review_url(pk):
    return REVIEW_URL_TEMPLATE.format(pk=pk)


# ---------------------------------------------------------------------------
# Shared fixture mixin
# ---------------------------------------------------------------------------
class BaseOfferingFixture(TestCase):
    """Common DB fixtures shared by all offering/decision test classes."""

    def setUp(self):
        self.client = APIClient()

        self.period = AcademicPeriod.objects.create(
            name='2026-offering',
            code='2026-off',
            start_date='2026-01-01',
            end_date='2026-12-31',
            is_active=True,
        )
        self.other_period = AcademicPeriod.objects.create(
            name='2025-offering',
            code='2025-off',
            start_date='2025-01-01',
            end_date='2025-12-31',
            is_active=False,
        )

        self.career = Career.objects.create(name='Career Off', code='CAR-OFF')

        self.manager = User.objects.create_user(
            username='manager-off', password='pass12345', role='m'
        )
        self.teacher = User.objects.create_user(
            username='teacher-off', password='pass12345', role='t'
        )
        self.student = User.objects.create_user(
            username='student-off', password='pass12345', role='s'
        )

        self.dept = Department.objects.create(
            name='Dept Off', code='DEPT-OFF', teacher=self.teacher
        )
        self.subject = Subject.objects.create(
            name='Subject Off', code='SUBOFF-A', career=self.career, department=self.dept
        )
        self.subject_b = Subject.objects.create(
            name='Subject Off B', code='SUBOFF-B', career=self.career, department=self.dept
        )

    # Helper: create an offering via the API as the manager
    def _create_offering(self, subject=None, period=None, label='', max_students=30):
        subject = subject or self.subject
        period = period or self.period
        self.client.force_authenticate(user=self.manager)
        payload = {
            'subject_id': subject.id,
            'period_id': period.id,
            'department_id': self.dept.id,
            'max_students': max_students,
            'label': label,
        }
        return self.client.post(OFFERINGS_URL, payload, format='json')

    # Helper: create an offering directly in the DB (bypasses API)
    def _make_offering(self, subject=None, period=None, label='', is_active=False, max_students=30):
        from academic.models import SubjectOffering
        subject = subject or self.subject
        period = period or self.period
        return SubjectOffering.objects.create(
            subject=subject,
            period=period,
            department=self.dept,
            max_students=max_students,
            label=label,
            is_active=is_active,
        )


# ===========================================================================
# 7.1  SubjectOffering creation — management succeeds (201)
# 7.2  SubjectOffering creation — teacher gets 403
# 7.3  Duplicate subject+period+label → 400
# 7.3b Same subject+period but different label → 201
# ===========================================================================
class SubjectOfferingCreationTests(BaseOfferingFixture):

    def test_management_can_create_offering(self):
        """POST /api/academic/offerings/ as management → 201."""
        response = self._create_offering()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertIn('id', response.data)

    def test_teacher_cannot_create_offering(self):
        """POST /api/academic/offerings/ as teacher → 403."""
        self.client.force_authenticate(user=self.teacher)
        payload = {
            'subject_id': self.subject.id,
            'period_id': self.period.id,
            'department_id': self.dept.id,
            'max_students': 30,
            'label': '',
        }
        response = self.client.post(OFFERINGS_URL, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_create_offering(self):
        """POST /api/academic/offerings/ as student → 403."""
        self.client.force_authenticate(user=self.student)
        payload = {
            'subject_id': self.subject.id,
            'period_id': self.period.id,
            'department_id': self.dept.id,
            'max_students': 30,
            'label': '',
        }
        response = self.client.post(OFFERINGS_URL, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_create_offering(self):
        """POST /api/academic/offerings/ unauthenticated → 401."""
        payload = {
            'subject_id': self.subject.id,
            'period_id': self.period.id,
            'department_id': self.dept.id,
            'max_students': 30,
        }
        response = self.client.post(OFFERINGS_URL, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_duplicate_subject_period_label_returns_400(self):
        """Two offerings with same subject+period+label → second returns 400."""
        self._create_offering(label='Section A')
        response = self._create_offering(label='Section A')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_same_subject_period_different_label_returns_201(self):
        """Same subject+period but different label → both succeed."""
        r1 = self._create_offering(label='Section A')
        r2 = self._create_offering(label='Section B')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)

    def test_offering_is_inactive_by_default(self):
        """Newly created offering has is_active=False."""
        response = self._create_offering()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response.data['is_active'])


# ===========================================================================
# 7.4  Activation / deactivation
# ===========================================================================
class SubjectOfferingActivationTests(BaseOfferingFixture):

    def setUp(self):
        super().setUp()
        self.offering = self._make_offering(is_active=False)

    def test_management_activates_offering(self):
        """PATCH /offerings/<id>/activate/ → is_active becomes True."""
        self.client.force_authenticate(user=self.manager)
        url = f'{OFFERINGS_URL}{self.offering.id}/activate/'
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.offering.refresh_from_db()
        self.assertTrue(self.offering.is_active)

    def test_management_deactivates_offering(self):
        """PATCH /offerings/<id>/deactivate/ → is_active becomes False."""
        self.offering.is_active = True
        self.offering.save()
        self.client.force_authenticate(user=self.manager)
        url = f'{OFFERINGS_URL}{self.offering.id}/deactivate/'
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.offering.refresh_from_db()
        self.assertFalse(self.offering.is_active)

    def test_teacher_cannot_activate_offering(self):
        """Teacher cannot activate an offering — 403."""
        self.client.force_authenticate(user=self.teacher)
        url = f'{OFFERINGS_URL}{self.offering.id}/activate/'
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_inactive_offering_not_visible_to_teacher(self):
        """Teacher list with ?active=true excludes inactive offerings."""
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(OFFERINGS_URL, {'active': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [o['id'] for o in response.data]
        self.assertNotIn(self.offering.id, ids)

    def test_active_offering_visible_to_teacher(self):
        """Teacher list with ?active=true shows active offerings."""
        self.offering.is_active = True
        self.offering.save()
        self.client.force_authenticate(user=self.teacher)
        response = self.client.get(OFFERINGS_URL, {'active': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [o['id'] for o in response.data]
        self.assertIn(self.offering.id, ids)


# ===========================================================================
# 7.5  Teacher selection → creates pending decision
# 7.6  Teacher cannot select inactive offering
# 7.5b Teacher can select multiple offerings in same period
# ===========================================================================
class TeacherSelectionTests(BaseOfferingFixture):

    def setUp(self):
        super().setUp()
        self.active_offering = self._make_offering(subject=self.subject, is_active=True)
        self.active_offering_b = self._make_offering(subject=self.subject_b, is_active=True)
        self.inactive_offering = self._make_offering(subject=self.subject, label='Inactive', is_active=False)

    def test_teacher_selects_active_offering_creates_pending_decision(self):
        """POST /offerings/<id>/select/ as teacher → TeacherSubjectDecision with decision='pending'."""
        self.client.force_authenticate(user=self.teacher)
        url = f'{OFFERINGS_URL}{self.active_offering.id}/select/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        decision = TeacherSubjectDecision.objects.get(
            teacher=self.teacher, offering=self.active_offering
        )
        self.assertEqual(decision.decision, 'pending')

    def test_teacher_cannot_select_inactive_offering(self):
        """POST /offerings/<id>/select/ on inactive offering → 400."""
        self.client.force_authenticate(user=self.teacher)
        url = f'{OFFERINGS_URL}{self.inactive_offering.id}/select/'
        response = self.client.post(url)
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN])
        self.assertFalse(
            TeacherSubjectDecision.objects.filter(
                teacher=self.teacher, offering=self.inactive_offering
            ).exists()
        )

    def test_teacher_can_select_multiple_offerings_same_period(self):
        """Teacher can select multiple active offerings in the same period."""
        self.client.force_authenticate(user=self.teacher)
        r1 = self.client.post(f'{OFFERINGS_URL}{self.active_offering.id}/select/')
        r2 = self.client.post(f'{OFFERINGS_URL}{self.active_offering_b.id}/select/')
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED, r1.data)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED, r2.data)
        self.assertEqual(
            TeacherSubjectDecision.objects.filter(teacher=self.teacher, period=self.period).count(), 2
        )

    def test_management_cannot_select_offering(self):
        """Management cannot call the teacher-select endpoint — 403."""
        self.client.force_authenticate(user=self.manager)
        url = f'{OFFERINGS_URL}{self.active_offering.id}/select/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ===========================================================================
# 7.7  Management approve / reject decision
# ===========================================================================
class ManagementReviewTests(BaseOfferingFixture):

    def setUp(self):
        super().setUp()
        self.offering = self._make_offering(is_active=True)
        self.decision = TeacherSubjectDecision.objects.create(
            teacher=self.teacher,
            offering=self.offering,
            period=self.period,
            decision='pending',
        )

    def test_management_approves_decision(self):
        """PATCH review with {'action': 'approved'} → decision becomes 'approved'."""
        self.client.force_authenticate(user=self.manager)
        url = review_url(self.decision.pk)
        response = self.client.patch(url, {'action': 'approved'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.decision.refresh_from_db()
        self.assertEqual(self.decision.decision, 'approved')

    def test_management_rejects_decision(self):
        """PATCH review with {'action': 'rejected'} → decision becomes 'rejected'."""
        self.client.force_authenticate(user=self.manager)
        url = review_url(self.decision.pk)
        response = self.client.patch(url, {'action': 'rejected'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.decision.refresh_from_db()
        self.assertEqual(self.decision.decision, 'rejected')

    def test_management_rejects_approved_decision_removes_generated_class(self):
        """Approved→rejected must invalidate generated class projections."""
        from academic.models import Class, Classroom
        from enrollment.models import ClassEnrollment, CareerEnrollment
        from academic.timetabling import prepare_classes_for_period

        self.client.force_authenticate(user=self.manager)
        Classroom.objects.create(name='Room X', building='Main', capacity=30)
        self.client.patch(review_url(self.decision.pk), {'action': 'approved'}, format='json')
        prepare_classes_for_period(self.period)
        generated_class = Class.objects.get(period=self.period, subject=self.subject)

        student = self.student
        CareerEnrollment.objects.create(student=student, career=self.career, period=self.period, status='active')
        class_enrollment = ClassEnrollment.objects.create(student=student, cls=generated_class, status='enrolled')

        response = self.client.patch(review_url(self.decision.pk), {'action': 'rejected'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertFalse(Class.objects.filter(pk=generated_class.pk).exists())
        class_enrollment.refresh_from_db()
        self.assertIsNone(class_enrollment.cls)
        self.assertEqual(class_enrollment.status, 'dropped')

    def test_teacher_cannot_approve_decision(self):
        """Teacher cannot call review endpoint — 403."""
        self.client.force_authenticate(user=self.teacher)
        url = review_url(self.decision.pk)
        response = self.client.patch(url, {'action': 'approved'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ===========================================================================
# 7.8  Timetabling gate: generator skips non-approved decisions
# 7.9  Timetabling gate: generator skips approved decision with inactive offering
# ===========================================================================
class TimetablingGateTests(BaseOfferingFixture):
    """
    Tests the prepare_classes_for_period() filter:
    only decision='approved' AND offering.is_active=True enters the generator.
    """

    def setUp(self):
        super().setUp()
        from academic.models import Classroom
        self.classroom = Classroom.objects.create(
            name='Room Off', building='Building Off', capacity=30
        )

    def _make_decision(self, decision_value, is_active_offering=True, subject=None):
        from academic.models import SubjectOffering
        subject = subject or self.subject
        offering = SubjectOffering.objects.create(
            subject=subject,
            period=self.period,
            department=self.dept,
            max_students=30,
            is_active=is_active_offering,
        )
        return TeacherSubjectDecision.objects.create(
            teacher=self.teacher,
            offering=offering,
            period=self.period,
            decision=decision_value,
        )

    def test_generator_skips_pending_decisions(self):
        """pending decision → no Class created."""
        from academic.models import Class
        from academic.timetabling import prepare_classes_for_period
        self._make_decision('pending', is_active_offering=True)
        prepare_classes_for_period(self.period)
        self.assertEqual(Class.objects.filter(period=self.period).count(), 0)

    def test_generator_skips_rejected_decisions(self):
        """rejected decision → no Class created."""
        from academic.models import Class
        from academic.timetabling import prepare_classes_for_period
        self._make_decision('rejected', is_active_offering=True)
        prepare_classes_for_period(self.period)
        self.assertEqual(Class.objects.filter(period=self.period).count(), 0)

    def test_generator_skips_approved_decision_with_inactive_offering(self):
        """approved decision but offering.is_active=False → no Class created."""
        from academic.models import Class
        from academic.timetabling import prepare_classes_for_period
        self._make_decision('approved', is_active_offering=False)
        prepare_classes_for_period(self.period)
        self.assertEqual(Class.objects.filter(period=self.period).count(), 0)

    def test_generator_includes_approved_active_decision(self):
        """approved decision AND offering.is_active=True → Class is created."""
        from academic.models import Class
        from academic.timetabling import prepare_classes_for_period
        self._make_decision('approved', is_active_offering=True)
        prepare_classes_for_period(self.period)
        self.assertGreater(Class.objects.filter(period=self.period).count(), 0)


# ===========================================================================
# 7.10  N+1 fix: decision list query count is O(1) relative to N rows
# ===========================================================================
class DecisionListQueryCountTests(BaseOfferingFixture):
    """
    Confirm that GET /decisions/ does not scale queries linearly with N.
    Uses CaptureQueriesContext to assert query count <= N + 2.
    """

    def setUp(self):
        super().setUp()
        from academic.models import SubjectOffering
        self.offerings = []
        for i in range(10):
            subj = Subject.objects.create(
                name=f'Subject QC {i}', code=f'QC-{i:03}', career=self.career, department=self.dept
            )
            offering = SubjectOffering.objects.create(
                subject=subj,
                period=self.period,
                department=self.dept,
                max_students=30,
                is_active=True,
            )
            self.offerings.append(offering)
            TeacherSubjectDecision.objects.create(
                teacher=self.teacher,
                offering=offering,
                period=self.period,
                decision='pending',
            )

    def test_decision_list_query_count_is_bounded(self):
        """Decision list endpoint issues at most N+2 queries for N=10 decisions."""
        self.client.force_authenticate(user=self.manager)
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(DECISIONS_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        n_decisions = len(response.data)
        # Must be constant (O(1)) — definitely not one query per decision
        # Allow a reasonable fixed budget: auth + queryset + a few related = < n_decisions
        self.assertLessEqual(
            len(ctx.captured_queries),
            n_decisions,  # if linear, this would fail; if O(1) it passes
            f"Too many queries: {len(ctx.captured_queries)} for {n_decisions} decisions. "
            "Expected constant-time query count. Likely missing select_related on offering."
        )


# ===========================================================================
# 7.11  No role='d' regression
# ===========================================================================
class NoDRoleRegressionTests(TestCase):
    """
    Confirm that no Python source file under backend/ contains role='d' references.
    """

    def test_no_role_d_in_backend_source(self):
        """No Python source file under backend/ contains role='d' access-check patterns."""
        import re

        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

        # Files to skip — they legitimately contain 'd' as test data or as string literals
        # inside test code (including this file).
        skip_filenames = {
            'tests_subject_offering.py',
            'tests_teacher_subject_list_api.py',
        }

        # Compiled patterns that should be absent from non-test source files
        forbidden = re.compile(
            r"role\s*(==|!=|__in)\s*['\"]d['\"]"
            r"|role__in\s*=\s*\[.*'d'.*\]"
            r"|role__in\s*=\s*\[.*\"d\".*\]"
        )

        violations = []
        for root, dirs, files in os.walk(backend_dir):
            # Skip non-source directories
            dirs[:] = [
                d for d in dirs
                if d not in ('__pycache__', '.git', 'migrations', 'venv', '.venv', 'node_modules')
            ]
            for filename in files:
                if not filename.endswith('.py'):
                    continue
                if filename in skip_filenames:
                    continue
                filepath = os.path.join(root, filename)
                with open(filepath, encoding='utf-8', errors='ignore') as fh:
                    for lineno, line in enumerate(fh, 1):
                        if forbidden.search(line):
                            violations.append(f"{filepath}:{lineno}: {line.rstrip()}")

        self.assertEqual(
            violations, [],
            "Found role='d' access-check patterns in backend source files:\n"
            + "\n".join(violations),
        )
