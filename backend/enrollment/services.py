from decimal import Decimal

from django.db.models import Q, F
from django.utils import timezone

from academic.models import MatriculaConfig
from academic.models import AcademicPeriod
from enrollment.models import CareerEnrollment, ClassEnrollment, EnrollmentFee, StudentBenefit
from enrollment.models import ExceptionalConvocationGrace
from notifications.models import SystemSettings
from grades.models import Grade

# Beneficios que eximen del pago total
_EXEMPT_BENEFITS = frozenset({
    'familia_numerosa_especial',
    'discapacidad_33',
    'beca_mec',
})

# Beneficios que aplican un descuento porcentual
_DISCOUNT_BENEFITS = {
    'familia_numerosa_general': Decimal('50'),
}

CONVOCATION_ALLOWED = 'allowed'
CONVOCATION_GRACE = 'extraordinary-grace'
CONVOCATION_BLOCKED = 'blocked'


# ---------------------------------------------------------------------------
# Utilidades internas
# ---------------------------------------------------------------------------

def _get_active_benefit(student):
    """
    Devuelve el beneficio verificado y vigente más favorable del alumno,
    o None si no tiene ninguno activo.

    Prioridad: exención total > descuento parcial.
    """
    today = timezone.now().date()
    benefits = StudentBenefit.objects.filter(
        student=student,
        verified=True,
    ).filter(
        Q(valid_until__isnull=True) | Q(valid_until__gte=today)
    )

    for b in benefits:
        if b.benefit_type in _EXEMPT_BENEFITS:
            return b
    for b in benefits:
        if b.benefit_type in _DISCOUNT_BENEFITS:
            return b
    return None


def _get_attempt_number(student, subject, exclude_ids=None):
    """
    Devuelve el número de intento de matrícula para un alumno en una asignatura.

    Cuenta todas las ClassEnrollment previas no descartadas (status != 'dropped'),
    excluyendo los IDs de la matrícula actual (para no contarla como intento pasado).
    El resultado se capa en 4 ('4ª o más').
    """
    qs = ClassEnrollment.objects.filter(
        student=student,
        cls__subject=subject,
    ).exclude(status='dropped')

    if exclude_ids:
        qs = qs.exclude(pk__in=exclude_ids)

    past_count = qs.count()
    return min(past_count + 1, 4)


def _get_price_per_credit(attempt_number, subject=None):
    """
    Devuelve el precio por crédito para un número de intento dado.

    Prioridad:
    1. Precio específico configurado en la asignatura.
    2. Configuración global legacy MatriculaConfig.

    Lanza ValueError si no hay configuración activa.
    """
    if subject is not None and hasattr(subject, 'get_credit_price_for_attempt'):
        return subject.get_credit_price_for_attempt(attempt_number)

    config = MatriculaConfig.objects.filter(
        attempt_number=attempt_number,
        is_active=True,
    ).first()

    if config is None:
        raise ValueError(
            f'No hay precio configurado para el intento {attempt_number}. '
            'Verificá la tabla MatriculaConfig.'
        )
    return config.price_per_credit


def _money(value):
    return Decimal(str(value or '0')).quantize(Decimal('0.01'))


def _final_failure_qs(student, subject, target_period):
    # La elegibilidad se calcula en lectura/escritura solo con notas finales de periodos previos.
    return Grade.objects.filter(
        student=student,
        evaluation__is_final_grade=True,
        evaluation__cls__subject=subject,
        evaluation__cls__period__start_date__lt=target_period.start_date,
    ).exclude(score__gte=F('evaluation__cls__passing_grade'))


def _student_passed_class(student, cls):
    from grades.services import resolve_class_final_grade

    resolved = resolve_class_final_grade(student, cls)
    return resolved['passed']


def resolve_convocation_eligibility(student, subject, target_period):
    # Un permiso extraordinario solo anula el bloqueo para la tupla exacta estudiante/asignatura/periodo.
    failed_convocations = 0
    prior_classes = (
        Grade.objects.filter(
            student=student,
            evaluation__cls__subject=subject,
            evaluation__cls__period__start_date__lt=target_period.start_date,
            evaluation__is_final_grade=True,
        )
        .values_list('evaluation__cls', flat=True)
        .distinct()
    )
    from academic.models import Class
    for cls in Class.objects.filter(id__in=prior_classes):
        if _student_passed_class(student, cls) is False:
            failed_convocations += 1
    max_convocations = subject.max_convocations or 6
    has_grace = ExceptionalConvocationGrace.objects.filter(
        student=student,
        subject=subject,
        period=target_period,
        is_active=True,
    ).exists()

    if failed_convocations >= max_convocations:
        eligibility = CONVOCATION_GRACE if has_grace else CONVOCATION_BLOCKED
    else:
        eligibility = CONVOCATION_ALLOWED

    return {
        'convocation_eligibility': eligibility,
        'failed_convocations': failed_convocations,
        'max_convocations': max_convocations,
        'convocation_block_reason': 'limit_reached' if eligibility == CONVOCATION_BLOCKED else None,
    }


def _serialize_amount(value):
    return str(_money(value))


def _student_has_previous_school_period(student, current_enrollment=None):
    """
    True si el alumno ya tuvo alguna matrícula de carrera previa.

    La apertura de expediente solo se cobra cuando NO existe ningún periodo
    escolar/matrícula anterior. Excluimos la matrícula actual porque al calcular
    el pago ya existe como borrador.
    """
    qs = CareerEnrollment.objects.filter(student=student).exclude(status='dropped')
    if current_enrollment is not None and current_enrollment.pk:
        qs = qs.exclude(pk=current_enrollment.pk)
    return qs.exists()


def _get_enrollment_charge_items(student, current_enrollment=None):
    settings, _ = SystemSettings.objects.get_or_create(pk=1)
    items = []

    school_insurance_fee = _money(settings.school_insurance_fee)
    if school_insurance_fee > 0:
        items.append({
            'type': 'school_insurance',
            'label': 'Seguro escolar',
            'amount': school_insurance_fee,
        })

    transcript_opening_fee = _money(settings.transcript_opening_fee)
    if transcript_opening_fee > 0 and not _student_has_previous_school_period(
        student,
        current_enrollment=current_enrollment,
    ):
        items.append({
            'type': 'transcript_opening',
            'label': 'Apertura de expediente',
            'amount': transcript_opening_fee,
        })

    for charge in settings.enrollment_extra_charges or []:
        if not isinstance(charge, dict) or not charge.get('active', True):
            continue
        amount = _money(charge.get('amount', '0'))
        if amount <= 0:
            continue
        items.append({
            'type': 'extra_charge',
            'label': str(charge.get('label', 'Cobro extra')).strip() or 'Cobro extra',
            'amount': amount,
        })

    return items


# ---------------------------------------------------------------------------
# Servicios públicos
# ---------------------------------------------------------------------------

def calculate_enrollment_cost(student, class_enrollments, career_enrollment=None):
    """
    Calcula el coste total de matrícula para un alumno dado un conjunto de
    ClassEnrollment, aplicando las bonificaciones verificadas del expediente.

    Args:
        student: instancia de User con role='s'
        class_enrollments: iterable de ClassEnrollment

    Returns:
        dict con:
            - line_items: lista de dicts por asignatura y cobros administrativos
            - base_amount: Decimal — total antes de descuento
            - discount_percent: Decimal — 0, 50 o 100
            - discount_amount: Decimal
            - final_amount: Decimal
            - benefit_applied: str con benefit_type aplicado, o None
    """
    class_enrollments = list(class_enrollments)
    current_ids = [ce.pk for ce in class_enrollments if ce.pk is not None]

    line_items = []
    base_amount = Decimal('0.00')

    for ce in class_enrollments:
        subject = ce.cls.subject
        attempt = _get_attempt_number(student, subject, exclude_ids=current_ids)
        price_per_credit = _get_price_per_credit(attempt, subject=subject)
        subtotal = Decimal(subject.credits) * price_per_credit

        line_items.append({
            'type': 'subject',
            'label': subject.name,
            'subject_code': subject.code,
            'subject_name': subject.name,
            'credits': subject.credits,
            'attempt_number': attempt,
            'price_per_credit': price_per_credit,
            'subtotal': subtotal,
        })
        base_amount += subtotal

    for charge in _get_enrollment_charge_items(student, current_enrollment=career_enrollment):
        line_items.append({
            **charge,
            'subtotal': charge['amount'],
        })
        base_amount += charge['amount']

    benefit = _get_active_benefit(student)
    discount_percent = Decimal('0')
    benefit_applied = None

    if benefit:
        benefit_applied = benefit.benefit_type
        if benefit.benefit_type in _EXEMPT_BENEFITS:
            discount_percent = Decimal('100')
        else:
            discount_percent = _DISCOUNT_BENEFITS[benefit.benefit_type]

    discount_amount = (base_amount * discount_percent / Decimal('100')).quantize(Decimal('0.01'))
    final_amount = base_amount - discount_amount

    return {
        'line_items': line_items,
        'base_amount': base_amount,
        'discount_percent': discount_percent,
        'discount_amount': discount_amount,
        'final_amount': final_amount,
        'benefit_applied': benefit_applied,
    }


def serialize_enrollment_cost_line_items(line_items):
    serialized = []
    for item in line_items:
        data = {}
        for key, value in item.items():
            if isinstance(value, Decimal):
                data[key] = _serialize_amount(value)
            else:
                data[key] = value
        serialized.append(data)
    return serialized


def refresh_enrollment_fee(career_enrollment):
    """
    Recalcula y persiste el pago de matrícula a partir de las asignaturas
    elegidas. Debe llamarse DESPUÉS de seleccionar asignaturas, no al crear
    la matrícula.
    """
    class_enrollments = (
        ClassEnrollment.objects
        .filter(
            student=career_enrollment.student,
            cls__period=career_enrollment.period,
            cls__subject__career=career_enrollment.career,
            status='enrolled',
        )
        .select_related('cls__subject')
    )
    cost = calculate_enrollment_cost(
        career_enrollment.student,
        class_enrollments,
        career_enrollment=career_enrollment,
    )
    discount_reason = cost['benefit_applied'] or ''
    if cost['discount_percent'] and cost['benefit_applied']:
        discount_reason = f"{cost['benefit_applied']} ({cost['discount_percent']}%)"

    fee, _ = EnrollmentFee.objects.get_or_create(
        career_enrollment=career_enrollment,
        defaults={
            'base_amount': cost['base_amount'],
            'discount_amount': cost['discount_amount'],
            'discount_reason': discount_reason,
            'final_amount': cost['final_amount'],
            'line_items': serialize_enrollment_cost_line_items(cost['line_items']),
        },
    )

    if fee.status != 'paid':
        fee.base_amount = cost['base_amount']
        fee.discount_amount = cost['discount_amount']
        fee.discount_reason = discount_reason
        fee.final_amount = cost['final_amount']
        fee.line_items = serialize_enrollment_cost_line_items(cost['line_items'])
        fee.stripe_payment_intent_id = ''
        fee.stripe_payment_status = ''
        fee.paid_at = None
        fee.status = 'exempted' if cost['final_amount'] <= Decimal('0.00') else 'pending'
        fee.save()

    return fee


def calculate_student_progress(student, career):
    """
    Calcula el progreso académico de un alumno en una carrera basándose en
    las notas ponderadas de cada clase frente al umbral passing_grade del profesor.

    Una asignatura se considera superada cuando:
        Σ (score / max_score × 10 × weight) / Σ weight  ≥  cls.passing_grade

    Solo se evalúan ClassEnrollment con status='enrolled'.
    Asignaturas sin ninguna evaluación calificada se omiten.

    Args:
        student: instancia de User con role='s'
        career: instancia de Career

    Returns:
        dict con:
            - ects_completed: int — créditos superados
            - ects_total: int — total de la carrera (duration_years × 60)
            - percentage: float — porcentaje completado (0–100)
            - by_type: dict — desglose de créditos superados por subject_type
    """
    from academic.models import Class
    from grades.services import resolve_class_final_grade

    class_enrollments = ClassEnrollment.objects.filter(
        student=student,
        status='enrolled',
        cls__subject__career=career,
    ).select_related('cls__subject', 'cls')

    ects_completed = 0
    by_type = {}

    for ce in class_enrollments:
        cls = ce.cls
        subject = cls.subject
        resolved = resolve_class_final_grade(student, cls)
        if resolved['passed']:
            credits = subject.credits
            ects_completed += credits
            stype = subject.subject_type
            by_type[stype] = by_type.get(stype, 0) + credits

    ects_total = career.duration_years * 60
    percentage = round((ects_completed / ects_total) * 100, 2) if ects_total > 0 else 0.0

    return {
        'ects_completed': ects_completed,
        'ects_total': ects_total,
        'percentage': percentage,
        'by_type': by_type,
    }
