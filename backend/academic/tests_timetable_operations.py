from datetime import time
from io import StringIO

from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.db import IntegrityError
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
        run.refresh_from_db()
        self.assertEqual(run.status, 'completed')
        self.assertGreater(run.assignments.count(), 0)
        self.assertIn('generator', run.metadata)

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

    def test_assignments_include_career_fields_and_filter(self):
        run = TimetableRun.objects.create(period=self.period, status='completed')
        ScheduleAssignment.objects.create(run=run, cls=self.cls, slot=self.slot, classroom=self.cls.classroom, teacher=self.cls.teacher)

        response = self.client.get('/api/academic/schedule-assignments/', {'run': run.id, 'career': self.cls.subject.career_id})
        self.assertEqual(response.status_code, 200)
        row = unwrap_results(response.data)[0]
        self.assertEqual(row['career_id'], self.cls.subject.career_id)
        self.assertEqual(row['career_code'], self.cls.subject.career.code)
        self.assertEqual(row['career_name'], self.cls.subject.career.name)

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
