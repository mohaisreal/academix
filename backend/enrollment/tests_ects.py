"""
Tests para el módulo ECTS: cálculo de coste de matrícula y progreso académico.
"""
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from users.models import User
from academic.models import Career, AcademicPeriod, Subject, Class, Classroom, MatriculaConfig
from enrollment.models import CareerEnrollment, ClassEnrollment, StudentBenefit
from enrollment.services import calculate_enrollment_cost, calculate_student_progress
from grades.models import Evaluation, Grade
from notifications.models import SystemSettings


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------

def make_student(username='student1', email='student1@test.com'):
    user = User.objects.create_user(
        username=username, email=email, password='testpass123', is_active=True,
    )
    user.role = 's'
    user.save()
    return user


def make_teacher(username='teacher1', email='teacher1@test.com'):
    user = User.objects.create_user(
        username=username, email=email, password='testpass123', is_active=True,
    )
    user.role = 't'
    user.save()
    return user


def setup_matricula_prices():
    """Crea la tabla de precios de matrícula estándar española."""
    MatriculaConfig.objects.bulk_create([
        MatriculaConfig(attempt_number=1, label='1ª matrícula', price_per_credit=Decimal('16.00')),
        MatriculaConfig(attempt_number=2, label='2ª matrícula', price_per_credit=Decimal('28.00')),
        MatriculaConfig(attempt_number=3, label='3ª matrícula', price_per_credit=Decimal('45.00')),
        MatriculaConfig(attempt_number=4, label='4ª o más',    price_per_credit=Decimal('60.00')),
    ])


def make_career(name='Ingeniería', code='ING', duration_years=4):
    return Career.objects.create(name=name, code=code, duration_years=duration_years)


def make_period(name='2026-1', code='2026-1'):
    return AcademicPeriod.objects.create(
        name=name, code=code,
        start_date='2026-03-01', end_date='2026-07-31',
        is_active=True,
    )


def make_subject(career, name='Matemáticas', code='MAT1', credits=6, subject_type='obligatoria', **extra):
    return Subject.objects.create(
        name=name, code=code, career=career,
        credits=credits, subject_type=subject_type, **extra,
    )


def make_class(subject, period, passing_grade=Decimal('5.00')):
    classroom = Classroom.objects.create(
        name='Aula 1', building='A', capacity=30, type='lecture',
    )
    return Class.objects.create(
        subject=subject, period=period,
        classroom=classroom, max_students=30,
        passing_grade=passing_grade,
    )


def make_evaluation(cls, name='Examen', weight=Decimal('100'), max_score=Decimal('100')):
    return Evaluation.objects.create(
        name=name, cls=cls, type='exam',
        weight=weight, max_score=max_score,
    )


def make_grade(student, evaluation, score):
    return Grade.objects.create(
        student=student, evaluation=evaluation,
        score=Decimal(str(score)),
    )


def make_class_enrollment(student, cls, status='enrolled'):
    return ClassEnrollment.objects.create(
        student=student, cls=cls, status=status,
    )


# ---------------------------------------------------------------------------
# Pruebas de MatriculaConfig
# ---------------------------------------------------------------------------

class MatriculaConfigTests(TestCase):

    def test_prices_are_created_and_ordered(self):
        """Los precios se crean y se devuelven ordenados por número de intento."""
        setup_matricula_prices()
        configs = list(MatriculaConfig.objects.all())
        self.assertEqual(len(configs), 4)
        self.assertEqual(configs[0].attempt_number, 1)
        self.assertEqual(configs[0].price_per_credit, Decimal('16.00'))
        self.assertEqual(configs[3].attempt_number, 4)
        self.assertEqual(configs[3].price_per_credit, Decimal('60.00'))

    def test_attempt_number_is_unique(self):
        """No se pueden crear dos configuraciones con el mismo número de intento."""
        from django.db import IntegrityError
        MatriculaConfig.objects.create(
            attempt_number=1, label='1ª matrícula', price_per_credit=Decimal('16.00'),
        )
        with self.assertRaises(IntegrityError):
            MatriculaConfig.objects.create(
                attempt_number=1, label='Duplicado', price_per_credit=Decimal('20.00'),
            )


# ---------------------------------------------------------------------------
# Pruebas de StudentBenefit
# ---------------------------------------------------------------------------

class StudentBenefitTests(TestCase):

    def setUp(self):
        self.student = make_student()

    def test_benefit_created_unverified_by_default(self):
        """Un beneficio recién creado no está verificado."""
        benefit = StudentBenefit.objects.create(
            student=self.student,
            benefit_type='beca_mec',
        )
        self.assertFalse(benefit.verified)
        self.assertIsNone(benefit.valid_until)

    def test_student_cannot_have_duplicate_benefit_type(self):
        """Un alumno no puede tener el mismo tipo de beneficio dos veces."""
        from django.db import IntegrityError
        StudentBenefit.objects.create(student=self.student, benefit_type='beca_mec')
        with self.assertRaises(IntegrityError):
            StudentBenefit.objects.create(student=self.student, benefit_type='beca_mec')


# ---------------------------------------------------------------------------
# Pruebas de calculate_enrollment_cost
# ---------------------------------------------------------------------------

class EnrollmentCostTests(TestCase):

    def setUp(self):
        setup_matricula_prices()
        self.student = make_student()
        self.career = make_career()
        self.period = make_period()

    def _make_enrolled(self, subject, status='enrolled'):
        cls = make_class(subject, self.period)
        return make_class_enrollment(self.student, cls, status=status)

    # --- Caso 1: sin beneficios, primera matrícula ---

    def test_first_attempt_no_benefit(self):
        """6 créditos × 16 €/cr = 96 €, sin descuento."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        ce = self._make_enrolled(subject)

        result = calculate_enrollment_cost(self.student, [ce])

        self.assertEqual(result['base_amount'], Decimal('96.00'))
        self.assertEqual(result['discount_percent'], Decimal('0'))
        self.assertEqual(result['final_amount'], Decimal('96.00'))
        self.assertIsNone(result['benefit_applied'])
        self.assertEqual(len(result['line_items']), 1)
        self.assertEqual(result['line_items'][0]['attempt_number'], 1)

    # --- Caso 2: múltiples asignaturas, primer intento ---

    def test_multiple_subjects_first_attempt(self):
        """Dos asignaturas, 6 y 4 créditos → (6+4) × 16 = 160 €."""
        s1 = make_subject(self.career, code='MAT1', credits=6)
        s2 = make_subject(self.career, code='FIS1', credits=4)
        ce1 = self._make_enrolled(s1)
        ce2 = self._make_enrolled(s2)

        result = calculate_enrollment_cost(self.student, [ce1, ce2])

        self.assertEqual(result['base_amount'], Decimal('160.00'))
        self.assertEqual(result['final_amount'], Decimal('160.00'))
        self.assertEqual(len(result['line_items']), 2)

    # --- Caso 3: segunda matrícula (intento 2) ---

    def test_second_attempt_price(self):
        """Si el alumno ya cursó la asignatura, aplica precio de 2ª matrícula (28 €/cr)."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        period2 = make_period(name='2025-1', code='2025-1')
        cls_past = make_class(subject, period2)
        # Matrícula pasada (ya existe en BD)
        ClassEnrollment.objects.create(student=self.student, cls=cls_past, status='enrolled')

        # Nueva matrícula en el período actual
        ce_new = self._make_enrolled(subject)

        result = calculate_enrollment_cost(self.student, [ce_new])

        self.assertEqual(result['line_items'][0]['attempt_number'], 2)
        self.assertEqual(result['base_amount'], Decimal('168.00'))  # 6 × 28

    # --- Caso 4: intento 4+ usa precio de 4ª ---

    def test_fourth_attempt_capped(self):
        """El 5º intento usa el precio del 4º (cap en 4)."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        for i in range(4):
            p = make_period(name=f'Period {i}', code=f'P{i}')
            cls = make_class(subject, p)
            ClassEnrollment.objects.create(student=self.student, cls=cls, status='enrolled')

        ce_new = self._make_enrolled(subject)
        result = calculate_enrollment_cost(self.student, [ce_new])

        self.assertEqual(result['line_items'][0]['attempt_number'], 4)
        self.assertEqual(result['base_amount'], Decimal('360.00'))  # 6 × 60

    # --- Caso 5: familia numerosa general → 50% ---

    def test_familia_numerosa_general_applies_50_percent(self):
        """Familia numerosa general aplica 50% de descuento."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        ce = self._make_enrolled(subject)

        StudentBenefit.objects.create(
            student=self.student,
            benefit_type='familia_numerosa_general',
            verified=True,
        )

        result = calculate_enrollment_cost(self.student, [ce])

        self.assertEqual(result['discount_percent'], Decimal('50'))
        self.assertEqual(result['base_amount'], Decimal('96.00'))
        self.assertEqual(result['discount_amount'], Decimal('48.00'))
        self.assertEqual(result['final_amount'], Decimal('48.00'))
        self.assertEqual(result['benefit_applied'], 'familia_numerosa_general')

    # --- Caso 6: familia numerosa especial → gratuita ---

    def test_familia_numerosa_especial_is_free(self):
        """Familia numerosa especial exime del pago total."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        ce = self._make_enrolled(subject)

        StudentBenefit.objects.create(
            student=self.student,
            benefit_type='familia_numerosa_especial',
            verified=True,
        )

        result = calculate_enrollment_cost(self.student, [ce])

        self.assertEqual(result['final_amount'], Decimal('0.00'))
        self.assertEqual(result['discount_percent'], Decimal('100'))

    # --- Caso 7: beca MEC → gratuita ---

    def test_beca_mec_is_free(self):
        """Beca MEC exime del pago total."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        ce = self._make_enrolled(subject)

        StudentBenefit.objects.create(
            student=self.student,
            benefit_type='beca_mec',
            verified=True,
        )

        result = calculate_enrollment_cost(self.student, [ce])

        self.assertEqual(result['final_amount'], Decimal('0.00'))
        self.assertEqual(result['benefit_applied'], 'beca_mec')

    # --- Caso 8: discapacidad 33 → gratuita ---

    def test_discapacidad_33_is_free(self):
        """Discapacidad ≥ 33% exime del pago total."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        ce = self._make_enrolled(subject)

        StudentBenefit.objects.create(
            student=self.student,
            benefit_type='discapacidad_33',
            verified=True,
        )

        result = calculate_enrollment_cost(self.student, [ce])

        self.assertEqual(result['final_amount'], Decimal('0.00'))

    # --- Caso 9: beneficio no verificado → no se aplica ---

    def test_unverified_benefit_not_applied(self):
        """Un beneficio no verificado por administración no se aplica."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        ce = self._make_enrolled(subject)

        StudentBenefit.objects.create(
            student=self.student,
            benefit_type='beca_mec',
            verified=False,
        )

        result = calculate_enrollment_cost(self.student, [ce])

        self.assertIsNone(result['benefit_applied'])
        self.assertEqual(result['final_amount'], Decimal('96.00'))

    # --- Caso 10: beneficio vencido → no se aplica ---

    def test_expired_benefit_not_applied(self):
        """Un beneficio con valid_until en el pasado no se aplica."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        ce = self._make_enrolled(subject)

        yesterday = timezone.now().date().replace(year=timezone.now().year - 1)
        StudentBenefit.objects.create(
            student=self.student,
            benefit_type='beca_mec',
            verified=True,
            valid_until=yesterday,
        )

        result = calculate_enrollment_cost(self.student, [ce])

        self.assertIsNone(result['benefit_applied'])
        self.assertEqual(result['final_amount'], Decimal('96.00'))

    # --- Caso 11: múltiples beneficios → se aplica el más favorable ---

    def test_most_favorable_benefit_wins(self):
        """Si el alumno tiene familia general (50%) y beca MEC (100%), gana la exención."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        ce = self._make_enrolled(subject)

        StudentBenefit.objects.create(
            student=self.student,
            benefit_type='familia_numerosa_general',
            verified=True,
        )
        StudentBenefit.objects.create(
            student=self.student,
            benefit_type='beca_mec',
            verified=True,
        )

        result = calculate_enrollment_cost(self.student, [ce])

        self.assertEqual(result['discount_percent'], Decimal('100'))
        self.assertEqual(result['final_amount'], Decimal('0.00'))

    # --- Caso 12: asignatura dropped no cuenta como intento previo ---

    def test_dropped_enrollment_does_not_count_as_attempt(self):
        """Una matrícula con status=dropped no cuenta como intento previo."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        period_past = make_period(name='2025-1', code='2025-1')
        cls_past = make_class(subject, period_past)
        ClassEnrollment.objects.create(
            student=self.student, cls=cls_past, status='dropped',
        )

        ce_new = self._make_enrolled(subject)
        result = calculate_enrollment_cost(self.student, [ce_new])

        self.assertEqual(result['line_items'][0]['attempt_number'], 1)
        self.assertEqual(result['base_amount'], Decimal('96.00'))

    # --- Caso 13: precio por asignatura sin MatriculaConfig legacy ---

    def test_subject_price_is_used_without_global_price_config(self):
        """La asignatura define sus propios precios, sin depender de MatriculaConfig."""
        MatriculaConfig.objects.all().delete()
        subject = make_subject(
            self.career,
            code='MAT1',
            credits=6,
            credit_price_first_enrollment=Decimal('21.00'),
        )
        ce = self._make_enrolled(subject)

        result = calculate_enrollment_cost(self.student, [ce])

        self.assertEqual(result['line_items'][0]['price_per_credit'], Decimal('21.00'))
        self.assertEqual(result['base_amount'], Decimal('126.00'))

    # --- Caso 14: cobros administrativos configurables ---

    def test_administrative_charges_are_added_after_subject_selection(self):
        """Seguro escolar, apertura de expediente y extras se suman al pago final."""
        SystemSettings.objects.update_or_create(
            pk=1,
            defaults={
                'school_insurance_fee': Decimal('12.00'),
                'transcript_opening_fee': Decimal('45.00'),
                'enrollment_extra_charges': [
                    {'label': 'Carné universitario', 'amount': '8.00', 'active': True},
                    {'label': 'Cobro inactivo', 'amount': '99.00', 'active': False},
                ],
            },
        )
        enrollment = CareerEnrollment.objects.create(
            student=self.student,
            career=self.career,
            period=self.period,
            status='pending',
        )
        subject = make_subject(self.career, code='ADMCHG', credits=6)
        ce = self._make_enrolled(subject)

        result = calculate_enrollment_cost(self.student, [ce], career_enrollment=enrollment)

        self.assertEqual(result['base_amount'], Decimal('161.00'))  # 96 + 12 + 45 + 8
        self.assertEqual(result['final_amount'], Decimal('161.00'))
        self.assertIn('school_insurance', [item['type'] for item in result['line_items']])
        self.assertIn('transcript_opening', [item['type'] for item in result['line_items']])
        self.assertIn('extra_charge', [item['type'] for item in result['line_items']])

    def test_transcript_opening_is_not_added_for_returning_student(self):
        """Apertura de expediente no se cobra si el alumno ya tenía una matrícula previa."""
        SystemSettings.objects.update_or_create(
            pk=1,
            defaults={
                'school_insurance_fee': Decimal('0.00'),
                'transcript_opening_fee': Decimal('45.00'),
                'enrollment_extra_charges': [],
            },
        )
        past_period = make_period(name='2025-returning', code='2025-returning')
        CareerEnrollment.objects.create(
            student=self.student,
            career=self.career,
            period=past_period,
            status='active',
        )
        current = CareerEnrollment.objects.create(
            student=self.student,
            career=self.career,
            period=self.period,
            status='pending',
        )
        subject = make_subject(self.career, code='RETURN', credits=6)
        ce = self._make_enrolled(subject)

        result = calculate_enrollment_cost(self.student, [ce], career_enrollment=current)

        self.assertEqual(result['base_amount'], Decimal('96.00'))
        self.assertNotIn('transcript_opening', [item['type'] for item in result['line_items']])


# ---------------------------------------------------------------------------
# Pruebas de calculate_student_progress
# ---------------------------------------------------------------------------

class StudentProgressTests(TestCase):

    def setUp(self):
        self.student = make_student()
        self.career = make_career(duration_years=4)
        self.period = make_period()

    # --- Caso 1: sin matrículas → 0% ---

    def test_no_enrollments_returns_zero_progress(self):
        """Sin ninguna matrícula, el progreso es 0%."""
        result = calculate_student_progress(self.student, self.career)

        self.assertEqual(result['ects_completed'], 0)
        self.assertEqual(result['ects_total'], 240)
        self.assertEqual(result['percentage'], 0.0)
        self.assertEqual(result['by_type'], {})

    # --- Caso 2: matriculado pero sin notas → no se cuenta ---

    def test_enrolled_without_grades_not_counted(self):
        """Una asignatura matriculada sin notas registradas no cuenta como superada."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        cls = make_class(subject, self.period)
        make_evaluation(cls, weight=Decimal('100'))
        make_class_enrollment(self.student, cls)

        result = calculate_student_progress(self.student, self.career)

        self.assertEqual(result['ects_completed'], 0)

    # --- Caso 3: asignatura superada → créditos contabilizados ---

    def test_passed_subject_adds_credits(self):
        """Una asignatura con nota final ≥ passing_grade suma sus créditos."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        cls = make_class(subject, self.period, passing_grade=Decimal('5.00'))
        ev = make_evaluation(cls, weight=Decimal('100'), max_score=Decimal('10'))
        make_class_enrollment(self.student, cls)
        make_grade(self.student, ev, score=7)

        result = calculate_student_progress(self.student, self.career)

        self.assertEqual(result['ects_completed'], 6)
        self.assertAlmostEqual(result['percentage'], 2.5)  # 6/240 × 100

    # --- Caso 4: asignatura suspendida → no se cuenta ---

    def test_failed_subject_not_counted(self):
        """Una asignatura con nota final < passing_grade no suma créditos."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        cls = make_class(subject, self.period, passing_grade=Decimal('5.00'))
        ev = make_evaluation(cls, weight=Decimal('100'), max_score=Decimal('10'))
        make_class_enrollment(self.student, cls)
        make_grade(self.student, ev, score=4)

        result = calculate_student_progress(self.student, self.career)

        self.assertEqual(result['ects_completed'], 0)

    # --- Caso 5: nota ponderada correctamente calculada ---

    def test_weighted_grade_calculation(self):
        """La nota ponderada combina correctamente dos evaluaciones con distinto peso."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        cls = make_class(subject, self.period, passing_grade=Decimal('5.00'))
        make_class_enrollment(self.student, cls)

        # Examen 60%, trabajo 40%
        ev_exam = make_evaluation(cls, name='Examen', weight=Decimal('60'), max_score=Decimal('10'))
        ev_work = make_evaluation(cls, name='Trabajo', weight=Decimal('40'), max_score=Decimal('100'))

        # Examen: 3/10 → nota 3.0 | Trabajo: 90/100 → nota 9.0
        # Ponderada: (3 × 60 + 9 × 40) / 100 = (180 + 360) / 100 = 5.4 → aprobado
        make_grade(self.student, ev_exam, score=3)
        make_grade(self.student, ev_work, score=90)

        result = calculate_student_progress(self.student, self.career)

        self.assertEqual(result['ects_completed'], 6)

    # --- Caso 6: passing_grade personalizado por el profesor ---

    def test_custom_passing_grade_respected(self):
        """El umbral de aprobado del profesor se respeta para el cálculo."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        cls = make_class(subject, self.period, passing_grade=Decimal('7.00'))
        ev = make_evaluation(cls, weight=Decimal('100'), max_score=Decimal('10'))
        make_class_enrollment(self.student, cls)
        # Nota 6.5: aprueba con passing_grade=5 pero no con passing_grade=7
        make_grade(self.student, ev, score=Decimal('6.5'))

        result = calculate_student_progress(self.student, self.career)

        self.assertEqual(result['ects_completed'], 0)

    # --- Caso 7: desglose por tipo de asignatura ---

    def test_progress_breakdown_by_subject_type(self):
        """El desglose by_type separa correctamente los créditos por tipo."""
        s_basica = make_subject(self.career, code='B1', credits=6, subject_type='basica')
        s_oblig = make_subject(self.career, code='O1', credits=9, subject_type='obligatoria')

        for subject in [s_basica, s_oblig]:
            cls = make_class(subject, self.period)
            ev = make_evaluation(cls, weight=Decimal('100'), max_score=Decimal('10'))
            make_class_enrollment(self.student, cls)
            make_grade(self.student, ev, score=8)

        result = calculate_student_progress(self.student, self.career)

        self.assertEqual(result['ects_completed'], 15)
        self.assertEqual(result['by_type']['basica'], 6)
        self.assertEqual(result['by_type']['obligatoria'], 9)

    # --- Caso 8: solo se cuentan matrículas con status=enrolled ---

    def test_only_enrolled_status_counts(self):
        """Matrículas con status=dropped o waitlisted no cuentan para el progreso."""
        subject = make_subject(self.career, code='MAT1', credits=6)
        cls = make_class(subject, self.period)
        ev = make_evaluation(cls, weight=Decimal('100'), max_score=Decimal('10'))
        make_class_enrollment(self.student, cls, status='dropped')
        make_grade(self.student, ev, score=9)

        result = calculate_student_progress(self.student, self.career)

        self.assertEqual(result['ects_completed'], 0)

    # --- Caso 9: total ECTS según duración de la carrera ---

    def test_ects_total_based_on_career_duration(self):
        """Una carrera de 3 años tiene 180 ECTS totales."""
        career_3y = make_career(name='Diplomatura', code='DIP', duration_years=3)

        result = calculate_student_progress(self.student, career_3y)

        self.assertEqual(result['ects_total'], 180)
