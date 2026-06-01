from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User
from academic.models import Career, AcademicPeriod, Subject, Class, ClassSchedule, Classroom, TimeSlot, TimetableRun, ScheduleAssignment
from enrollment.models import CareerEnrollment, ClassEnrollment, EnrollmentFee
from admissions.models import AdmissionApplication


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def make_student(username='student1', email='student1@test.com', password='testpass123'):
    user = User.objects.create_user(
        username=username, email=email, password=password, is_active=True,
    )
    user.role = 's'
    user.save()
    return user


def make_manager(username='manager1', email='manager1@test.com', password='testpass123'):
    user = User.objects.create_user(
        username=username, email=email, password=password, is_active=True,
    )
    user.role = 'm'
    user.save()
    return user


# ---------------------------------------------------------------------------
# Pruebas de CareerEnrollment
# ---------------------------------------------------------------------------

class CareerEnrollmentTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.student = make_student()
        self.manager = make_manager()

        self.career = Career.objects.create(
            name='Ingeniería Test', code='ITEST', duration_years=4, is_active=True,
        )
        self.period = AcademicPeriod.objects.create(
            name='2026-Test', code='2026T', is_active=True,
            start_date='2026-03-01', end_date='2026-07-31',
        )

        # Admisión confirmada para el estudiante principal
        self.confirmed_app = AdmissionApplication.objects.create(
            student=self.student,
            career=self.career,
            academic_period=self.period,
            status='confirmed',
        )

    def _enroll_url(self):
        return '/api/enrollment/career-enrollments/'

    # --- Prueba 1: caso correcto ---------------------------------------------------

    def test_student_can_create_enrollment_with_confirmed_admission(self):
        """Un estudiante con admisión confirmada puede matricularse."""
        self.client.force_authenticate(user=self.student)
        response = self.client.post(self._enroll_url(), {
            'career_id': self.career.pk,
            'period_id': self.period.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'pending')
        # El arancel se calcula después de elegir asignaturas, no al crear matrícula
        enrollment = CareerEnrollment.objects.get(
            student=self.student, career=self.career, period=self.period,
        )
        self.assertFalse(EnrollmentFee.objects.filter(career_enrollment=enrollment).exists())

    # --- Prueba 2: sin admisión → 403 ------------------------------------------

    def test_student_cannot_enroll_without_admission(self):
        """Un estudiante sin admisión confirmada recibe 403."""
        other_student = make_student(username='student_no_adm', email='no_adm@test.com')
        self.client.force_authenticate(user=other_student)
        response = self.client.post(self._enroll_url(), {
            'career_id': self.career.pk,
            'period_id': self.period.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Prueba 3: doble matrícula → 400 ----------------------------------------

    def test_student_cannot_enroll_twice(self):
        """Un estudiante no puede matricularse dos veces en la misma carrera/periodo."""
        # Primera matrícula manual
        CareerEnrollment.objects.create(
            student=self.student, career=self.career, period=self.period, status='pending',
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.post(self._enroll_url(), {
            'career_id': self.career.pk,
            'period_id': self.period.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Prueba 4: estudiante ve solo las suyas --------------------------------

    def test_student_can_view_own_enrollments(self):
        """GET devuelve solo las matrículas del estudiante autenticado."""
        # Matrícula propia
        CareerEnrollment.objects.create(
            student=self.student, career=self.career, period=self.period, status='pending',
        )
        # Otra carrera, otro estudiante
        other_student = make_student(username='student_other', email='other@test.com')
        career2 = Career.objects.create(name='Medicina', code='MED', duration_years=6)
        CareerEnrollment.objects.create(
            student=other_student, career=career2, period=self.period, status='pending',
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self._enroll_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data if isinstance(response.data, list) else response.data.get('results', response.data)
        # Solo debe ver la suya
        ids = [r['id'] for r in results]
        enrollments_of_student = list(
            CareerEnrollment.objects.filter(student=self.student).values_list('id', flat=True)
        )
        for eid in ids:
            self.assertIn(eid, enrollments_of_student)

    # --- Prueba 5: gestión ve todas -----------------------------------------

    def test_management_can_view_all_enrollments(self):
        """Un usuario de management puede ver todas las matrículas."""
        # Dos estudiantes con matrículas
        other_student = make_student(username='student_m2', email='m2@test.com')
        career2 = Career.objects.create(name='Contaduría', code='CONT', duration_years=5)
        CareerEnrollment.objects.create(
            student=self.student, career=self.career, period=self.period, status='active',
        )
        CareerEnrollment.objects.create(
            student=other_student, career=career2, period=self.period, status='active',
        )
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(self._enroll_url())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data if isinstance(response.data, list) else response.data.get('results', response.data)
        self.assertGreaterEqual(len(results), 2)

    

    # --- Prueba 6: pagar arancel -----------------------------------------------

    def test_student_can_pay_enrollment_fee(self):
        """POST /pay/ cambia fee.status=paid y enrollment.status=active."""
        subject = Subject.objects.create(
            name='Matemáticas I', code='MAT-PAY', career=self.career, credits=4,
        )
        cls = Class.objects.create(subject=subject, period=self.period, max_students=30)
        enrollment = CareerEnrollment.objects.create(
            student=self.student, career=self.career, period=self.period, status='pending',
        )
        ClassEnrollment.objects.create(student=self.student, cls=cls, status='enrolled')
        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/enrollment/career-enrollments/{enrollment.pk}/pay/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['enrollment']['status'], 'active')

        fee = EnrollmentFee.objects.get(career_enrollment=enrollment)
        enrollment.refresh_from_db()
        self.assertEqual(fee.status, 'paid')
        self.assertIsNotNone(fee.paid_at)
        self.assertEqual(enrollment.status, 'active')

    # --- Prueba 7: ya pagado → 400 ---------------------------------------------

    def test_student_cannot_pay_already_paid_fee(self):
        """Intentar pagar un arancel ya pagado devuelve 400."""
        enrollment = CareerEnrollment.objects.create(
            student=self.student, career=self.career, period=self.period, status='active',
        )
        EnrollmentFee.objects.create(
            career_enrollment=enrollment,
            base_amount='800.00',
            discount_amount='0.00',
            final_amount='800.00',
            status='paid',
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.post(f'/api/enrollment/career-enrollments/{enrollment.pk}/pay/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Pruebas de ClassEnrollment
# ---------------------------------------------------------------------------

class ClassEnrollmentTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.student = make_student()

        # Titulación, periodo, aula
        self.career = Career.objects.create(
            name='Ingeniería Test', code='ITEST2', duration_years=4, is_active=True,
        )
        self.period = AcademicPeriod.objects.create(
            name='2026-T2', code='2026T2', is_active=True,
            start_date='2026-03-01', end_date='2026-07-31',
        )
        # Aula con capacidad para 2 (fácil de llenar en pruebas)
        self.classroom = Classroom.objects.create(
            name='Aula 101', building='Edificio A', capacity=2, type='lecture',
        )

        # Asignatura y clase
        self.subject = Subject.objects.create(
            name='Matemáticas I', code='MAT1', career=self.career, credits=4,
        )
        self.cls = Class.objects.create(
            subject=self.subject,
            period=self.period,
            classroom=self.classroom,
            max_students=2,
        )
        # Horario: Lunes 08:00-10:00
        self.schedule = ClassSchedule.objects.create(
            cls=self.cls,
            day_of_week=0, # Lunes
            start_time='08:00',
            end_time='10:00',
        )
        self.slot_a = TimeSlot.objects.create(period=self.period, day_of_week=0, start_time='08:00', end_time='10:00')
        self.slot_b_overlap = TimeSlot.objects.create(period=self.period, day_of_week=0, start_time='09:00', end_time='11:00')
        self.slot_c_no_overlap = TimeSlot.objects.create(period=self.period, day_of_week=0, start_time='10:00', end_time='12:00')
        self.run = TimetableRun.objects.create(period=self.period, status='published')
        ScheduleAssignment.objects.create(run=self.run, cls=self.cls, slot=self.slot_a, classroom=self.classroom, teacher=None)

        # CareerEnrollment activo para el estudiante
        self.career_enrollment = CareerEnrollment.objects.create(
            student=self.student,
            career=self.career,
            period=self.period,
            status='active',
        )

    def _class_enroll_url(self):
        return '/api/enrollment/class-enrollments/'

    def _class_enroll_delete_url(self, pk):
        return f'/api/enrollment/class-enrollments/{pk}/'

    # --- Prueba 8: caso correcto inscripción en clase -----------------------------

    def test_student_can_enroll_in_class_with_active_career_enrollment(self):
        """Un estudiante con matrícula activa puede inscribirse en una clase."""
        self.client.force_authenticate(user=self.student)
        response = self.client.post(self._class_enroll_url(), {
            'class_id': self.cls.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        ce = ClassEnrollment.objects.get(student=self.student, cls=self.cls)
        self.assertEqual(ce.status, 'enrolled')

    # --- Prueba 9: waitlisted cuando clase llena --------------------------------

    def test_student_waitlisted_when_class_full(self):
        """Si la clase está llena, el estudiante queda en waitlist."""
        # Llenar la clase con otros 2 estudiantes
        for i in range(2):
            s = make_student(username=f'filler{i}', email=f'filler{i}@test.com')
            CareerEnrollment.objects.create(
                student=s, career=self.career, period=self.period, status='active',
            )
            ClassEnrollment.objects.create(student=s, cls=self.cls, status='enrolled')

        self.client.force_authenticate(user=self.student)
        response = self.client.post(self._class_enroll_url(), {
            'class_id': self.cls.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('status'), 'waitlisted')

        ce = ClassEnrollment.objects.get(student=self.student, cls=self.cls)
        self.assertEqual(ce.status, 'waitlisted')

    # --- Prueba 10: sin matrícula de carrera → 403 ------------------------------

    def test_student_cannot_enroll_in_class_without_career_enrollment(self):
        """Un estudiante sin matrícula activa para la carrera recibe 403."""
        other_student = make_student(username='no_career_enr', email='no_ce@test.com')
        self.client.force_authenticate(user=other_student)
        response = self.client.post(self._class_enroll_url(), {
            'class_id': self.cls.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Prueba 11: doble inscripción → 400 ------------------------------------

    def test_student_cannot_enroll_twice_in_same_class(self):
        """Inscribirse dos veces en la misma clase devuelve 400."""
        ClassEnrollment.objects.create(student=self.student, cls=self.cls, status='enrolled')
        self.client.force_authenticate(user=self.student)
        response = self.client.post(self._class_enroll_url(), {
            'class_id': self.cls.pk,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Prueba 12: solapamiento de horario → 400 --------------------------------

    def test_schedule_overlap_detected(self):
        """Inscribirse en una clase con horario solapado devuelve 400 con mensaje descriptivo."""
        # El estudiante ya está en cls (Lunes 08:00-10:00)
        ClassEnrollment.objects.create(student=self.student, cls=self.cls, status='enrolled')

        # Clase B: Lunes 09:00-11:00 (solapa con 08:00-10:00)
        subject_b = Subject.objects.create(
            name='Física I', code='FIS1', career=self.career, credits=4,
        )
        cls_b = Class.objects.create(
            subject=subject_b, period=self.period, classroom=self.classroom, max_students=30,
        )
        ClassSchedule.objects.create(cls=cls_b, day_of_week=0, start_time='09:00', end_time='11:00')
        ScheduleAssignment.objects.create(run=self.run, cls=cls_b, slot=self.slot_b_overlap, classroom=self.classroom, teacher=None)

        # Clase C: Lunes 10:00-12:00 (NO solapa — empieza justo cuando termina la A)
        subject_c = Subject.objects.create(
            name='Química I', code='QUI1', career=self.career, credits=4,
        )
        cls_c = Class.objects.create(
            subject=subject_c, period=self.period, classroom=self.classroom, max_students=30,
        )
        ClassSchedule.objects.create(cls=cls_c, day_of_week=0, start_time='10:00', end_time='12:00')
        ScheduleAssignment.objects.create(run=self.run, cls=cls_c, slot=self.slot_c_no_overlap, classroom=self.classroom, teacher=None)

        self.client.force_authenticate(user=self.student)

        # Clase B: debe dar 400 (solapamiento)
        response_b = self.client.post(self._class_enroll_url(), {'class_id': cls_b.pk})
        self.assertEqual(response_b.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Solapamiento', response_b.data.get('detail', ''))

        # Clase C: debe dar 201 (no hay solapamiento)
        response_c = self.client.post(self._class_enroll_url(), {'class_id': cls_c.pk})
        self.assertEqual(response_c.status_code, status.HTTP_201_CREATED)

    # --- Prueba 13: dar de baja → status=dropped --------------------------------

    def test_student_can_unenroll_from_class(self):
        """DELETE sobre la inscripción cambia status a dropped."""
        ce = ClassEnrollment.objects.create(
            student=self.student, cls=self.cls, status='enrolled',
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.delete(self._class_enroll_delete_url(ce.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        ce.refresh_from_db()
        self.assertEqual(ce.status, 'dropped')

    # --- Prueba 14: promoverse de waitlist cuando otro da de baja ---------------

    def test_waitlisted_student_promoted_when_enrolled_drops(self):
        """Al darse de baja un enrolled, el primer waitlisted pasa a enrolled."""
        # Llenar clase (capacidad 2)
        enrolled_student = make_student(username='enrolled_one', email='enr1@test.com')
        CareerEnrollment.objects.create(
            student=enrolled_student, career=self.career, period=self.period, status='active',
        )
        ce_enrolled = ClassEnrollment.objects.create(
            student=enrolled_student, cls=self.cls, status='enrolled',
        )

        s2 = make_student(username='enrolled_two', email='enr2@test.com')
        CareerEnrollment.objects.create(
            student=s2, career=self.career, period=self.period, status='active',
        )
        ClassEnrollment.objects.create(student=s2, cls=self.cls, status='enrolled')

        # waitlisted
        waitlisted_student = make_student(username='waitlisted_one', email='wait1@test.com')
        CareerEnrollment.objects.create(
            student=waitlisted_student, career=self.career, period=self.period, status='active',
        )
        ce_wait = ClassEnrollment.objects.create(
            student=waitlisted_student, cls=self.cls, status='waitlisted',
        )

        # enrolled_student se da de baja
        self.client.force_authenticate(user=enrolled_student)
        response = self.client.delete(self._class_enroll_delete_url(ce_enrolled.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # El waitlisted debe haber sido promovido
        ce_wait.refresh_from_db()
        self.assertEqual(ce_wait.status, 'enrolled')


# ---------------------------------------------------------------------------
# Pruebas de recibos
# ---------------------------------------------------------------------------

class ReceiptTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.student = make_student()
        self.other_student = make_student(username='other_s', email='other_s@test.com')

        self.career = Career.objects.create(
            name='Ingeniería Test', code='ITEST3', duration_years=4, is_active=True,
        )
        self.period = AcademicPeriod.objects.create(
            name='2026-T3', code='2026T3', is_active=True,
            start_date='2026-03-01', end_date='2026-07-31',
        )

        self.enrollment = CareerEnrollment.objects.create(
            student=self.student,
            career=self.career,
            period=self.period,
            status='active',
        )
        self.fee = EnrollmentFee.objects.create(
            career_enrollment=self.enrollment,
            base_amount='800.00',
            discount_amount='0.00',
            final_amount='800.00',
            status='paid',
        )

    def _receipt_url(self, pk):
        return f'/api/enrollment/career-enrollments/{pk}/receipt/'

    # --- Prueba 15: recibo propio -----------------------------------------------

    def test_student_can_get_own_receipt(self):
        """Un estudiante puede obtener su propio justificante."""
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self._receipt_url(self.enrollment.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data['student']['id'], self.student.pk)
        self.assertEqual(data['career']['code'], self.career.code)
        self.assertEqual(data['enrollment']['id'], self.enrollment.pk)
        self.assertEqual(data['fee']['status'], 'paid')

    # --- Prueba 16: recibo ajeno → 403 -----------------------------------------

    def test_student_cannot_get_others_receipt(self):
        """Un estudiante no puede ver el justificante de otro estudiante."""
        self.client.force_authenticate(user=self.other_student)
        response = self.client.get(self._receipt_url(self.enrollment.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
