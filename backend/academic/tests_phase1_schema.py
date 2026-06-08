from django.test import TestCase

from users.models import User
from academic.models import AcademicPeriod, Career, Class, Classroom, Subject, TeacherSubjectDecision, TeacherSubjectEligibility
from academic.serializers import ClassSerializer


class Phase1SchemaFoundationTests(TestCase):
    def setUp(self):
        self.career = Career.objects.create(name='Career A', code='CAR-A')
        self.subject = Subject.objects.create(name='Subject A', code='SUB-A', career=self.career)
        self.period = AcademicPeriod.objects.create(
            name='2026',
            code='2026',
            start_date='2026-01-01',
            end_date='2026-12-31',
        )
        self.classroom = Classroom.objects.create(name='Room 1', building='Main', capacity=30)
        self.teacher = User.objects.create_user(username='teacher-a', password='pass12345', role='t')
        self.reviewer = User.objects.create_user(username='reviewer-a', password='pass12345', role='d')

    def test_class_exposes_section_label_and_source_teacher_decision(self):
        decision = TeacherSubjectDecision.objects.create(
            teacher=self.teacher,
            subject=self.subject,
            period=self.period,
            decision='none',
            decided_by=self.reviewer,
        )

        cls = Class.objects.create(
            subject=self.subject,
            period=self.period,
            classroom=self.classroom,
            max_students=20,
            section_label='A',
            source_teacher_decision=decision,
        )

        cls.refresh_from_db()

        self.assertEqual(cls.section_label, 'A')
        self.assertEqual(cls.source_teacher_decision_id, decision.id)

    def test_class_allows_same_subject_period_when_section_label_differs(self):
        Class.objects.create(
            subject=self.subject,
            period=self.period,
            classroom=self.classroom,
            max_students=20,
            section_label='A',
        )

        other = Class.objects.create(
            subject=self.subject,
            period=self.period,
            classroom=self.classroom,
            max_students=20,
            section_label='B',
        )

        self.assertEqual(other.section_label, 'B')

    def test_teacher_subject_eligibility_model_exists_for_department_head_review(self):
        eligibility = TeacherSubjectEligibility.objects.create(
            teacher=self.teacher,
            subject=self.subject,
            period=self.period,
            is_eligible=True,
            reviewed_by=self.reviewer,
        )

        self.assertTrue(eligibility.is_eligible)

    def test_class_serializer_exposes_section_and_source_decision_fields(self):
        decision = TeacherSubjectDecision.objects.create(
            teacher=self.teacher,
            subject=self.subject,
            period=self.period,
            decision='none',
            decided_by=self.reviewer,
        )
        cls = Class.objects.create(
            subject=self.subject,
            period=self.period,
            classroom=self.classroom,
            max_students=20,
            section_label='A',
            source_teacher_decision=decision,
        )

        data = ClassSerializer(cls).data
        self.assertEqual(data['section_label'], 'A')
        self.assertEqual(data['source_teacher_decision'], decision.id)
