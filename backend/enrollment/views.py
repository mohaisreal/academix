from rest_framework.views import APIView
from rest_framework import generics, status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal
import unicodedata

from .models import CareerEnrollment, ClassEnrollment, EnrollmentFee
from .serializers import CareerEnrollmentSerializer, ClassEnrollmentSerializer, EnrollmentFeeSerializer
from .services import refresh_enrollment_fee
from academic.models import AcademicPeriod
from notifications.utils import create_notification
from shared.permissions import IsAdminOrManagement, IsStudent

User = get_user_model()


def _is_production_stripe_enabled():
    return (
        not settings.DEBUG
        and getattr(settings, 'STRIPE_LIVE_PAYMENTS_ENABLED', False)
    )


def _amount_to_minor_units(amount):
    return int((Decimal(str(amount)) * Decimal('100')).quantize(Decimal('1')))


def _get_stripe_module():
    try:
        import stripe as stripe_lib
    except ImportError:
        return None
    stripe_lib.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
    return stripe_lib


def _mark_enrollment_paid(enrollment, fee):
    if fee.status != 'paid':
        fee.status = 'paid'
        fee.stripe_payment_status = fee.stripe_payment_status or 'paid'
        fee.paid_at = timezone.now()
        fee.save(update_fields=['status', 'stripe_payment_status', 'paid_at'])

    if enrollment.status != 'active':
        enrollment.status = 'active'
        enrollment.save(update_fields=['status', 'updated_at'])

    try:
        from admissions.models import AdmissionApplication
        AdmissionApplication.objects.filter(
            student=enrollment.student,
            assigned_career=enrollment.career,
            academic_period=enrollment.period,
            status='confirmed',
        ).update(status='completed')
    except Exception:
        pass

    create_notification(
        user=enrollment.student,
        title='Matrícula confirmada',
        message=f'Matrícula confirmada para {enrollment.career.name} - {enrollment.period.name}.',
        notif_type='success',
        event_type='enrollment_confirmed',
        context={
            'career_name': enrollment.career.name,
            'period_name': enrollment.period.name,
        },
    )


def _mark_enrollment_exempted(enrollment, fee):
    fee.status = 'exempted'
    fee.stripe_payment_status = 'exempted'
    fee.paid_at = timezone.now()
    fee.save(update_fields=['status', 'stripe_payment_status', 'paid_at'])

    if enrollment.status != 'active':
        enrollment.status = 'active'
        enrollment.save(update_fields=['status', 'updated_at'])

    try:
        from admissions.models import AdmissionApplication
        AdmissionApplication.objects.filter(
            student=enrollment.student,
            assigned_career=enrollment.career,
            academic_period=enrollment.period,
            status='confirmed',
        ).update(status='completed')
    except Exception:
        pass


class MyEnrollmentView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        career_enrollment = (
            CareerEnrollment.objects
            .filter(student=request.user, status__in=['active', 'completed'])
            .select_related('career', 'period')
            .first()
        )
        if not career_enrollment:
            return Response({'id': None, 'classes': []})

        class_enrollments = (
            ClassEnrollment.objects
            .filter(student=request.user, cls__period=career_enrollment.period, status='enrolled')
            .select_related('cls__subject', 'cls__teacher', 'cls__classroom', 'cls__period')
            .prefetch_related('cls__schedules')
        )

        classes = []
        for ce in class_enrollments:
            cls = ce.cls
            t = cls.teacher
            classes.append({
                'id': ce.id,
                'class_id': cls.id,
                'subject_name': cls.subject.name,
                'subject_code': cls.subject.code,
                'credits': cls.subject.credits,
                'teacher_name': (f"{t.first_name} {t.last_name}".strip() or t.username) if t else '',
                'classroom_name': str(cls.classroom) if cls.classroom else '',
                'status': ce.status,
                'schedules': [
                    {'day_of_week': s.day_of_week, 'start_time': s.start_time.strftime('%H:%M'), 'end_time': s.end_time.strftime('%H:%M') if s.end_time else None}
                    for s in cls.schedules.all()
                ],
            })

        return Response({
            'id': career_enrollment.id,
            'status': career_enrollment.status,
            'career_name': career_enrollment.career.name,
            'period_name': career_enrollment.period.name,
            'enrolled_at': career_enrollment.enrolled_at.isoformat() if career_enrollment.enrolled_at else None,
            'classes': classes,
        })


class MySubjectsView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        from grades.models import Grade, Evaluation
        active_period = AcademicPeriod.objects.filter(is_active=True).first()
        enrollments = (
            ClassEnrollment.objects
            .filter(student=request.user, status='enrolled')
            .select_related('cls__subject', 'cls__teacher', 'cls__classroom', 'cls__period')
            .prefetch_related('cls__schedules')
        )
        if active_period:
            enrollments = enrollments.filter(cls__period=active_period)

        result = []
        for enr in enrollments:
            evals = Evaluation.objects.filter(cls=enr.cls)
            grades = Grade.objects.filter(
                student=request.user,
                evaluation__in=evals,
            ).select_related('evaluation')
            percentages = [
                float(g.score) / float(g.evaluation.max_score) * 100
                for g in grades
                if g.evaluation.max_score and g.evaluation.max_score > 0
            ]
            avg = sum(percentages) / len(percentages) if percentages else None
            t = enr.cls.teacher
            result.append({
                'enrollment_id': enr.id,
                'class_id': enr.cls.id,
                'subject_name': enr.cls.subject.name,
                'subject_code': enr.cls.subject.code,
                'credits': enr.cls.subject.credits,
                'teacher_name': (f"{t.first_name} {t.last_name}".strip() or t.username) if t else None,
                'period_name': enr.cls.period.name,
                'classroom': str(enr.cls.classroom) if enr.cls.classroom else None,
                'current_grade': round(float(avg), 1) if avg is not None else None,
                'status': enr.status,
                'enrolled_at': enr.enrolled_at.isoformat() if enr.enrolled_at else None,
                'schedules': [
                    {'day_of_week': s.day_of_week, 'start_time': s.start_time.strftime('%H:%M'), 'end_time': s.end_time.strftime('%H:%M') if s.end_time else None}
                    for s in enr.cls.schedules.all()
                ],
            })
        return Response(result)


class MyTeachersView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        active_period = AcademicPeriod.objects.filter(is_active=True).first()
        enrollments = (
            ClassEnrollment.objects
            .filter(student=request.user, status='enrolled')
            .select_related('cls__teacher', 'cls__subject', 'cls__period')
        )
        if active_period:
            enrollments = enrollments.filter(cls__period=active_period)

        teachers_map = {}
        for enr in enrollments:
            if not enr.cls.teacher:
                continue
            t = enr.cls.teacher
            if t.id not in teachers_map:
                teachers_map[t.id] = {
                    'id': t.id,
                    'username': t.username,
                    'full_name': f"{t.first_name} {t.last_name}".strip() or t.username,
                    'email': t.email,
                    'phone': t.phone,
                    'profile_image': t.profile_image.url if t.profile_image else None,
                    'subjects': [],
                }
            teachers_map[t.id]['subjects'].append({
                'name': enr.cls.subject.name,
                'code': enr.cls.subject.code,
            })
        return Response(list(teachers_map.values()))


class EnrollmentManagementListCreate(ListCreateAPIView):
    permission_classes = [IsAdminOrManagement]
    serializer_class = CareerEnrollmentSerializer

    def get_queryset(self):
        qs = CareerEnrollment.objects.select_related('student', 'career', 'period').all()
        for param, field in [('career', 'career_id'), ('period', 'period_id'),
                              ('status', 'status'), ('student', 'student_id')]:
            val = self.request.query_params.get(param)
            if val:
                qs = qs.filter(**{field: val})
        return qs


class EnrollmentManagementDetail(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdminOrManagement]
    serializer_class = CareerEnrollmentSerializer
    queryset = CareerEnrollment.objects.all()


class EnrollmentStatusView(APIView):
    permission_classes = [IsAdminOrManagement]

    def patch(self, request, pk):
        try:
            enrollment = CareerEnrollment.objects.get(pk=pk)
        except CareerEnrollment.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        new_status = request.data.get('status')
        valid = [c[0] for c in CareerEnrollment.STATUS_CHOICES]
        if new_status not in valid:
            return Response({'error': f'Estado inválido. Debe ser uno de: {valid}'}, status=400)
        enrollment.status = new_status
        enrollment.save()
        return Response(CareerEnrollmentSerializer(enrollment).data)


class EnrollmentReviewView(APIView):
    permission_classes = [IsAdminOrManagement]

    def get(self, request):
        pending = (
            CareerEnrollment.objects
            .filter(status='pending')
            .select_related('student', 'career', 'period')
        )
        return Response(CareerEnrollmentSerializer(pending, many=True).data)


class EnrollmentApproveView(APIView):
    permission_classes = [IsAdminOrManagement]

    def patch(self, request, pk):
        try:
            enrollment = CareerEnrollment.objects.get(pk=pk)
        except CareerEnrollment.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        enrollment.status = 'active'
        enrollment.save()
        return Response(CareerEnrollmentSerializer(enrollment).data)


class EnrollmentRejectView(APIView):
    permission_classes = [IsAdminOrManagement]

    def patch(self, request, pk):
        try:
            enrollment = CareerEnrollment.objects.get(pk=pk)
        except CareerEnrollment.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        enrollment.status = 'dropped'
        enrollment.save()
        return Response(CareerEnrollmentSerializer(enrollment).data)


# ---- NUEVAS VISTAS: matrícula, pago, justificante ----

class CareerEnrollmentListCreateView(generics.GenericAPIView):
    """
    GET  /api/enrollment/career-enrollments/ — listar matrículas
    POST /api/enrollment/career-enrollments/ — crear matrícula (solo estudiantes con admisión confirmada)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CareerEnrollmentSerializer

    def get(self, request, *args, **kwargs):
        user = request.user
        qs = CareerEnrollment.objects.select_related('student', 'career', 'period')
        if user.role not in ('m', 'a'):
            qs = qs.filter(student=user)
        serializer = CareerEnrollmentSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        from admissions.models import AdmissionApplication

        if request.user.role != 's':
            return Response({"detail": "Solo estudiantes pueden matricularse."}, status=status.HTTP_403_FORBIDDEN)

        career_id = request.data.get('career_id')
        period_id = request.data.get('period_id')

        if not career_id or not period_id:
            return Response({"detail": "career_id y period_id son requeridos."}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar admisión confirmada
        has_admission = AdmissionApplication.objects.filter(
            student=request.user,
            assigned_career_id=career_id,
            academic_period_id=period_id,
            status='confirmed',
        ).exists()

        if not has_admission:
            return Response(
                {"detail": "No tienes admisión confirmada para esta titulación y periodo."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Verificar que no existe ya una matrícula
        existing = CareerEnrollment.objects.filter(
            student=request.user,
            career_id=career_id,
            period_id=period_id,
        ).first()
        if existing:
            return Response(
                {"detail": "Ya tienes una matrícula para esta titulación y periodo.", "enrollment_id": existing.pk},
                status=status.HTTP_400_BAD_REQUEST
            )

        enrollment = CareerEnrollment.objects.create(
            student=request.user,
            career_id=career_id,
            period_id=period_id,
            status='pending',
        )

        serializer = CareerEnrollmentSerializer(enrollment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# Alias para compatibilidad con código existente
CareerEnrollmentCreateView = CareerEnrollmentListCreateView


class EnrollmentFeeDetailView(generics.RetrieveAPIView):
    """GET /api/enrollment/career-enrollments/<pk>/fee/"""
    permission_classes = [IsAuthenticated]
    serializer_class = EnrollmentFeeSerializer

    def get_object(self):
        enrollment = get_object_or_404(
            CareerEnrollment,
            pk=self.kwargs['pk']
        )
        if request := self.request:
            if request.user.role not in ('m', 'a') and enrollment.student != request.user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("No tienes permiso para ver esta información.")

        enrolled_classes = ClassEnrollment.objects.filter(
            student=enrollment.student,
            cls__period=enrollment.period,
            cls__subject__career=enrollment.career,
            status='enrolled',
        ).exists()
        if enrolled_classes:
            return refresh_enrollment_fee(enrollment)
        return get_object_or_404(EnrollmentFee, career_enrollment=enrollment)


class EnrollmentPayView(generics.GenericAPIView):
    """POST /api/enrollment/career-enrollments/<pk>/pay/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        enrollment = get_object_or_404(CareerEnrollment, pk=self.kwargs['pk'])

        if request.user.role not in ('m', 'a') and enrollment.student != request.user:
            return Response({"detail": "No tienes permiso."}, status=status.HTTP_403_FORBIDDEN)

        enrolled_classes = ClassEnrollment.objects.filter(
            student=enrollment.student,
            cls__period=enrollment.period,
            cls__subject__career=enrollment.career,
            status='enrolled',
        ).exists()
        if not enrolled_classes:
            return Response(
                {"detail": "Debes elegir al menos una asignatura antes de pagar la matrícula."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        fee = refresh_enrollment_fee(enrollment)

        if fee.status == 'paid':
            return Response({"detail": "El arancel ya fue pagado."}, status=status.HTTP_400_BAD_REQUEST)

        if fee.final_amount <= Decimal('0.00'):
            _mark_enrollment_exempted(enrollment, fee)
            return Response({
                'mode': 'exempted',
                'enrollment': CareerEnrollmentSerializer(enrollment).data,
                'fee': EnrollmentFeeSerializer(fee).data,
            })

        if not _is_production_stripe_enabled():
            fee.stripe_payment_intent_id = f'pi_demo_enrollment_{fee.pk}'
            fee.stripe_payment_status = 'paid'
            fee.save(update_fields=['stripe_payment_intent_id', 'stripe_payment_status'])
            _mark_enrollment_paid(enrollment, fee)
            return Response({
                'mode': 'demo',
                'enrollment': CareerEnrollmentSerializer(enrollment).data,
                'fee': EnrollmentFeeSerializer(fee).data,
            })

        stripe_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
        if not stripe_key:
            return Response(
                {'detail': 'Stripe no está configurado para pagos de producción.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        stripe_lib = _get_stripe_module()
        if stripe_lib is None:
            return Response(
                {'detail': 'Stripe SDK no está instalado.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            intent = stripe_lib.PaymentIntent.create(
                amount=_amount_to_minor_units(fee.final_amount),
                currency='eur',
                automatic_payment_methods={'enabled': True},
                metadata={
                    'enrollment_fee_id': str(fee.pk),
                    'career_enrollment_id': str(enrollment.pk),
                    'student_id': str(enrollment.student_id),
                },
                description=f'Matrícula {enrollment.career.name} - {enrollment.period.name}',
            )
        except Exception as exc:
            return Response(
                {'detail': f'Error de Stripe: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        fee.stripe_payment_intent_id = intent['id']
        fee.stripe_payment_status = 'pending'
        fee.save(update_fields=['stripe_payment_intent_id', 'stripe_payment_status'])

        return Response({
            'mode': 'stripe',
            'client_secret': intent.get('client_secret'),
            'amount': str(fee.final_amount),
            'currency': 'eur',
            'fee': EnrollmentFeeSerializer(fee).data,
        })


class EnrollmentConfirmPaymentView(generics.GenericAPIView):
    """POST /api/enrollment/career-enrollments/<pk>/confirm-payment/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        enrollment = get_object_or_404(CareerEnrollment, pk=self.kwargs['pk'])

        if request.user.role not in ('m', 'a') and enrollment.student != request.user:
            return Response({"detail": "No tienes permiso."}, status=status.HTTP_403_FORBIDDEN)

        fee = get_object_or_404(EnrollmentFee, career_enrollment=enrollment)
        if fee.status == 'paid':
            return Response({
                'status': 'paid',
                'enrollment': CareerEnrollmentSerializer(enrollment).data,
                'fee': EnrollmentFeeSerializer(fee).data,
            })

        if not _is_production_stripe_enabled():
            if not fee.stripe_payment_intent_id.startswith('pi_demo_'):
                return Response(
                    {'detail': 'La confirmación simulada solo acepta intentos demo.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            fee.stripe_payment_status = 'paid'
            fee.save(update_fields=['stripe_payment_status'])
            _mark_enrollment_paid(enrollment, fee)
            return Response({
                'status': 'paid',
                'enrollment': CareerEnrollmentSerializer(enrollment).data,
                'fee': EnrollmentFeeSerializer(fee).data,
            })

        if not fee.stripe_payment_intent_id:
            return Response(
                {'detail': 'No existe PaymentIntent de Stripe para esta matrícula.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stripe_lib = _get_stripe_module()
        if stripe_lib is None or not getattr(settings, 'STRIPE_SECRET_KEY', ''):
            return Response(
                {'detail': 'Stripe no está configurado para pagos de producción.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            intent = stripe_lib.PaymentIntent.retrieve(fee.stripe_payment_intent_id)
        except Exception as exc:
            return Response(
                {'detail': f'Error de Stripe: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        stripe_status = intent['status']
        if stripe_status == 'succeeded':
            fee.stripe_payment_status = 'paid'
            fee.save(update_fields=['stripe_payment_status'])
            _mark_enrollment_paid(enrollment, fee)
        elif stripe_status in ('requires_payment_method', 'canceled'):
            fee.status = 'failed'
            fee.stripe_payment_status = 'failed'
            fee.save(update_fields=['status', 'stripe_payment_status'])
        else:
            fee.stripe_payment_status = 'pending'
            fee.save(update_fields=['stripe_payment_status'])

        return Response({
            'status': fee.status,
            'stripe_status': stripe_status,
            'enrollment': CareerEnrollmentSerializer(enrollment).data,
            'fee': EnrollmentFeeSerializer(fee).data,
        })


class EnrollmentStripeConfigView(APIView):
    """GET /api/enrollment/stripe/config/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        live_mode = _is_production_stripe_enabled()
        return Response({
            'live_mode': live_mode,
            'publishable_key': getattr(settings, 'STRIPE_PUBLIC_KEY', '') if live_mode else '',
        })


def _get_enrollment_for_receipt(request, pk):
    enrollment = get_object_or_404(
        CareerEnrollment.objects.select_related(
            'student', 'career', 'period', 'fee'
        ),
        pk=pk,
    )
    if request.user.role not in ('m', 'a') and enrollment.student != request.user:
        return None, Response({"detail": "No tienes permiso."}, status=status.HTTP_403_FORBIDDEN)
    return enrollment, None


def _build_enrollment_receipt_data(enrollment):
    class_enrollments = ClassEnrollment.objects.filter(
        student=enrollment.student,
        cls__period=enrollment.period,
        cls__subject__career=enrollment.career,
        status='enrolled',
    ).select_related(
        'cls__subject', 'cls__teacher', 'cls__classroom'
    ).prefetch_related('cls__schedules')

    classes_data = []
    for ce in class_enrollments:
        cls = ce.cls
        schedules = [
            {
                'day': s.get_day_of_week_display() if hasattr(s, 'get_day_of_week_display') else s.day_of_week,
                'start_time': str(s.start_time),
                'end_time': str(s.end_time),
            }
            for s in cls.schedules.all()
        ]
        classes_data.append({
            'class_id': cls.pk,
            'subject_name': cls.subject.name,
            'subject_credits': cls.subject.credits,
            'teacher_name': cls.teacher.get_full_name() if cls.teacher else None,
            'classroom': cls.classroom.name if cls.classroom else None,
            'schedules': schedules,
        })

    try:
        fee = enrollment.fee
        fee_data = {
            'base_amount': str(fee.base_amount),
            'discount_amount': str(fee.discount_amount),
            'discount_reason': fee.discount_reason,
            'final_amount': str(fee.final_amount),
            'line_items': fee.line_items,
            'status': fee.status,
            'paid_at': fee.paid_at.isoformat() if fee.paid_at else None,
        }
    except Exception:
        fee_data = None

    return {
        'student': {
            'id': enrollment.student.pk,
            'full_name': enrollment.student.get_full_name(),
            'email': enrollment.student.email,
            'dni': getattr(enrollment.student, 'dni', None),
        },
        'career': {
            'id': enrollment.career.pk,
            'name': enrollment.career.name,
            'code': enrollment.career.code,
        },
        'period': {
            'id': enrollment.period.pk,
            'name': enrollment.period.name,
            'start_date': str(enrollment.period.start_date),
            'end_date': str(enrollment.period.end_date),
        },
        'enrollment': {
            'id': enrollment.pk,
            'status': enrollment.status,
            'enrolled_at': enrollment.enrolled_at.isoformat(),
        },
        'classes': classes_data,
        'fee': fee_data,
    }


def _pdf_safe_text(value):
    text = str(value or '').replace('\n', ' ').replace('\r', ' ')
    # Helvetica/WinAnsi no soporta todos los glifos Unicode. Normalizamos lo justo
    # para que el PDF sea estable sin depender de librerías externas de renderizado.
    text = text.replace('—', '-').replace('✓', 'OK')
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def _format_pdf_money(value):
    try:
        return f"€{Decimal(str(value or '0')).quantize(Decimal('0.01'))}"
    except Exception:
        return f"€{value or '0.00'}"


def _format_pdf_date(value):
    raw = str(value or '').strip()
    if not raw:
        return '-'
    date_part = raw.split('T')[0].split(' ')[0]
    parts = date_part.split('-')
    if len(parts) == 3:
        return f'{int(parts[2])}/{int(parts[1])}/{parts[0]}'
    return raw


def _truncate_pdf_text(value, max_len):
    text = str(value or '')
    return text if len(text) <= max_len else f'{text[:max_len - 1]}…'


def _build_pdf_document(operations):
    content = '\n'.join(operations).encode('cp1252', errors='replace')

    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>',
        b'<< /Length ' + str(len(content)).encode('ascii') + b' >>\nstream\n' + content + b'\nendstream',
    ]

    pdf = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f'{idx} 0 obj\n'.encode('ascii'))
        pdf.extend(obj)
        pdf.extend(b'\nendobj\n')
    xref = len(pdf)
    pdf.extend(f'xref\n0 {len(objects) + 1}\n'.encode('ascii'))
    pdf.extend(b'0000000000 65535 f \n')
    for offset in offsets[1:]:
        pdf.extend(f'{offset:010d} 00000 n \n'.encode('ascii'))
    pdf.extend(
        f'trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode('ascii')
    )
    return bytes(pdf)


def _build_designed_receipt_pdf(data):
    fee = data.get('fee') or {}
    student = data.get('student') or {}
    career = data.get('career') or {}
    period = data.get('period') or {}
    enrollment = data.get('enrollment') or {}

    ops = []

    def fill(rgb):
        ops.append(f'{rgb[0]} {rgb[1]} {rgb[2]} rg')

    def stroke(rgb):
        ops.append(f'{rgb[0]} {rgb[1]} {rgb[2]} RG')

    def rect(x, y, w, h, rgb):
        fill(rgb)
        ops.append(f'{x} {y} {w} {h} re f')

    def rounded_rect_path(x, y, w, h, r):
        # 0.5522848 aproxima un cuarto de círculo con curvas Bézier.
        c = r * 0.5522848
        return (
            f'{x + r} {y} m '
            f'{x + w - r} {y} l '
            f'{x + w - r + c} {y} {x + w} {y + r - c} {x + w} {y + r} c '
            f'{x + w} {y + h - r} l '
            f'{x + w} {y + h - r + c} {x + w - r + c} {y + h} {x + w - r} {y + h} c '
            f'{x + r} {y + h} l '
            f'{x + r - c} {y + h} {x} {y + h - r + c} {x} {y + h - r} c '
            f'{x} {y + r} l '
            f'{x} {y + r - c} {x + r - c} {y} {x + r} {y} c h'
        )

    def rounded_rect(x, y, w, h, r, fill_rgb, stroke_rgb=None, width=1):
        fill(fill_rgb)
        if stroke_rgb:
            stroke(stroke_rgb)
            ops.append(f'{width} w')
            ops.append(f'{rounded_rect_path(x, y, w, h, r)} B')
        else:
            ops.append(f'{rounded_rect_path(x, y, w, h, r)} f')

    def top_rounded_rect(x, y, w, h, r, rgb):
        fill(rgb)
        c = r * 0.5522848
        ops.append(
            f'{x} {y} m '
            f'{x + w} {y} l '
            f'{x + w} {y + h - r} l '
            f'{x + w} {y + h - r + c} {x + w - r + c} {y + h} {x + w - r} {y + h} c '
            f'{x + r} {y + h} l '
            f'{x + r - c} {y + h} {x} {y + h - r + c} {x} {y + h - r} c '
            f'{x} {y} l h f'
        )

    def book_logo(x, y, scale=1):
        stroke((0.0, 0.32, 1.0))
        ops.append(f'{1.2 * scale} w')
        left = (
            f'{x} {y} m '
            f'{x + 5 * scale} {y + 2 * scale} l '
            f'{x + 5 * scale} {y + 12 * scale} l '
            f'{x} {y + 10 * scale} l h S'
        )
        right = (
            f'{x + 10 * scale} {y} m '
            f'{x + 5 * scale} {y + 2 * scale} l '
            f'{x + 5 * scale} {y + 12 * scale} l '
            f'{x + 10 * scale} {y + 10 * scale} l h S'
        )
        ops.extend([left, right])

    def line(x1, y1, x2, y2, rgb=(0.16, 0.16, 0.18), width=1):
        stroke(rgb)
        ops.append(f'{width} w')
        ops.append(f'{x1} {y1} m {x2} {y2} l S')

    def text(x, y, value, size=10, rgb=(1, 1, 1), bold=False):
        fill(rgb)
        font = 'F2' if bold else 'F1'
        ops.append(f'BT /{font} {size} Tf {x} {y} Td ({_pdf_safe_text(value)}) Tj ET')

    def amount_text(y, amount):
        text(485, y, _format_pdf_money(amount), 9, (1, 1, 1), True)

    # Fondo y tarjeta principal, replicando el ticket oscuro del frontend.
    rect(0, 0, 595, 842, (0.04, 0.04, 0.045))
    rounded_rect(48, 34, 499, 774, 10, (0.075, 0.075, 0.075), (0.22, 0.22, 0.24), 1)

    # Cabecera azul oscuro.
    top_rounded_rect(48, 722, 499, 86, 10, (0.07, 0.09, 0.16))
    line(48, 722, 547, 722, (0.19, 0.19, 0.22), 1)
    book_logo(74, 770, 0.95)
    text(94, 773, 'academix', 13, (1, 1, 1), True)
    text(74, 752, 'Comprobante de matrícula', 9, (0.78, 0.80, 0.86))

    text(477, 780, 'Receipt #', 7, (0.78, 0.80, 0.86))
    text(493, 763, f"#{enrollment.get('id') or '-'}", 13, (1, 1, 1), True)
    text(489, 745, _format_pdf_date(fee.get('paid_at') or enrollment.get('enrolled_at')), 8, (0.78, 0.80, 0.86))

    y = 690
    text(74, y, 'STUDENT', 7, (0.72, 0.72, 0.76), True)
    text(74, y - 18, student.get('full_name') or '-', 10, (1, 1, 1), True)
    text(74, y - 33, student.get('email') or '-', 9, (0.82, 0.84, 0.88))
    text(74, y - 48, f"DNI: {student.get('dni') or student.get('id') or '-'}", 7, (0.82, 0.84, 0.88))

    line(74, 638, 520, 638, (0.17, 0.17, 0.18), 1)

    text(74, 612, 'Career', 7, (0.72, 0.72, 0.76))
    text(74, 599, _truncate_pdf_text(career.get('name') or '-', 32), 9, (1, 1, 1), True)
    text(274, 612, 'Period', 7, (0.72, 0.72, 0.76))
    text(274, 599, _truncate_pdf_text(period.get('name') or '-', 24), 9, (1, 1, 1), True)
    text(74, 574, 'Fecha de matrícula', 7, (0.72, 0.72, 0.76))
    text(74, 561, _format_pdf_date(enrollment.get('enrolled_at')), 9, (1, 1, 1), True)
    text(274, 574, 'Estado', 7, (0.72, 0.72, 0.76))
    text(274, 561, 'Active' if enrollment.get('status') == 'active' else str(enrollment.get('status') or '-').title(), 9, (0.15, 0.95, 0.55), True)

    line(74, 536, 520, 536, (0.17, 0.17, 0.18), 1)
    text(74, 508, 'FEE DETAILS', 7, (0.72, 0.72, 0.76), True)

    y = 489
    for item in fee.get('line_items') or []:
        if y < 300:
            text(74, y, 'Detalle truncado. Consulta el ticket web para ver todas las líneas.', 8, (0.85, 0.72, 0.35))
            y -= 18
            break
        if item.get('type') == 'subject':
            label = _truncate_pdf_text(
                f"{item.get('subject_code', '')} {item.get('subject_name') or item.get('label') or 'Asignatura'}".strip(),
                42,
            )
            text(74, y, label, 9, (1, 1, 1))
            amount_text(y, item.get('subtotal') or '0.00')
            y -= 13
            text(74, y, f"{item.get('credits') or 0} ECTS × {_format_pdf_money(item.get('price_per_credit'))}/crédito", 7, (0.70, 0.72, 0.76))
            y -= 16
        else:
            text(74, y, _truncate_pdf_text(item.get('label') or 'Cargo administrativo', 42), 9, (0.88, 0.90, 0.94))
            amount_text(y, item.get('subtotal') or item.get('amount') or '0.00')
            y -= 18

    discount = Decimal(str(fee.get('discount_amount') or '0'))
    if discount > Decimal('0.00'):
        text(74, y, f"Descuento {fee.get('discount_reason') or ''}", 9, (0.15, 0.95, 0.55))
        text(485, y, f"-{_format_pdf_money(discount)}", 9, (0.15, 0.95, 0.55), True)
        y -= 18

    line(74, y + 4, 520, y + 4, (0.22, 0.22, 0.24), 1)
    text(74, y - 15, 'Total Paid', 10, (1, 1, 1), True)
    amount_text(y - 15, fee.get('final_amount') or '0.00')

    y -= 48
    line(74, y + 10, 520, y + 10, (0.17, 0.17, 0.18), 1)
    text(74, y - 14, 'ENROLLED CLASSES', 7, (0.72, 0.72, 0.76), True)
    y -= 34

    for cls in data.get('classes') or []:
        if y < 86:
            text(74, y, 'Lista truncada. Consulta el ticket web para ver todas las asignaturas.', 8, (0.85, 0.72, 0.35))
            y -= 14
            break
        text(74, y, _truncate_pdf_text(cls.get('subject_name') or 'Asignatura', 42), 9, (1, 1, 1), True)
        teacher = cls.get('teacher_name') or ''
        if teacher:
            text(432, y, _truncate_pdf_text(teacher, 22), 7, (0.82, 0.84, 0.88))
        y -= 22
        line(74, y + 8, 520, y + 8, (0.13, 0.13, 0.14), 0.5)

    line(74, 78, 520, 78, (0.17, 0.17, 0.18), 1)
    text(74, 54, 'This document serves as official proof of enrollment.', 8, (0.82, 0.84, 0.88))
    rounded_rect(472, 45, 48, 20, 10, (0.75, 1.0, 0.85))
    text(483, 51, 'Valid', 8, (0.02, 0.40, 0.18), True)

    return _build_pdf_document(ops)


class EnrollmentReceiptView(generics.RetrieveAPIView):
    """GET /api/enrollment/career-enrollments/<pk>/receipt/"""
    permission_classes = [IsAuthenticated]

    def retrieve(self, request, *args, **kwargs):
        enrollment, error = _get_enrollment_for_receipt(request, self.kwargs['pk'])
        if error:
            return error
        return Response(_build_enrollment_receipt_data(enrollment))


class EnrollmentReceiptPdfView(APIView):
    """GET /api/enrollment/career-enrollments/<pk>/receipt.pdf/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk=None):
        enrollment, error = _get_enrollment_for_receipt(request, pk)
        if error:
            return error

        data = _build_enrollment_receipt_data(enrollment)
        fee = data.get('fee') or {}
        if fee.get('status') not in ('paid', 'exempted'):
            return Response(
                {"detail": "Solo puedes descargar el ticket PDF cuando la matrícula está pagada."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pdf = _build_designed_receipt_pdf(data)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="ticket-matricula-{enrollment.pk}.pdf"'
        return response


class ClassEnrollmentCreateDeleteView(generics.GenericAPIView):
    """
    GET    /api/enrollment/class-enrollments/         — listar inscripciones del estudiante
    POST   /api/enrollment/class-enrollments/         — inscribir en clase
    DELETE /api/enrollment/class-enrollments/<pk>/    — dar de baja
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ClassEnrollmentSerializer

    def get(self, request, *args, **kwargs):
        user = request.user
        qs = ClassEnrollment.objects.select_related(
            'student', 'cls__subject', 'cls__teacher', 'cls__classroom', 'cls__period'
        ).prefetch_related('cls__schedules')
        if user.role not in ('m', 'a'):
            qs = qs.filter(student=user, status__in=['enrolled', 'waitlisted'])
        serializer = ClassEnrollmentSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        from academic.models import Class, ClassSchedule

        if request.user.role != 's':
            return Response({"detail": "Solo estudiantes pueden inscribirse en clases."}, status=status.HTTP_403_FORBIDDEN)

        class_id = request.data.get('class_id')
        if not class_id:
            return Response({"detail": "class_id es requerido."}, status=status.HTTP_400_BAD_REQUEST)

        cls = get_object_or_404(
            Class.objects.select_related('subject__career', 'period', 'classroom').prefetch_related('schedules'),
            pk=class_id
        )

        # Verificar que tiene CareerEnrollment iniciada para la carrera.
        # El pago se realiza DESPUÉS de elegir asignaturas, así que durante la
        # selección la matrícula está en pending, no active.
        has_enrollment = CareerEnrollment.objects.filter(
            student=request.user,
            career=cls.subject.career,
            period=cls.period,
            status__in=['pending', 'active'],
        ).exists()

        if not has_enrollment:
            return Response(
                {"detail": "No tienes una matrícula iniciada para la titulación de esta clase."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Verificar duplicado
        if ClassEnrollment.objects.filter(student=request.user, cls=cls).exists():
            return Response({"detail": "Ya estás inscripto en esta clase."}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar solapamiento de horarios
        enrolled_classes = ClassEnrollment.objects.filter(
            student=request.user,
            cls__period=cls.period,
            status='enrolled',
        ).select_related('cls').prefetch_related('cls__schedules')

        new_schedules = cls.schedules.all()
        DAY_NAMES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

        for enrolled_ce in enrolled_classes:
            for existing_schedule in enrolled_ce.cls.schedules.all():
                for new_schedule in new_schedules:
                    if existing_schedule.day_of_week == new_schedule.day_of_week:
                        # Verificar solapamiento de horas
                        if not (new_schedule.end_time <= existing_schedule.start_time or
                                new_schedule.start_time >= existing_schedule.end_time):
                            day_name = DAY_NAMES[existing_schedule.day_of_week] if existing_schedule.day_of_week < 7 else str(existing_schedule.day_of_week)
                            return Response(
                                {
                                    "detail": (
                                        f"Solapamiento de horarios: la clase {cls.subject.name} "
                                        f"({day_name} {new_schedule.start_time}-{new_schedule.end_time}) "
                                        f"solapa con {enrolled_ce.cls.subject.name} "
                                        f"({day_name} {existing_schedule.start_time}-{existing_schedule.end_time})."
                                    )
                                },
                                status=status.HTTP_400_BAD_REQUEST
                            )

        # Verificar disponibilidad
        enrolled_count = ClassEnrollment.objects.filter(cls=cls, status='enrolled').count()
        if cls.classroom and cls.classroom.capacity:
            capacity = min(cls.classroom.capacity, cls.max_students)
        else:
            capacity = cls.max_students or 30

        if enrolled_count >= capacity:
            ce = ClassEnrollment.objects.create(
                student=request.user,
                cls=cls,
                status='waitlisted',
            )
            return Response(
                {
                    "detail": "No hay plazas disponibles. Has sido agregado a la lista de espera.",
                    "status": "waitlisted",
                    "id": ce.pk,
                },
                status=status.HTTP_201_CREATED
            )

        ce = ClassEnrollment.objects.create(
            student=request.user,
            cls=cls,
            status='enrolled',
        )

        serializer = ClassEnrollmentSerializer(ce)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk=None, *args, **kwargs):
        from django.utils import timezone

        ce = get_object_or_404(ClassEnrollment, pk=pk, student=request.user)

        if ce.status == 'dropped':
            return Response({"detail": "Ya estás dado de baja de esta clase."}, status=status.HTTP_400_BAD_REQUEST)

        # Verificar período de modificación
        period = ce.cls.period
        if hasattr(period, 'enrollment_modification_deadline') and period.enrollment_modification_deadline:
            if timezone.now().date() > period.enrollment_modification_deadline:
                return Response(
                    {"detail": "El período de modificación de matrícula ha cerrado."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        was_enrolled = ce.status == 'enrolled'
        ce.status = 'dropped'
        ce.save(update_fields=['status'])

        # Si había waitlisted, promover al primero
        if was_enrolled:
            next_waitlisted = ClassEnrollment.objects.filter(
                cls=ce.cls, status='waitlisted'
            ).order_by('enrolled_at').first()

            if next_waitlisted:
                next_waitlisted.status = 'enrolled'
                next_waitlisted.save(update_fields=['status'])
                create_notification(
                    user=next_waitlisted.student,
                    title='Plaza disponible',
                    message=f'Se liberó una plaza en {ce.cls.subject.name}. Ya estás inscripto.',
                    notif_type='info',
                    event_type='class_waitlist_promoted',
                    context={
                        'subject_name': ce.cls.subject.name,
                        'class_name': str(ce.cls),
                    },
                )

        return Response(status=status.HTTP_204_NO_CONTENT)


class EnrollmentCompleteView(generics.GenericAPIView):
    """
    POST /api/enrollment/career-enrollments/<pk>/complete/
    Recalcula el pago de matrícula después de elegir asignaturas.
    No activa la matrícula: la activación ocurre al pagar (Stripe en producción,
    pago simulado en desarrollo).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        enrollment = get_object_or_404(CareerEnrollment, pk=self.kwargs['pk'])

        if request.user.role not in ('m', 'a') and enrollment.student != request.user:
            return Response({"detail": "No tienes permiso."}, status=status.HTTP_403_FORBIDDEN)

        if enrollment.status not in ('pending', 'active'):
            return Response(
                {"detail": "Solo se puede finalizar una matrícula pendiente o activa."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Comprueba que el estudiante tenga al menos una clase matriculada
        enrolled_classes = ClassEnrollment.objects.filter(
            student=enrollment.student,
            cls__period=enrollment.period,
            cls__subject__career=enrollment.career,
            status='enrolled',
        ).count()

        if enrolled_classes == 0:
            return Response(
                {"detail": "Debés inscribirte en al menos una materia antes de completar la matrícula."},
                status=status.HTTP_400_BAD_REQUEST
            )

        fee = refresh_enrollment_fee(enrollment)

        if fee.final_amount <= Decimal('0.00'):
            _mark_enrollment_exempted(enrollment, fee)

        return Response({
            'enrollment': CareerEnrollmentSerializer(enrollment).data,
            'fee': EnrollmentFeeSerializer(fee).data,
            'next_step': 'payment' if fee.status == 'pending' else 'receipt',
        })
