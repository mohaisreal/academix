from datetime import time

from django.test import TestCase

from academic.models import AcademicPeriod, Career, Classroom, Class, Department, Subject, TeacherSubjectDecision, TeacherSubjectEligibility, TimeSlot, TimetableRun
from academic.timetabling import generate_for_run
from users.models import User


class Phase3TimetableTests(TestCase):
    def setUp(self):
        self.period = AcademicPeriod.objects.create(name='2026', code='2026', start_date='2026-01-01', end_date='2026-12-31', is_active=True)
        self.career = Career.objects.create(name='Career A', code='CAR-A')
        self.department_head = User.objects.create_user(username='head-p3', password='pass12345', role='d')
        self.department = Department.objects.create(name='Department A', code='DEP-A', teacher=self.department_head)
        self.teacher = User.objects.create_user(username='teacher-p3', password='pass12345', role='t')
        self.subject = Subject.objects.create(name='Subject A', code='SUB-A', career=self.career, department=self.department, hours_per_week=1)
        self.classroom = Classroom.objects.create(name='Room 1', building='Main', capacity=40)
        self.slot1 = TimeSlot.objects.create(period=self.period, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))
        self.slot2 = TimeSlot.objects.create(period=self.period, day_of_week=1, start_time=time(8, 0), end_time=time(9, 0))

    def test_generate_uses_reviewed_decisions_and_sections(self):
        TeacherSubjectEligibility.objects.create(teacher=self.teacher, subject=self.subject, period=self.period, is_eligible=True, reviewed_by=self.department_head)
        decision = TeacherSubjectDecision.objects.create(teacher=self.teacher, subject=self.subject, period=self.period, decision='selected', decided_by=self.department_head)

        run = TimetableRun.objects.create(period=self.period, status='draft')
        result = generate_for_run(run)

        self.assertEqual(result.status, 'completed')
        cls = Class.objects.get(period=self.period, subject=self.subject)
        self.assertEqual(cls.section_label, 'A')
        self.assertEqual(cls.source_teacher_decision_id, decision.id)
        self.assertTrue(result.assignments.exists())

    def test_sibling_sections_are_assigned_different_days(self):
        teacher2 = User.objects.create_user(username='teacher-p3b', password='pass12345', role='t')
        TeacherSubjectEligibility.objects.create(teacher=self.teacher, subject=self.subject, period=self.period, is_eligible=True, reviewed_by=self.department_head)
        TeacherSubjectEligibility.objects.create(teacher=teacher2, subject=self.subject, period=self.period, is_eligible=True, reviewed_by=self.department_head)
        TeacherSubjectDecision.objects.create(teacher=self.teacher, subject=self.subject, period=self.period, decision='selected', decided_by=self.department_head)
        TeacherSubjectDecision.objects.create(teacher=teacher2, subject=self.subject, period=self.period, decision='selected', decided_by=self.department_head)

        run = TimetableRun.objects.create(period=self.period, status='draft')
        generate_for_run(run)

        classes = list(Class.objects.filter(period=self.period, subject=self.subject).order_by('section_label'))
        self.assertEqual([cls.section_label for cls in classes], ['A', 'B'])
        self.assertNotEqual(
            classes[0].schedule_assignments.first().slot.day_of_week,
            classes[1].schedule_assignments.first().slot.day_of_week,
        )

    def test_generate_skips_explicit_none_and_keeps_legacy_when_no_decisions(self):
        TeacherSubjectEligibility.objects.create(teacher=self.teacher, subject=self.subject, period=self.period, is_eligible=True, reviewed_by=self.department_head)
        TeacherSubjectDecision.objects.create(teacher=self.teacher, subject=self.subject, period=self.period, decision='none', decided_by=self.department_head)

        run = TimetableRun.objects.create(period=self.period, status='draft')
        result = generate_for_run(run)

        self.assertEqual(result.status, 'completed')
        self.assertEqual(Class.objects.filter(period=self.period, subject=self.subject).count(), 0)

    def test_generate_ignores_stale_or_ineligible_decisions(self):
        eligibility = TeacherSubjectEligibility.objects.create(teacher=self.teacher, subject=self.subject, period=self.period, is_eligible=True, reviewed_by=self.department_head)
        decision = TeacherSubjectDecision.objects.create(teacher=self.teacher, subject=self.subject, period=self.period, decision='selected', decided_by=self.department_head)
        eligibility.is_eligible = False
        eligibility.save(update_fields=['is_eligible', 'updated_at'])

        run = TimetableRun.objects.create(period=self.period, status='draft')
        generate_for_run(run)

        self.assertEqual(Class.objects.filter(period=self.period, subject=self.subject).count(), 0)
        self.assertFalse(run.assignments.exists())

    def test_generate_legacy_fallback_creates_class_when_no_decisions_exist(self):
        run = TimetableRun.objects.create(period=self.period, status='draft')
        result = generate_for_run(run)

        self.assertEqual(result.status, 'completed')
        self.assertEqual(Class.objects.filter(period=self.period, subject=self.subject).count(), 1)
        self.assertEqual(Class.objects.get(period=self.period, subject=self.subject).section_label, 'A')
