from datetime import time
from io import StringIO

from django.core.management import call_command
from django.core.exceptions import ValidationError
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
        make_class(period, 'G1')
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
        TimeSlot.objects.create(
            period=period,
            day_of_week=0,
            start_time=time(8, 0),
            end_time=time(9, 0),
        )
        run = TimetableRun.objects.create(period=period)

        response = self.client.post(f'/api/academic/timetable-runs/{run.id}/generate/')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        self.assertIn('clases', str(response.data['detail']).lower())
        run.refresh_from_db()
        self.assertIn('missing_classes', run.metadata['generator'].get('precondition_errors', []))

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

    def test_generate_fails_with_missing_teacher_and_classroom_categories(self):
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
        self.assertIn('missing_teachers', categories)
        self.assertIn('missing_classrooms', categories)

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
        results = response.data.get('results', response.data)
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
        results = response.data.get('results', response.data)
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
        results = response.data.get('results', response.data)
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
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        row = results[0]
        self.assertIsNone(row['teacher'])
        self.assertIsNone(row['classroom'])
        self.assertIsNone(row['teacher_name'])
        self.assertIsNone(row['classroom_name'])
        self.assertEqual(row['subject_name'], cls.subject.name)
        self.assertEqual(row['subject_code'], cls.subject.code)

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
        results = response.data.get('results', response.data)
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
