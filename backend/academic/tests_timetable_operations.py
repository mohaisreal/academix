from datetime import time
from io import StringIO

from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import override_settings
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from academic.models import (
    AcademicPeriod,
    Career,
    Class,
    Classroom,
    Subject,
    TimeSlot,
    TimetableRun,
    ScheduleAssignment,
    ConstraintViolation,
    ClassSchedule,
    SchedulingConstraint,
    Department,
)
from academic.timetabling import backfill_generated_class_teachers, generate_for_run
from academic.models import TeacherSubjectDecision
from enrollment.models import ClassEnrollment
from users.models import User


def make_manager(username='mgr_timetable'):
    user = User.objects.create_user(
        username=username,
        email=f'{username}@test.com',
        password='testpass123',
        is_active=True,
    )
    user.role = 'm'
    user.save()
    return user


def make_admin(username='admin_timetable'):
    user = User.objects.create_user(
        username=username,
        email=f'{username}@test.com',
        password='testpass123',
        is_active=True,
    )
    user.role = 'a'
    user.save()
    return user


def make_period(code='P2026A', active=True):
    return AcademicPeriod.objects.create(
        name=f'Period {code}',
        code=code,
        start_date='2026-01-01',
        end_date='2026-06-30',
        is_active=active,
    )


def make_student(username='student_timetable'):
    return User.objects.create_user(
        username=username,
        email=f'{username}@test.com',
        password='testpass123',
        role='s',
    )


def make_class(period, suffix='A'):
    career = Career.objects.create(name=f'Career {suffix}', code=f'CAR{suffix}')
    subject = Subject.objects.create(
        name=f'Subject {suffix}',
        code=f'SUB{suffix}',
        career=career,
    )
    teacher = User.objects.create_user(
        username=f'teacher_{suffix}',
        email=f'teacher_{suffix}@test.com',
        password='testpass123',
        role='t',
    )
    classroom = Classroom.objects.create(
        name=f'Room {suffix}',
        building='Main',
        capacity=40,
        type='lecture',
    )
    return Class.objects.create(
        subject=subject,
        teacher=teacher,
        period=period,
        classroom=classroom,
        max_students=30,
    )


def unwrap_results(payload):
    return payload.get('results', payload) if isinstance(payload, dict) else payload


class TimeSlotModelTests(TestCase):
    def test_slot_accepts_valid_boundaries(self):
        period = make_period('P2026TS1')
        slot = TimeSlot(
            period=period,
            day_of_week=0,
            start_time=time(8, 0),
            end_time=time(9, 0),
        )
        slot.full_clean()
        slot.save()
        self.assertEqual(TimeSlot.objects.count(), 1)

    def test_slot_rejects_invalid_boundaries(self):
        period = make_period('P2026TS2')
        slot = TimeSlot(
            period=period,
            day_of_week=0,
            start_time=time(10, 0),
            end_time=time(10, 0),
        )
        with self.assertRaises(ValidationError):
            slot.full_clean()


class TimetableGenerateAndPublishTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = make_manager()
        self.client.force_authenticate(user=self.manager)

    def test_generate_completed_with_assignments(self):
        period = make_period('P2026GEN1')
        cls = make_class(period, 'G1')
        cls.subject.hours_per_week = 1
        cls.subject.save(update_fields=['hours_per_week'])
        TimeSlot.objects.create(
            period=period,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('warning_summary', response.data)
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')
        self.assertGreater(run.assignments.count(), 0)
        self.assertIn('generator', run.metadata)

    def test_generate_persists_teacher_on_generated_class(self):
        period = make_period('P2026GEN1T')
        teacher = User.objects.create_user(
            username='teacher_gen_persist',
            email='teacher_gen_persist@test.com',
            password='testpass123',
            role='t',
        )
        department = Department.objects.create(name='Departamento GENP', code='DEP-GENP', teacher=teacher)
        career = Career.objects.create(name='Career GENP', code='CAR-GENP')
        subject = Subject.objects.create(
            name='Subject GENP', code='SUB-GENP', career=career, department=department, hours_per_week=1
        )
        classroom = Classroom.objects.create(name='Room GENP', building='Main', capacity=40, type='lecture')
        TimeSlot.objects.create(period=period, day_of_week=1, start_time=time(9, 0), end_time=time(10, 0))
        cls = Class.objects.create(subject=subject, teacher=None, period=period, classroom=classroom, max_students=30, is_generated_by_timetable=True)
        run = TimetableRun.objects.create(period=period)

        generate_for_run(run)

        cls.refresh_from_db()
        assignment = ScheduleAssignment.objects.get(run=run, cls=cls)
        self.assertEqual(cls.teacher_id, teacher.id)
        self.assertEqual(assignment.teacher_id, teacher.id)

    def test_seeded_teacher_decisions_generate_classes_with_teacher_assignments(self):
        call_command('seed_academic_base', stdout=StringIO())
        period = AcademicPeriod.objects.get(code='SEED-AP-01')

        approved = TeacherSubjectDecision.objects.filter(period=period, decision='approved', offering__is_active=True)
        self.assertEqual(approved.count(), 12)
        self.assertGreaterEqual(approved.values_list('offering__subject__code', flat=True).distinct().count(), 10)

        run = TimetableRun.objects.create(period=period)
        generate_for_run(run)

        generated = Class.objects.filter(period=period, is_generated_by_timetable=True)
        self.assertGreaterEqual(generated.count(), approved.count())
        self.assertEqual(generated.filter(teacher__isnull=True).count(), 0)
        self.assertEqual(generated.filter(source_teacher_decision__isnull=True).count(), 0)

    def test_generate_does_not_overwrite_manual_class_teacher(self):
        period = make_period('P2026GEN1M')
        persisted_teacher = User.objects.create_user(
            username='teacher_manual_persist',
            email='teacher_manual_persist@test.com',
            password='testpass123',
            role='t',
        )
        department_teacher = User.objects.create_user(
            username='teacher_dept_manual_persist',
            email='teacher_dept_manual_persist@test.com',
            password='testpass123',
            role='t',
        )
        department = Department.objects.create(name='Departamento GENM', code='DEP-GENM', teacher=department_teacher)
        career = Career.objects.create(name='Career GENM', code='CAR-GENM')
        subject = Subject.objects.create(
            name='Subject GENM', code='SUB-GENM', career=career, department=department, hours_per_week=1
        )
        classroom = Classroom.objects.create(name='Room GENM', building='Main', capacity=40, type='lecture')
        TimeSlot.objects.create(period=period, day_of_week=1, start_time=time(11, 0), end_time=time(12, 0))
        cls = Class.objects.create(subject=subject, teacher=persisted_teacher, period=period, classroom=classroom, max_students=30, is_generated_by_timetable=False)
        run = TimetableRun.objects.create(period=period)

        generate_for_run(run)

        cls.refresh_from_db()
        assignment = ScheduleAssignment.objects.get(run=run, cls=cls)
        self.assertEqual(cls.teacher_id, persisted_teacher.id)
        self.assertEqual(assignment.teacher_id, persisted_teacher.id)

    def test_generate_with_limited_slots_keeps_run_non_failed(self):
        period = make_period('P2026GEN2')
        make_class(period, 'G2A')
        make_class(period, 'G2B')
        TimeSlot.objects.create(
            period=period,
            day_of_week=2,
            start_time=time(8, 0),
            end_time=time(9, 0),
        )
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        run.refresh_from_db()
        self.assertIn(run.status, {'partial', 'completed'})
        self.assertIn('generator', run.metadata)

    def test_generate_failed_when_no_assignments_possible(self):
        period = make_period('P2026GEN3')
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        self.assertEqual(run.status, 'failed')
        self.assertIn('generator', run.metadata)

    def test_generate_fails_with_missing_classes_category(self):
        period = make_period('P2026GEN4')
        dep_teacher = User.objects.create_user(
            username='teacher_dep_g4',
            email='teacher_dep_g4@test.com',
            password='testpass123',
            role='t',
        )
        department = Department.objects.create(name='Departamento G4', code='DEP-G4', teacher=dep_teacher)
        career = Career.objects.create(name='Career G4', code='CAR-G4')
        Subject.objects.create(name='Subject G4', code='SUB-G4', career=career, department=department, is_active=True)
        Classroom.objects.create(name='Room G4', building='Main', capacity=35, type='lecture')
        TimeSlot.objects.create(
            period=period,
            day_of_week=0,
            start_time=time(8, 0),
            end_time=time(9, 0),
        )
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        run.refresh_from_db()
        self.assertIn(run.status, {'completed', 'partial'})
        self.assertEqual(Class.objects.filter(period=period).count(), 1)
        self.assertNotIn('missing_classes', run.metadata['generator'].get('precondition_errors', []))
        self.assertEqual(run.metadata['generator'].get('classes_created'), 1)
        for field in ['classes_created', 'classes_considered', 'generated_assignments', 'precondition_errors', 'class_preparation_errors']:
            self.assertIn(field, run.metadata['generator'])

    def test_generate_is_idempotent_for_prepared_classes(self):
        period = make_period('P2026GEN4B')
        dep_teacher = User.objects.create_user(
            username='teacher_dep_g4b',
            email='teacher_dep_g4b@test.com',
            password='testpass123',
            role='t',
        )
        department = Department.objects.create(name='Departamento G4B', code='DEP-G4B', teacher=dep_teacher)
        career = Career.objects.create(name='Career G4B', code='CAR-G4B')
        Subject.objects.create(name='Subject G4B', code='SUB-G4B', career=career, department=department, is_active=True)
        Classroom.objects.create(name='Room G4B', building='Main', capacity=35, type='lecture')
        TimeSlot.objects.create(period=period, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period)

        first = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')
        second = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        run.refresh_from_db()
        self.assertEqual(Class.objects.filter(period=period).count(), 1)
        self.assertEqual(run.metadata['generator'].get('classes_created'), 0)

    def test_generate_marks_newly_prepared_classes_as_generated(self):
        period = make_period('P2026GEN4B2')
        dep_teacher = User.objects.create_user(
            username='teacher_dep_g4b2',
            email='teacher_dep_g4b2@test.com',
            password='testpass123',
            role='t',
        )
        department = Department.objects.create(name='Departamento G4B2', code='DEP-G4B2', teacher=dep_teacher)
        career = Career.objects.create(name='Career G4B2', code='CAR-G4B2')
        Subject.objects.create(name='Subject G4B2', code='SUB-G4B2', career=career, department=department, is_active=True)
        Classroom.objects.create(name='Room G4B2', building='Main', capacity=35, type='lecture')
        TimeSlot.objects.create(period=period, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        generated_class = Class.objects.get(period=period)
        self.assertTrue(generated_class.is_generated_by_timetable)

    def test_generate_does_not_touch_existing_manual_classes(self):
        period = make_period('P2026GEN4B3')
        dep_teacher = User.objects.create_user(
            username='teacher_dep_g4b3',
            email='teacher_dep_g4b3@test.com',
            password='testpass123',
            role='t',
        )
        department = Department.objects.create(name='Departamento G4B3', code='DEP-G4B3', teacher=dep_teacher)
        career = Career.objects.create(name='Career G4B3', code='CAR-G4B3')
        subject = Subject.objects.create(name='Subject G4B3', code='SUB-G4B3', career=career, department=department, is_active=True)
        classroom = Classroom.objects.create(name='Room G4B3', building='Main', capacity=35, type='lecture')
        manual_class = Class.objects.create(
            subject=subject,
            teacher=None,
            period=period,
            classroom=classroom,
            max_students=30,
            is_generated_by_timetable=False,
        )
        TimeSlot.objects.create(period=period, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        manual_class.refresh_from_db()
        self.assertFalse(manual_class.is_generated_by_timetable)

    def test_generate_fails_when_no_active_subjects_for_preparation(self):
        period = make_period('P2026GEN4C')
        Career.objects.create(name='Career G4C', code='CAR-G4C')
        Classroom.objects.create(name='Room G4C', building='Main', capacity=35, type='lecture')
        TimeSlot.objects.create(period=period, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        self.assertIn('class_preparation_insufficient_subjects', run.metadata['generator'].get('class_preparation_errors', []))
        self.assertEqual(run.metadata['generator'].get('generated_assignments'), 0)
        for field in ['classes_created', 'classes_considered', 'generated_assignments', 'precondition_errors', 'class_preparation_errors']:
            self.assertIn(field, run.metadata['generator'])

    def test_generate_fails_when_no_classrooms_for_preparation(self):
        period = make_period('P2026GEN4D')
        career = Career.objects.create(name='Career G4D', code='CAR-G4D')
        Subject.objects.create(name='Subject G4D', code='SUB-G4D', career=career, is_active=True)
        TimeSlot.objects.create(period=period, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        self.assertIn('class_preparation_insufficient_classrooms', run.metadata['generator'].get('class_preparation_errors', []))
        self.assertEqual(run.metadata['generator'].get('generated_assignments'), 0)

    def test_generate_fails_with_missing_time_slots_category(self):
        period = make_period('P2026GEN5')
        make_class(period, 'G5')
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        self.assertIn('franjas', str(response.data['detail']).lower())
        run.refresh_from_db()
        self.assertIn('missing_time_slots', run.metadata['generator'].get('precondition_errors', []))

    def test_generate_fails_with_missing_classroom_category(self):
        period = make_period('P2026GEN6')
        cls = make_class(period, 'G6')
        cls.teacher = None
        cls.classroom = None
        cls.save(update_fields=['teacher', 'classroom'])
        TimeSlot.objects.create(
            period=period,
            day_of_week=2,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        categories = run.metadata['generator'].get('precondition_errors', [])
        self.assertIn('missing_classrooms', categories)

    def test_generate_uses_department_teacher_when_class_teacher_missing(self):
        period = make_period('P2026GEN7')
        fallback_teacher = User.objects.create_user(
            username='teacher_dep_g7',
            email='teacher_dep_g7@test.com',
            password='testpass123',
            role='t',
        )
        department = Department.objects.create(name='Departamento G7', code='DEP-G7', teacher=fallback_teacher)
        career = Career.objects.create(name='Career G7', code='CAR-G7')
        subject = Subject.objects.create(name='Subject G7', code='SUB-G7', career=career, department=department)
        subject.hours_per_week = 1
        subject.save(update_fields=['hours_per_week'])
        classroom = Classroom.objects.create(name='Room G7', building='Main', capacity=30, type='lecture')
        cls = Class.objects.create(subject=subject, teacher=None, period=period, classroom=classroom, max_students=30)
        TimeSlot.objects.create(period=period, day_of_week=1, start_time=time(9, 0), end_time=time(10, 0))
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')
        assignment = ScheduleAssignment.objects.get(run=run, cls=cls)
        self.assertEqual(assignment.teacher_id, fallback_teacher.id)
        unresolved = run.metadata['generator'].get('unresolved_teachers', [])
        self.assertEqual(unresolved, [])

    def test_class_teacher_precedence_blocks_even_if_department_teacher_available(self):
        period = make_period('P2026GEN8')
        class_teacher = User.objects.create_user(
            username='teacher_cls_g8',
            email='teacher_cls_g8@test.com',
            password='testpass123',
            role='t',
        )
        department_teacher = User.objects.create_user(
            username='teacher_dep_g8',
            email='teacher_dep_g8@test.com',
            password='testpass123',
            role='t',
        )
        department = Department.objects.create(name='Departamento G8', code='DEP-G8', teacher=department_teacher)
        career = Career.objects.create(name='Career G8', code='CAR-G8')
        subject = Subject.objects.create(name='Subject G8', code='SUB-G8', career=career, department=department)
        classroom = Classroom.objects.create(name='Room G8', building='Main', capacity=30, type='lecture')
        Class.objects.create(subject=subject, teacher=class_teacher, period=period, classroom=classroom, max_students=30)
        TimeSlot.objects.create(period=period, day_of_week=1, start_time=time(11, 0), end_time=time(12, 0))
        SchedulingConstraint.objects.create(
            kind='teacher_unavailable',
            scope='period',
            period=period,
            teacher=class_teacher,
            day_of_week=1,
            start_time=time(11, 0),
            end_time=time(12, 0),
            is_active=True,
        )
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        self.assertEqual(run.status, 'failed')
        self.assertEqual(run.assignments.count(), 0)

    def test_generate_reports_unresolved_teachers_when_no_resolution_possible(self):
        period = make_period('P2026GEN9')
        career = Career.objects.create(name='Career G9', code='CAR-G9')
        subject = Subject.objects.create(name='Subject G9', code='SUB-G9', career=career)
        classroom = Classroom.objects.create(name='Room G9', building='Main', capacity=25, type='lecture')
        cls = Class.objects.create(subject=subject, teacher=None, period=period, classroom=classroom, max_students=20)
        TimeSlot.objects.create(period=period, day_of_week=2, start_time=time(10, 0), end_time=time(11, 0))
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        run.refresh_from_db()
        self.assertEqual(run.status, 'failed')
        unresolved = run.metadata['generator'].get('unresolved_teachers', [])
        self.assertEqual(unresolved, [cls.id])
        violation = ConstraintViolation.objects.get(run=run)
        self.assertTrue(violation.metadata.get('unresolved_teacher'))

    def test_generate_uses_subject_hours_per_week_as_weekly_demand(self):
        period = make_period('P2026GEN10')
        cls = make_class(period, 'G10')
        cls.subject.hours_per_week = 3
        cls.subject.save(update_fields=['hours_per_week'])
        TimeSlot.objects.create(period=period, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))
        TimeSlot.objects.create(period=period, day_of_week=2, start_time=time(8, 0), end_time=time(9, 0))
        TimeSlot.objects.create(period=period, day_of_week=4, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        run.refresh_from_db()
        self.assertEqual(run.assignments.filter(cls=cls).count(), 3)
        self.assertEqual(run.metadata['generator']['sessions_requested'], 3)
        self.assertEqual(run.metadata['generator']['generated_assignments'], 3)
        self.assertEqual(run.metadata['generator']['unscheduled_sessions'], 0)

    def test_generate_never_repeats_same_class_on_same_day(self):
        period = make_period('P2026GEN11')
        cls = make_class(period, 'G11')
        cls.subject.hours_per_week = 3
        cls.subject.save(update_fields=['hours_per_week'])
        TimeSlot.objects.create(period=period, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))
        TimeSlot.objects.create(period=period, day_of_week=0, start_time=time(9, 0), end_time=time(10, 0))
        TimeSlot.objects.create(period=period, day_of_week=2, start_time=time(8, 0), end_time=time(9, 0))
        TimeSlot.objects.create(period=period, day_of_week=4, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        run.refresh_from_db()
        assignments = list(run.assignments.filter(cls=cls).select_related('slot').order_by('slot__day_of_week', 'slot__start_time'))
        self.assertEqual(len(assignments), 3)
        self.assertEqual(len({a.slot.day_of_week for a in assignments}), 3)

    def test_generate_keeps_teacher_consistent_for_class_across_sessions(self):
        period = make_period('P2026GEN12')
        class_teacher = User.objects.create_user(
            username='teacher_cls_g12',
            email='teacher_cls_g12@test.com',
            password='testpass123',
            role='t',
        )
        department_teacher = User.objects.create_user(
            username='teacher_dep_g12',
            email='teacher_dep_g12@test.com',
            password='testpass123',
            role='t',
        )
        department = Department.objects.create(name='Departamento G12', code='DEP-G12', teacher=department_teacher)
        career = Career.objects.create(name='Career G12', code='CAR-G12')
        subject = Subject.objects.create(name='Subject G12', code='SUB-G12', career=career, department=department, hours_per_week=2)
        classroom = Classroom.objects.create(name='Room G12', building='Main', capacity=30, type='lecture')
        cls = Class.objects.create(subject=subject, teacher=class_teacher, period=period, classroom=classroom, max_students=30)
        TimeSlot.objects.create(period=period, day_of_week=1, start_time=time(8, 0), end_time=time(9, 0))
        TimeSlot.objects.create(period=period, day_of_week=3, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        run.refresh_from_db()
        teacher_ids = set(run.assignments.filter(cls=cls).values_list('teacher_id', flat=True))
        self.assertEqual(teacher_ids, {class_teacher.id})

    def test_generate_reports_partial_when_hours_exceed_distinct_days(self):
        period = make_period('P2026GEN13')
        cls = make_class(period, 'G13')
        cls.subject.hours_per_week = 4
        cls.subject.save(update_fields=['hours_per_week'])
        TimeSlot.objects.create(period=period, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))
        TimeSlot.objects.create(period=period, day_of_week=2, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        run.refresh_from_db()
        self.assertEqual(run.status, 'partial')
        self.assertEqual(run.assignments.filter(cls=cls).count(), 2)
        self.assertEqual(run.metadata['generator']['sessions_requested'], 4)
        self.assertEqual(run.metadata['generator']['unscheduled_sessions'], 2)
        self.assertEqual(run.metadata['generator']['warning_summary']['hard_violations'], 2)
        self.assertTrue(run.metadata['generator']['warning_summary']['blocks_publish'])

    def test_allows_multiple_assignments_same_run_and_class_different_slots(self):
        period = make_period('P2026SAC1')
        cls = make_class(period, 'SAC1')
        slot_a = TimeSlot.objects.create(period=period, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))
        slot_b = TimeSlot.objects.create(period=period, day_of_week=2, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period)

        ScheduleAssignment.objects.create(run=run, cls=cls, slot=slot_a, classroom=cls.classroom, teacher=cls.teacher)
        ScheduleAssignment.objects.create(run=run, cls=cls, slot=slot_b, classroom=cls.classroom, teacher=cls.teacher)

        self.assertEqual(ScheduleAssignment.objects.filter(run=run, cls=cls).count(), 2)

    def test_rejects_duplicate_assignment_same_run_class_and_slot(self):
        period = make_period('P2026SAC2')
        cls = make_class(period, 'SAC2')
        slot = TimeSlot.objects.create(period=period, day_of_week=1, start_time=time(9, 0), end_time=time(10, 0))
        run = TimetableRun.objects.create(period=period)

        ScheduleAssignment.objects.create(run=run, cls=cls, slot=slot, classroom=cls.classroom, teacher=cls.teacher)

        with self.assertRaises(IntegrityError):
            ScheduleAssignment.objects.create(run=run, cls=cls, slot=slot, classroom=cls.classroom, teacher=cls.teacher)

    def test_publish_rejects_failed_run(self):
        period = make_period('P2026PUB1')
        run = TimetableRun.objects.create(period=period, status='failed')

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/publish/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_publish_demotes_previous_published_run_in_same_period(self):
        period = make_period('P2026PUB2')
        previous = TimetableRun.objects.create(period=period, status='published')
        current = TimetableRun.objects.create(period=period, status='completed')

        response = self.client.post(f'/api/academic/timetable-runs/{current.id}/publish/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        previous.refresh_from_db()
        current.refresh_from_db()
        self.assertEqual(current.status, 'published')
        self.assertEqual(previous.status, 'completed')
        self.assertEqual(TimetableRun.objects.filter(period=period, status='published').count(), 1)

    def test_publish_blocks_runs_with_hard_infringements(self):
        period = make_period('P2026PUB3')
        cls = make_class(period, 'PUB3')
        slot = TimeSlot.objects.create(period=period, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period, status='completed', metadata={'generator': {'warning_summary': {'hard_violations': 1, 'soft_violations': 0, 'precondition_errors': [], 'class_preparation_errors': [], 'unresolved_teachers': [], 'blocks_publish': True, 'blocking_reasons': ['hard_violations']}}})
        assignment = ScheduleAssignment.objects.create(run=run, cls=cls, slot=slot, classroom=cls.classroom, teacher=cls.teacher)
        ConstraintViolation.objects.create(run=run, assignment=assignment, severity='hard', reason='Hard infringement', metadata={'code': 'teacher_conflict'})

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/publish/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('warning_summary', response.data)
        self.assertEqual(response.data['warning_summary']['hard_violations'], 1)

    def test_publish_allows_soft_only_warnings(self):
        period = make_period('P2026PUB4')
        cls = make_class(period, 'PUB4')
        slot = TimeSlot.objects.create(period=period, day_of_week=1, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period, status='completed', metadata={'generator': {'warning_summary': {'hard_violations': 0, 'soft_violations': 1, 'precondition_errors': [], 'class_preparation_errors': [], 'unresolved_teachers': [], 'blocks_publish': False, 'blocking_reasons': []}}})
        assignment = ScheduleAssignment.objects.create(run=run, cls=cls, slot=slot, classroom=cls.classroom, teacher=cls.teacher)
        ConstraintViolation.objects.create(run=run, assignment=assignment, severity='soft', reason='Soft infringement', metadata={'code': 'preference_miss'})

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/publish/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        run.refresh_from_db()
        self.assertEqual(run.status, 'published')
        self.assertEqual(response.data['warning_summary']['soft_violations'], 1)

    def test_delete_allows_non_published_statuses(self):
        period = make_period('P2026DEL1')
        for idx, run_status in enumerate(['draft', 'failed', 'partial', 'completed']):
            run = TimetableRun.objects.create(period=period, status=run_status)

            response = self.client.delete(f'/api/academic/timetable-runs/{run.id}/')

            self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, msg=f'estado {run_status} debería poder eliminarse')
            self.assertFalse(TimetableRun.objects.filter(id=run.id).exists())

    def test_delete_blocks_published_status(self):
        period = make_period('P2026DEL2')
        run = TimetableRun.objects.create(period=period, status='published')

        response = self.client.delete(f'/api/academic/timetable-runs/{run.id}/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        self.assertIn('publicada', str(response.data['detail']).lower())
        self.assertTrue(TimetableRun.objects.filter(id=run.id).exists())


class TimetableCleanupTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.student = make_student('student_cleanup')

    @override_settings(DEBUG=True)
    def test_cleanup_requires_admin_or_management(self):
        period = make_period('P2026CLN1')
        self.client.force_authenticate(user=self.student)

        response = self.client.post('/api/academic/timetable-runs/cleanup/generated-classes/', {'period': period.id})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(DEBUG=False)
    def test_cleanup_is_blocked_outside_debug(self):
        period = make_period('P2026CLN2')
        self.client.force_authenticate(user=self.admin)

        response = self.client.post('/api/academic/timetable-runs/cleanup/generated-classes/', {'period': period.id})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(DEBUG=True)
    def test_cleanup_deletes_only_generated_classes_for_period_and_cascades(self):
        period_a = make_period('P2026CLN3A')
        period_b = make_period('P2026CLN3B')
        generated_a = make_class(period_a, 'CLN3GA')
        generated_a.is_generated_by_timetable = True
        generated_a.save(update_fields=['is_generated_by_timetable'])
        manual_a = make_class(period_a, 'CLN3MA')
        manual_a.is_generated_by_timetable = False
        manual_a.save(update_fields=['is_generated_by_timetable'])
        generated_b = make_class(period_b, 'CLN3GB')
        generated_b.is_generated_by_timetable = True
        generated_b.save(update_fields=['is_generated_by_timetable'])

        slot_a = TimeSlot.objects.create(period=period_a, day_of_week=1, start_time=time(9, 0), end_time=time(10, 0))
        run_a = TimetableRun.objects.create(period=period_a, status='published')
        assignment = ScheduleAssignment.objects.create(
            run=run_a,
            cls=generated_a,
            slot=slot_a,
            classroom=generated_a.classroom,
            teacher=generated_a.teacher,
        )
        ClassSchedule.objects.create(cls=generated_a, day_of_week=1, start_time=time(11, 0), end_time=time(12, 0))
        ConstraintViolation.objects.create(run=run_a, assignment=assignment, severity='hard', reason='cleanup')

        self.client.force_authenticate(user=self.admin)
        response = self.client.post('/api/academic/timetable-runs/cleanup/generated-classes/', {'period': period_a.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['deleted_classes'], 1)
        self.assertFalse(Class.objects.filter(id=generated_a.id).exists())
        self.assertTrue(Class.objects.filter(id=manual_a.id).exists())
        self.assertTrue(Class.objects.filter(id=generated_b.id).exists())
        self.assertFalse(ClassSchedule.objects.filter(cls_id=generated_a.id).exists())
        self.assertFalse(ScheduleAssignment.objects.filter(id=assignment.id).exists())
        self.assertFalse(ConstraintViolation.objects.filter(run=run_a).exists())


class TimetableFilteringTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = make_manager('mgr_filters')
        self.client.force_authenticate(user=self.manager)

    def test_runs_support_period_and_status_filters(self):
        period_a = make_period('P2026FR1')
        period_b = make_period('P2026FR2')
        TimetableRun.objects.create(period=period_a, status='published')
        TimetableRun.objects.create(period=period_a, status='completed')
        TimetableRun.objects.create(period=period_b, status='published')

        response = self.client.get('/api/academic/timetable-runs/', {
            'period': period_a.id,
            'status': 'published',
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = unwrap_results(response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['period'], period_a.id)
        self.assertEqual(results[0]['status'], 'published')

    def test_assignments_support_run_period_and_class_filters(self):
        period = make_period('P2026FA1')
        cls_a = make_class(period, 'FA')
        cls_b = make_class(period, 'FB')
        slot = TimeSlot.objects.create(period=period, day_of_week=1, start_time=time(9, 0), end_time=time(10, 0))
        run = TimetableRun.objects.create(period=period, status='published')
        ScheduleAssignment.objects.create(run=run, cls=cls_a, slot=slot, classroom=cls_a.classroom, teacher=cls_a.teacher)
        ScheduleAssignment.objects.create(run=run, cls=cls_b, slot=slot, classroom=cls_b.classroom, teacher=cls_b.teacher)

        response = self.client.get('/api/academic/schedule-assignments/', {
            'run': run.id,
            'period': period.id,
            'cls': cls_b.id,
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = unwrap_results(response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['cls'], cls_b.id)

    def test_assignments_include_display_fields_and_keep_ids(self):
        period = make_period('P2026FA2')
        cls = make_class(period, 'FC')
        slot = TimeSlot.objects.create(period=period, day_of_week=3, start_time=time(13, 0), end_time=time(14, 0))
        run = TimetableRun.objects.create(period=period, status='completed')
        assignment = ScheduleAssignment.objects.create(
            run=run,
            cls=cls,
            slot=slot,
            classroom=cls.classroom,
            teacher=cls.teacher,
        )

        response = self.client.get('/api/academic/schedule-assignments/', {'run': run.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = unwrap_results(response.data)
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertEqual(row['id'], assignment.id)
        self.assertEqual(row['run'], run.id)
        self.assertEqual(row['cls'], cls.id)
        self.assertEqual(row['slot'], slot.id)
        self.assertEqual(row['classroom'], cls.classroom_id)
        self.assertEqual(row['teacher'], cls.teacher_id)
        self.assertEqual(row['subject_name'], cls.subject.name)
        self.assertEqual(row['subject_code'], cls.subject.code)
        self.assertTrue(row['teacher_name'])
        self.assertEqual(row['classroom_name'], cls.classroom.name)
        self.assertEqual(row['timeslot_day_name'], slot.get_day_of_week_display())
        self.assertEqual(row['timeslot_start_time'], '13:00:00')
        self.assertEqual(row['timeslot_end_time'], '14:00:00')

    def test_assignments_return_null_display_fields_when_relations_missing(self):
        period = make_period('P2026FA3')
        cls = make_class(period, 'FD')
        slot = TimeSlot.objects.create(period=period, day_of_week=4, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period, status='completed')
        ScheduleAssignment.objects.create(run=run, cls=cls, slot=slot, classroom=None, teacher=None)

        response = self.client.get('/api/academic/schedule-assignments/', {'run': run.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = unwrap_results(response.data)
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertIsNone(row['teacher'])
        self.assertIsNone(row['classroom'])
        self.assertIsNone(row['teacher_name'])
        self.assertIsNone(row['classroom_name'])
        self.assertEqual(row['subject_name'], cls.subject.name)
        self.assertEqual(row['subject_code'], cls.subject.code)

    def test_assignments_run_filter_returns_full_dataset_without_pagination_cut(self):
        period = make_period('P2026FA4')
        slot = TimeSlot.objects.create(period=period, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))
        run = TimetableRun.objects.create(period=period, status='completed')

        for index in range(25):
            cls = make_class(period, f'FALL{index}')
            ScheduleAssignment.objects.create(
                run=run,
                cls=cls,
                slot=slot,
                classroom=cls.classroom,
                teacher=cls.teacher,
            )

        response = self.client.get('/api/academic/schedule-assignments/', {'run': run.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 25)

    def test_assignments_career_filter_returns_all_matching_rows_without_pagination_cut(self):
        period = make_period('P2026FA5')
        slot = TimeSlot.objects.create(period=period, day_of_week=1, start_time=time(10, 0), end_time=time(11, 0))
        run = TimetableRun.objects.create(period=period, status='completed')
        target_career = Career.objects.create(name='Career Target FA5', code='CAR-FA5-T')

        for index in range(24):
            subject = Subject.objects.create(
                name=f'Subject Target {index}',
                code=f'SUB-FA5-T-{index}',
                career=target_career,
            )
            teacher = User.objects.create_user(
                username=f'teacher_fa5_target_{index}',
                email=f'teacher_fa5_target_{index}@test.com',
                password='testpass123',
                role='t',
            )
            classroom = Classroom.objects.create(
                name=f'Room FA5 T{index}',
                building='Main',
                capacity=40,
                type='lecture',
            )
            cls = Class.objects.create(
                subject=subject,
                teacher=teacher,
                period=period,
                classroom=classroom,
                max_students=30,
            )
            ScheduleAssignment.objects.create(run=run, cls=cls, slot=slot, classroom=classroom, teacher=teacher)

        for index in range(4):
            cls = make_class(period, f'FA5O{index}')
            ScheduleAssignment.objects.create(run=run, cls=cls, slot=slot, classroom=cls.classroom, teacher=cls.teacher)

        response = self.client.get('/api/academic/schedule-assignments/', {
            'run': run.id,
            'career': target_career.id,
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 24)
        self.assertTrue(all(row['career_id'] == target_career.id for row in response.data))

    def test_violations_support_run_assignment_and_severity_filters(self):
        period = make_period('P2026FV1')
        cls = make_class(period, 'FV')
        slot = TimeSlot.objects.create(period=period, day_of_week=2, start_time=time(11, 0), end_time=time(12, 0))
        run = TimetableRun.objects.create(period=period, status='partial')
        assignment = ScheduleAssignment.objects.create(
            run=run,
            cls=cls,
            slot=slot,
            classroom=cls.classroom,
            teacher=cls.teacher,
        )
        ConstraintViolation.objects.create(run=run, assignment=assignment, severity='hard', reason='Teacher conflict')
        ConstraintViolation.objects.create(run=run, assignment=assignment, severity='soft', reason='Preference miss')

        response = self.client.get('/api/academic/constraint-violations/', {
            'run': run.id,
            'assignment': assignment.id,
            'severity': 'hard',
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = unwrap_results(response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['severity'], 'hard')


class MyScheduleCompatibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = make_student()
        self.period = make_period('P2026MS1')
        self.cls = make_class(self.period, 'MS1')
        ClassEnrollment.objects.create(student=self.student, cls=self.cls, status='enrolled')

    def test_my_schedule_prefers_generated_assignments_when_published(self):
        TimeSlot.objects.create(period=self.period, day_of_week=3, start_time=time(14, 0), end_time=time(15, 0))
        slot = TimeSlot.objects.get(period=self.period)
        run = TimetableRun.objects.create(period=self.period, status='published')
        assignment = ScheduleAssignment.objects.create(
            run=run,
            cls=self.cls,
            slot=slot,
            classroom=self.cls.classroom,
            teacher=self.cls.teacher,
        )

        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/academic/classes/my-schedule/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row['source'], 'generated')
        self.assertEqual(row['assignment_id'], assignment.id)
        self.assertEqual(row['class_id'], self.cls.id)

    def test_my_classes_returns_empty_without_active_period(self):
        self.period.is_active = False
        self.period.save(update_fields=['is_active'])

        self.client.force_authenticate(user=self.cls.teacher)
        response = self.client.get('/api/academic/classes/my-classes/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_my_schedule_falls_back_to_latest_available_student_period(self):
        inactive_period = AcademicPeriod.objects.create(
            name='Period P2026MS0',
            code='P2026MS0',
            start_date='2026-01-01',
            end_date='2026-06-30',
            is_active=False,
        )
        newer_inactive_period = AcademicPeriod.objects.create(
            name='Period P2026MS2',
            code='P2026MS2',
            start_date='2026-02-01',
            end_date='2026-07-31',
            is_active=False,
        )
        inactive_class = make_class(inactive_period, 'MS0')
        fallback_class = make_class(newer_inactive_period, 'MS2')
        ClassEnrollment.objects.create(student=self.student, cls=inactive_class, status='enrolled')
        ClassEnrollment.objects.create(student=self.student, cls=fallback_class, status='enrolled')
        ClassSchedule.objects.create(
            cls=fallback_class,
            day_of_week=1,
            start_time=time(9, 0),
            end_time=time(10, 0),
        )
        self.period.is_active = False
        self.period.save(update_fields=['is_active'])

        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/academic/classes/my-schedule/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['class_id'], fallback_class.id)
        self.assertEqual(response.data[0]['period_name'], newer_inactive_period.name)

    def test_my_schedule_falls_back_to_legacy_class_schedule(self):
        ClassSchedule.objects.create(
            cls=self.cls,
            day_of_week=4,
            start_time=time(8, 0),
            end_time=time(9, 30),
        )

        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/academic/classes/my-schedule/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual(row['source'], 'legacy')
        self.assertEqual(row['class_id'], self.cls.id)
        self.assertIsNone(row['assignment_id'])

    def test_my_schedule_returns_all_generated_sessions_for_same_class(self):
        slot_a = TimeSlot.objects.create(period=self.period, day_of_week=1, start_time=time(10, 0), end_time=time(11, 0))
        slot_b = TimeSlot.objects.create(period=self.period, day_of_week=3, start_time=time(10, 0), end_time=time(11, 0))
        run = TimetableRun.objects.create(period=self.period, status='published')
        assignment_a = ScheduleAssignment.objects.create(
            run=run,
            cls=self.cls,
            slot=slot_a,
            classroom=self.cls.classroom,
            teacher=self.cls.teacher,
        )
        assignment_b = ScheduleAssignment.objects.create(
            run=run,
            cls=self.cls,
            slot=slot_b,
            classroom=self.cls.classroom,
            teacher=self.cls.teacher,
        )

        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/academic/classes/my-schedule/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        assignment_ids = {row['assignment_id'] for row in response.data}
        self.assertEqual(assignment_ids, {assignment_a.id, assignment_b.id})
        self.assertTrue(all(row['source'] == 'generated' for row in response.data))

    def test_my_schedule_teacher_branch_falls_back_without_active_period(self):
        fallback_period = AcademicPeriod.objects.create(
            name='Period P2026MS3',
            code='P2026MS3',
            start_date='2026-02-01',
            end_date='2026-07-31',
            is_active=False,
        )
        fallback_class = make_class(fallback_period, 'MS3')
        fallback_class.teacher = self.cls.teacher
        fallback_class.save(update_fields=['teacher'])
        ClassSchedule.objects.create(
            cls=fallback_class,
            day_of_week=2,
            start_time=time(11, 0),
            end_time=time(12, 0),
        )

        self.period.is_active = False
        self.period.save(update_fields=['is_active'])

        self.client.force_authenticate(user=self.cls.teacher)
        response = self.client.get('/api/academic/classes/my-schedule/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['class_id'], fallback_class.id)
        self.assertEqual(response.data[0]['period_name'], fallback_period.name)

    def test_my_schedule_prefers_persisted_class_teacher_over_assignment_teacher(self):
        persisted_teacher = User.objects.create_user(
            username='teacher_persisted_ms',
            email='teacher_persisted_ms@test.com',
            password='testpass123',
            role='t',
        )
        assignment_teacher = User.objects.create_user(
            username='teacher_assignment_ms',
            email='teacher_assignment_ms@test.com',
            password='testpass123',
            role='t',
        )
        run = TimetableRun.objects.create(period=self.period, status='published')
        slot = TimeSlot.objects.create(period=self.period, day_of_week=2, start_time=time(12, 0), end_time=time(13, 0))
        self.cls.teacher = persisted_teacher
        self.cls.save(update_fields=['teacher'])
        ScheduleAssignment.objects.create(
            run=run,
            cls=self.cls,
            slot=slot,
            classroom=self.cls.classroom,
            teacher=assignment_teacher,
        )

        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/academic/classes/my-schedule/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['teacher_name'], f'{persisted_teacher.first_name} {persisted_teacher.last_name}'.strip() or persisted_teacher.username)


class GeneratedTeacherBackfillTests(TestCase):
    def test_backfill_populates_only_unambiguous_generated_classes_and_is_idempotent(self):
        period = make_period('P2026BF1')
        career = Career.objects.create(name='Career BF', code='CAR-BF')
        teacher = User.objects.create_user(username='teacher_bf1', email='teacher_bf1@test.com', password='testpass123', role='t')
        teacher2 = User.objects.create_user(username='teacher_bf2', email='teacher_bf2@test.com', password='testpass123', role='t')
        classroom = Classroom.objects.create(name='Room BF', building='Main', capacity=40, type='lecture')
        classroom2 = Classroom.objects.create(name='Room BF2', building='Main', capacity=40, type='lecture')
        subject1 = Subject.objects.create(name='Subject BF1', code='SUB-BF1', career=career, hours_per_week=1)
        subject2 = Subject.objects.create(name='Subject BF2', code='SUB-BF2', career=career, hours_per_week=1)
        subject3 = Subject.objects.create(name='Subject BF3', code='SUB-BF3', career=career, hours_per_week=1)
        cls_backfill = Class.objects.create(subject=subject1, teacher=None, period=period, classroom=classroom, max_students=30, is_generated_by_timetable=True)
        cls_ambiguous = Class.objects.create(subject=subject2, teacher=None, period=period, classroom=classroom, max_students=30, is_generated_by_timetable=True)
        cls_existing = Class.objects.create(subject=subject3, teacher=teacher2, period=period, classroom=classroom2, max_students=30, is_generated_by_timetable=True)
        run = TimetableRun.objects.create(period=period, status='published')
        slot_a = TimeSlot.objects.create(period=period, day_of_week=1, start_time=time(8, 0), end_time=time(9, 0))
        slot_b = TimeSlot.objects.create(period=period, day_of_week=2, start_time=time(8, 0), end_time=time(9, 0))
        ScheduleAssignment.objects.create(run=run, cls=cls_backfill, slot=slot_a, classroom=classroom, teacher=teacher)
        ScheduleAssignment.objects.create(run=run, cls=cls_ambiguous, slot=slot_b, classroom=classroom, teacher=teacher)
        ScheduleAssignment.objects.create(run=run, cls=cls_ambiguous, slot=slot_a, classroom=classroom2, teacher=teacher2)
        ScheduleAssignment.objects.create(run=run, cls=cls_existing, slot=slot_b, classroom=classroom2, teacher=teacher2)

        first_result = backfill_generated_class_teachers()
        second_result = backfill_generated_class_teachers()

        cls_backfill.refresh_from_db()
        cls_ambiguous.refresh_from_db()
        cls_existing.refresh_from_db()

        self.assertEqual(first_result['updated'], 1)
        self.assertEqual(first_result['skipped_ambiguous'], 1)
        self.assertEqual(first_result['skipped_existing_teacher'], 1)
        self.assertEqual(first_result['skipped_empty'], 0)
        self.assertEqual(second_result['updated'], 0)
        self.assertEqual(cls_backfill.teacher_id, teacher.id)
        self.assertIsNone(cls_ambiguous.teacher_id)
        self.assertEqual(cls_existing.teacher_id, teacher2.id)


class CareerClassesCanonicalScheduleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = make_student('student_ccs')
        self.client.force_authenticate(user=self.student)
        self.period = make_period('P2026CCS1')
        self.career = Career.objects.create(name='Career Canon', code='CCAN')
        self.subject = Subject.objects.create(name='Subject Canon', code='SCAN', career=self.career)
        self.teacher = User.objects.create_user(
            username='teacher_ccs',
            email='teacher_ccs@test.com',
            password='testpass123',
            role='t',
        )
        self.classroom = Classroom.objects.create(name='Room Canon', building='Main', capacity=40, type='lecture')
        self.cls = Class.objects.create(
            subject=self.subject,
            teacher=self.teacher,
            period=self.period,
            classroom=self.classroom,
            max_students=30,
        )

    def test_classes_endpoint_uses_published_assignment_and_contract_fields(self):
        ClassSchedule.objects.create(cls=self.cls, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))
        slot = TimeSlot.objects.create(period=self.period, day_of_week=2, start_time=time(13, 0), end_time=time(14, 0))
        run = TimetableRun.objects.create(period=self.period, status='published')
        assignment = ScheduleAssignment.objects.create(
            run=run,
            cls=self.cls,
            slot=slot,
            classroom=self.classroom,
            teacher=self.teacher,
        )

        response = self.client.get(f'/api/academic/careers/{self.career.id}/classes/', {'period': self.period.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data[0]
        self.assertEqual(row['schedule_source'], 'generated')
        self.assertTrue(row['schedule_available'])
        self.assertIsNone(row['schedule_unavailable_reason'])
        self.assertEqual(len(row['schedules']), 1)
        self.assertEqual(row['schedules'][0]['assignment_id'], assignment.id)
        self.assertEqual(row['schedules'][0]['source'], 'generated')
        self.assertEqual(row['schedules'][0]['day_name'], slot.get_day_of_week_display())

    def test_classes_endpoint_marks_unavailable_when_no_published_assignment(self):
        ClassSchedule.objects.create(cls=self.cls, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))

        response = self.client.get(f'/api/academic/careers/{self.career.id}/classes/', {'period': self.period.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data[0]
        self.assertEqual(row['schedule_source'], 'generated')
        self.assertFalse(row['schedule_available'])
        self.assertEqual(row['schedule_unavailable_reason'], 'schedule_unavailable')
        self.assertEqual(row['schedules'], [])

    def test_classes_endpoint_returns_multiple_published_schedules_for_class(self):
        slot_a = TimeSlot.objects.create(period=self.period, day_of_week=1, start_time=time(9, 0), end_time=time(10, 0))
        slot_b = TimeSlot.objects.create(period=self.period, day_of_week=3, start_time=time(9, 0), end_time=time(10, 0))
        run = TimetableRun.objects.create(period=self.period, status='published')
        assignment_a = ScheduleAssignment.objects.create(
            run=run,
            cls=self.cls,
            slot=slot_a,
            classroom=self.classroom,
            teacher=self.teacher,
        )
        assignment_b = ScheduleAssignment.objects.create(
            run=run,
            cls=self.cls,
            slot=slot_b,
            classroom=self.classroom,
            teacher=self.teacher,
        )

        response = self.client.get(f'/api/academic/careers/{self.career.id}/classes/', {'period': self.period.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data[0]
        self.assertTrue(row['schedule_available'])
        self.assertEqual(len(row['schedules']), 2)
        assignment_ids = {s['assignment_id'] for s in row['schedules']}
        self.assertEqual(assignment_ids, {assignment_a.id, assignment_b.id})


class SchedulingConstraintsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = make_manager('mgr_constraints')
        self.client.force_authenticate(user=self.manager)
        self.period = make_period('P2026SC1')
        self.cls = make_class(self.period, 'SC1')
        self.slot = TimeSlot.objects.create(period=self.period, day_of_week=0, start_time=time(8, 0), end_time=time(9, 0))

    def test_constraints_crud_validation_and_list(self):
        invalid = self.client.post('/api/academic/scheduling-constraints/', {
            'kind': 'teacher_unavailable', 'scope': 'period', 'period': self.period.id, 'day_of_week': 0, 'start_time': '10:00:00', 'end_time': '09:00:00', 'is_active': True,
        }, format='json')
        self.assertEqual(invalid.status_code, 400)
        self.assertIn('end_time', invalid.data)

        valid = self.client.post('/api/academic/scheduling-constraints/', {
            'kind': 'teacher_unavailable', 'scope': 'period', 'period': self.period.id, 'teacher': self.cls.teacher_id, 'day_of_week': 0, 'start_time': '08:00:00', 'end_time': '10:00:00', 'is_active': True,
        }, format='json')
        self.assertEqual(valid.status_code, 201)
        self.assertEqual(SchedulingConstraint.objects.count(), 1)

        row = valid.data
        self.assertEqual(row['kind'], 'teacher_unavailable')
        self.assertEqual(row['scope'], 'period')
        self.assertEqual(row['day_of_week'], 0)
        self.assertEqual(row['kind_label'], 'Docente no disponible')
        self.assertEqual(row['scope_label'], 'Periodo')
        self.assertEqual(row['day_label'], 'Lunes')
        self.assertEqual(row['period_name'], self.period.name)
        self.assertTrue(row['teacher_name'])
        self.assertIsNone(row['classroom_name'])
        self.assertIsNone(row['career_name'])

    def test_constraints_labels_use_neutral_placeholders_for_unknown_or_missing(self):
        constraint = SchedulingConstraint.objects.create(
            kind='teacher_unavailable',
            scope='period',
            period=self.period,
            teacher=self.cls.teacher,
            day_of_week=1,
            start_time=time(8, 0),
            end_time=time(9, 0),
            is_active=True,
        )
        SchedulingConstraint.objects.filter(id=constraint.id).update(kind='unknown_kind', scope='unknown_scope', day_of_week=9)

        response = self.client.get('/api/academic/scheduling-constraints/', {'is_active': 'true'})
        self.assertEqual(response.status_code, 200)
        row = unwrap_results(response.data)[0]

        self.assertEqual(row['kind'], 'unknown_kind')
        self.assertEqual(row['scope'], 'unknown_scope')
        self.assertEqual(row['day_of_week'], 9)
        self.assertEqual(row['kind_label'], 'Tipo no especificado')
        self.assertEqual(row['scope_label'], 'Alcance no especificado')
        self.assertEqual(row['day_label'], 'Día no especificado')

    def test_assignments_include_career_fields_and_filter(self):
        run = TimetableRun.objects.create(period=self.period, status='completed')
        ScheduleAssignment.objects.create(run=run, cls=self.cls, slot=self.slot, classroom=self.cls.classroom, teacher=self.cls.teacher)

        response = self.client.get('/api/academic/schedule-assignments/', {'run': run.id, 'career': self.cls.subject.career_id})
        self.assertEqual(response.status_code, 200)
        row = unwrap_results(response.data)[0]
        self.assertEqual(row['career_id'], self.cls.subject.career_id)
        self.assertEqual(row['career_code'], self.cls.subject.career.code)
        self.assertEqual(row['career_name'], self.cls.subject.career.name)

    def test_schedule_assignments_filter_includes_shared_career_relations(self):
        shared_career = Career.objects.create(name='Shared Career', code='CAR-SHARED')
        self.cls.subject.careers.add(shared_career)
        run = TimetableRun.objects.create(period=self.period, status='completed')
        ScheduleAssignment.objects.create(run=run, cls=self.cls, slot=self.slot, classroom=self.cls.classroom, teacher=self.cls.teacher)

        response = self.client.get('/api/academic/schedule-assignments/', {'career': shared_career.id})

        self.assertEqual(response.status_code, 200)
        rows = unwrap_results(response.data)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['cls'], self.cls.id)

    def test_generate_applies_active_constraints_and_registers_violation(self):
        run = TimetableRun.objects.create(period=self.period, status='draft')
        SchedulingConstraint.objects.create(
            kind='teacher_unavailable', scope='period', period=self.period,
            teacher=self.cls.teacher, day_of_week=0, start_time=time(7, 0), end_time=time(11, 0), is_active=True,
        )

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')
        self.assertEqual(response.status_code, 400)
        run.refresh_from_db()
        self.assertIn(run.status, {'partial', 'failed'})
        self.assertEqual(run.assignments.count(), 0)
        self.assertGreaterEqual(run.violations.count(), 1)

    def test_generate_blocks_shared_career_constraints(self):
        shared_career = Career.objects.create(name='Shared Career G', code='CAR-SHARED-G')
        self.cls.subject.careers.add(shared_career)
        run = TimetableRun.objects.create(period=self.period, status='draft')
        SchedulingConstraint.objects.create(
            kind='career_unavailable', scope='period', period=self.period,
            career=shared_career, day_of_week=0, start_time=time(7, 0), end_time=time(11, 0), is_active=True,
        )

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, 400)
        run.refresh_from_db()
        self.assertGreaterEqual(run.violations.count(), 1)

    def test_seeded_dataset_generates_without_unresolved_teachers(self):
        call_command('seed_academic_base')
        period = AcademicPeriod.objects.filter(is_active=True).order_by('-start_date').first()
        self.assertIsNotNone(period)
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, 200)
        run.refresh_from_db()
        self.assertIn(run.status, {'completed', 'partial'})
        unresolved = run.metadata.get('generator', {}).get('unresolved_teachers', [])
        self.assertEqual(unresolved, [])
        self.assertNotIn('class_preparation_insufficient_teachers', run.metadata.get('generator', {}).get('class_preparation_errors', []))


class SeedTestDataTimetableCommandTests(TestCase):
    def setUp(self):
        self.period = AcademicPeriod.objects.create(
            name='Period SP2026CMD',
            code='SP2026CMD',
            start_date='2026-02-01',
            end_date='2026-06-30',
            is_active=True,
        )
        Career.objects.create(name='Ciencias de la Computación', code='CS', is_active=True)
        User.objects.create_user(
            username='teacher01',
            email='teacher01@academix.edu',
            password='testpass123',
            role='t',
        )

    def test_seed_timetable_generate_run_creates_completed_or_partial_run(self):
        stdout = StringIO()
        call_command(
            'seed_test_data',
            profile='timetable',
            period_code='SP2026CMD',
            slots_per_day=1,
            generate_run=True,
            stdout=stdout,
        )

        run = TimetableRun.objects.filter(period=self.period).order_by('-id').first()
        self.assertIsNotNone(run)
        self.assertIn(run.status, {'completed', 'partial'})
        self.assertIn('generator', run.metadata)
