from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from admissions.models import AdmissionApplication
from academic.models import AcademicPeriod, Career, Classroom, Department, Subject, TeacherSubjectDecision, TeacherSubjectEligibility
from users.models import User


class Phase2CoreApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.period = AcademicPeriod.objects.create(
            name='2026',
            code='2026',
            start_date='2026-01-01',
            end_date='2026-12-31',
            is_active=True,
        )
        self.teacher = User.objects.create_user(username='teacher-p2', password='pass12345', role='t')
        self.department_head = User.objects.create_user(username='head-p2', password='pass12345', role='d')
        self.other_head = User.objects.create_user(username='head-other', password='pass12345', role='d')
        self.department = Department.objects.create(name='Department A', code='DEP-A', teacher=self.department_head)
        self.other_department = Department.objects.create(name='Department B', code='DEP-B', teacher=self.other_head)
        self.career = Career.objects.create(name='Career A', code='CAR-A')
        self.subject = Subject.objects.create(name='Subject A', code='SUB-A', career=self.career, department=self.department)
        self.other_subject = Subject.objects.create(name='Subject B', code='SUB-B', career=self.career, department=self.other_department)
        self.eligibility = TeacherSubjectEligibility.objects.create(
            teacher=self.teacher,
            subject=self.subject,
            period=self.period,
            is_eligible=True,
            reviewed_by=self.department_head,
        )

    def test_teacher_can_submit_selected_subjects_and_none_is_valid(self):
        self.client.force_authenticate(user=self.teacher)

        response = self.client.post(
            '/api/academic/teacher-subject-selection/submit/',
            {'decision': 'selected', 'subject_ids': [self.subject.id]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['current_period']['id'], self.period.id)
        self.assertEqual(len(response.data['results']), 1)

        none_response = self.client.post(
            '/api/academic/teacher-subject-selection/submit/',
            {'decision': 'none'},
            format='json',
        )
        self.assertEqual(none_response.status_code, status.HTTP_200_OK)
        self.assertEqual(none_response.data['results'], [])
        self.assertTrue(
            TeacherSubjectDecision.objects.filter(
                teacher=self.teacher,
                subject=self.subject,
                period=self.period,
                decision='none',
            ).exists()
        )

    def test_submit_rejects_empty_selected_and_wrong_department(self):
        self.client.force_authenticate(user=self.teacher)

        empty = self.client.post(
            '/api/academic/teacher-subject-selection/submit/',
            {'decision': 'selected', 'subject_ids': []},
            format='json',
        )
        self.assertEqual(empty.status_code, status.HTTP_400_BAD_REQUEST)

        wrong = self.client.post(
            '/api/academic/teacher-subject-selection/submit/',
            {'decision': 'selected', 'subject_ids': [self.other_subject.id]},
            format='json',
        )
        self.assertEqual(wrong.status_code, status.HTTP_400_BAD_REQUEST)

    def test_department_head_can_review_and_eligibility_edit_marks_decisions_stale(self):
        self.client.force_authenticate(user=self.teacher)
        submit = self.client.post(
            '/api/academic/teacher-subject-selection/submit/',
            {'decision': 'selected', 'subject_ids': [self.subject.id]},
            format='json',
        )
        decision_id = submit.data['results'][0]['id']

        self.client.force_authenticate(user=self.department_head)
        review = self.client.patch(
            f'/api/academic/teacher-subject-selection/decisions/{decision_id}/review/',
            {'decision': 'approve', 'notes': 'ok'},
            format='json',
        )
        self.assertEqual(review.status_code, status.HTTP_200_OK)
        self.assertEqual(review.data['decision'], 'approve')

        eligibility = self.client.patch(
            f'/api/academic/teacher-subject-selection/eligibilities/{self.eligibility.id}/',
            {'is_eligible': False},
            format='json',
        )
        self.assertEqual(eligibility.status_code, status.HTTP_200_OK)

        self.assertFalse(TeacherSubjectEligibility.objects.get(pk=self.eligibility.id).is_eligible)

    def test_review_and_edit_permissions_are_department_scoped(self):
        self.client.force_authenticate(user=self.teacher)
        submit = self.client.post(
            '/api/academic/teacher-subject-selection/submit/',
            {'decision': 'selected', 'subject_ids': [self.subject.id]},
            format='json',
        )
        decision_id = submit.data['results'][0]['id']

        self.client.force_authenticate(user=self.other_head)
        review = self.client.patch(
            f'/api/academic/teacher-subject-selection/decisions/{decision_id}/review/',
            {'decision': 'reject', 'notes': 'wrong department'},
            format='json',
        )
        self.assertEqual(review.status_code, status.HTTP_403_FORBIDDEN)

        eligibility = self.client.patch(
            f'/api/academic/teacher-subject-selection/eligibilities/{self.eligibility.id}/',
            {'is_eligible': False},
            format='json',
        )
        self.assertEqual(eligibility.status_code, status.HTTP_403_FORBIDDEN)

    def test_decision_becomes_stale_when_eligibility_changes(self):
        self.client.force_authenticate(user=self.teacher)
        submit = self.client.post(
            '/api/academic/teacher-subject-selection/submit/',
            {'decision': 'selected', 'subject_ids': [self.subject.id]},
            format='json',
        )
        decision_id = submit.data['results'][0]['id']

        self.client.force_authenticate(user=self.department_head)
        self.client.patch(
            f'/api/academic/teacher-subject-selection/eligibilities/{self.eligibility.id}/',
            {'is_eligible': False},
            format='json',
        )

        from academic.models import TeacherSubjectDecision
        from academic.serializers import TeacherSubjectDecisionSerializer

        decision = TeacherSubjectDecision.objects.get(pk=decision_id)
        self.assertTrue(TeacherSubjectDecisionSerializer(decision).data['stale'])

    def test_period_scoped_views_expose_current_period_context(self):
        applicant = User.objects.create_user(username='student-p2', password='pass12345', role='s')
        AdmissionApplication.objects.create(student=applicant, academic_period=self.period, status='draft')

        self.client.force_authenticate(user=applicant)
        enrollment = self.client.get('/api/enrollment/my-enrollment/')
        self.assertIn('current_period', enrollment.data)

        self.client.force_authenticate(user=self.department_head)
        admissions = self.client.get('/api/admissions/applications/')
        self.assertIn('current_period', admissions.data)
