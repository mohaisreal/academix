from datetime import time

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from users.models import User
from academic.models import AcademicPeriod, Career, Subject, Class, ClassSchedule, Classroom, TimeSlot, TimetableRun, ScheduleAssignment
from enrollment.models import CareerEnrollment, ClassEnrollment


def make_student(username='student_cs', email='student_cs@test.com', password='testpass123'):
    user = User.objects.create_user(username=username, email=email, password=password, is_active=True)
    user.role = 's'
    user.save()
    return user


class CanonicalClassEnrollmentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = make_student()
        self.career = Career.objects.create(name='Ingeniería Canon', code='ICAN', duration_years=4, is_active=True)
        self.period = AcademicPeriod.objects.create(
            name='2026-CS',
            code='2026CS',
            is_active=True,
            start_date='2026-03-01',
            end_date='2026-07-31',
        )
        self.classroom = Classroom.objects.create(name='Aula Canon', building='A', capacity=4, type='lecture')
        self.subject_a = Subject.objects.create(name='Materia A', code='MATA', career=self.career, credits=4)
        self.subject_b = Subject.objects.create(name='Materia B', code='MATB', career=self.career, credits=4)

        self.cls_a = Class.objects.create(subject=self.subject_a, period=self.period, classroom=self.classroom, max_students=4)
        self.cls_b = Class.objects.create(subject=self.subject_b, period=self.period, classroom=self.classroom, max_students=4)

        self.slot_a = TimeSlot.objects.create(period=self.period, day_of_week=0, start_time=time(8, 0), end_time=time(10, 0))
        self.slot_overlap = TimeSlot.objects.create(period=self.period, day_of_week=0, start_time=time(9, 0), end_time=time(11, 0))
        self.slot_non_overlap = TimeSlot.objects.create(period=self.period, day_of_week=0, start_time=time(10, 0), end_time=time(12, 0))

        self.run = TimetableRun.objects.create(period=self.period, status='published')

        CareerEnrollment.objects.create(student=self.student, career=self.career, period=self.period, status='active')
        self.client.force_authenticate(user=self.student)

    def _url(self):
        return '/api/enrollment/class-enrollments/'

    def test_rejects_legacy_only_schedule_with_machine_code(self):
        ClassSchedule.objects.create(cls=self.cls_a, day_of_week=0, start_time=time(8, 0), end_time=time(10, 0))

        response = self.client.post(self._url(), {'class_id': self.cls_a.id})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get('code'), 'schedule_unavailable')
        self.assertFalse(ClassEnrollment.objects.filter(student=self.student, cls=self.cls_a).exists())

    def test_accepts_enrollment_when_published_assignment_exists(self):
        ScheduleAssignment.objects.create(run=self.run, cls=self.cls_a, slot=self.slot_a, classroom=self.classroom, teacher=None)

        response = self.client.post(self._url(), {'class_id': self.cls_a.id})

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ClassEnrollment.objects.filter(student=self.student, cls=self.cls_a, status='enrolled').exists())

    def test_conflict_detection_uses_canonical_assignments(self):
        ScheduleAssignment.objects.create(run=self.run, cls=self.cls_a, slot=self.slot_a, classroom=self.classroom, teacher=None)
        ScheduleAssignment.objects.create(run=self.run, cls=self.cls_b, slot=self.slot_overlap, classroom=self.classroom, teacher=None)

        first_response = self.client.post(self._url(), {'class_id': self.cls_a.id})
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        overlap_response = self.client.post(self._url(), {'class_id': self.cls_b.id})
        self.assertEqual(overlap_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Solapamiento', overlap_response.data.get('detail', ''))

        ScheduleAssignment.objects.filter(cls=self.cls_b).delete()
        ScheduleAssignment.objects.create(run=self.run, cls=self.cls_b, slot=self.slot_non_overlap, classroom=self.classroom, teacher=None)
        ok_response = self.client.post(self._url(), {'class_id': self.cls_b.id})
        self.assertEqual(ok_response.status_code, status.HTTP_201_CREATED)
