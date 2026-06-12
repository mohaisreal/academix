from rest_framework.views import APIView
from rest_framework import generics, status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal
import unicodedata

from .models import CareerEnrollment, ClassEnrollment, EnrollmentFee
from .models import ExceptionalConvocationGrace
from .serializers import CareerEnrollmentSerializer, ClassEnrollmentSerializer, EnrollmentFeeSerializer
from .services import refresh_enrollment_fee, resolve_convocation_eligibility
from backend.settings import _stripe_credentials_prefix_mismatch
from academic.models import AcademicPeriod
from academic.schedule_source import (
    canonical_assignment_map_for_period,
    resolve_assignment_teacher_for_class,
    schedules_overlap,
)
from notifications.utils import create_notification
from shared.permissions import IsAdminOrManagement, IsStudent
from shared.periods import get_active_academic_period

User = get_user_model()


def _resolve_assignment_teacher_name(cls):
    teacher = resolve_assignment_teacher_for_class(cls)
    if not teacher:
        return None
    return teacher.get_full_name() or teacher.username


def _is_production_stripe_enabled():
    return getattr(settings, 'STRIPE_PAYMENT_MODE', 'demo') == 'stripe_live' and not settings.DEBUG and getattr(settings, 'STRIPE_LIVE_PAYMENTS_ENABLED', False)


def _stripe_payment_mode():
    mode = getattr(settings, 'STRIPE_PAYMENT_MODE', 'demo')
    if mode in ('demo', 'stripe_test', 'stripe_live'):
        return mode
    return 'demo'


def _stripe_payment_config_is_valid(mode: str, stripe_key: str, publishable_key: str, webhook_secret: str):
    if mode == 'stripe_test' and (not stripe_key or not publishable_key or not webhook_secret):
        return False
    if mode == 'stripe_live' and not stripe_key:
        return False
    if mode in ('stripe_test', 'stripe_live') and _stripe_credentials_prefix_mismatch(mode, stripe_key, publishable_key):
        return False
    return True


def _amount_to_minor_units(amount):
    return int((Decimal(str(amount)) * Decimal('100')).quantize(Decimal('1')))


def _get_stripe_module():
    try:
        import stripe as stripe_lib
    except ImportError:
        return None
    stripe_lib.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
    return stripe_lib


def _create_stripe_payment_intent(stripe_lib, fee, enrollment):
    return stripe_lib.PaymentIntent.create(
        amount=_amount_to_minor_units(fee.final_amount),
        currency='eur',
        automatic_payment_methods={'enabled': True},
        metadata={
            'enrollment_fee_id': str(fee.pk),
            'career_enrollment_id': str(enrollment.pk),
            'student_id': str(enrollment.student_id),
            'source': 'enrollment',
            'payment_mode': _stripe_payment_mode(),
        },
        description=f'Matrícula {enrollment.career.name} - {enrollment.period.name}',
    )


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


def _apply_stripe_payment_result(enrollment, fee, stripe_status, intent_id=None):
    if intent_id:
        fee.stripe_payment_intent_id = intent_id

    if stripe_status == 'succeeded':
        fee.stripe_payment_status = 'paid'
        fee.status = 'paid'
        fee.save(update_fields=['stripe_payment_intent_id', 'stripe_payment_status', 'status'])
        _mark_enrollment_paid(enrollment, fee)
    elif stripe_status in ('requires_payment_method', 'canceled'):
        fee.status = 'failed'
        fee.stripe_payment_status = 'failed'
        fee.save(update_fields=['stripe_payment_intent_id', 'status', 'stripe_payment_status'])
    else:
        fee.stripe_payment_status = 'pending'
        fee.save(update_fields=['stripe_payment_intent_id', 'stripe_payment_status'])


class MyEnrollmentView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        active_period = get_active_academic_period()
        career_enrollment = (
            CareerEnrollment.objects
            .filter(student=request.user, status__in=['active', 'completed'])
            .order_by('-period__is_active', '-period__start_date', '-period_id', '-id')
            .select_related('career', 'period')
            .first()
        )
        if active_period:
            current_enrollment = (
                CareerEnrollment.objects
                .filter(student=request.user, status__in=['active', 'completed'], period_id=active_period.id)
                .select_related('career', 'period')
                .first()
            )
            if current_enrollment:
                career_enrollment = current_enrollment
        if not career_enrollment:
            return Response({'id': None, 'classes': [], 'current_period': None})

        class_enrollments = (
            ClassEnrollment.objects
            .filter(student=request.user, cls__period=career_enrollment.period, status='enrolled')
            .select_related('cls__subject', 'cls__teacher', 'cls__classroom', 'cls__period')
            .prefetch_related('cls__schedules')
        )

        classes = []
        assignment_map = canonical_assignment_map_for_period(
            career_enrollment.period_id,
            [ce.cls_id for ce in class_enrollments],
        )
        for ce in class_enrollments:
            cls = ce.cls
            t = resolve_assignment_teacher_for_class(cls, assignment_map)
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
            'current_period': _current_period_payload(career_enrollment.period),
            'enrolled_at': career_enrollment.enrolled_at.isoformat() if career_enrollment.enrolled_at else None,
            'classes': classes,
        })


class MySubjectsView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        from grades.models import Grade, Evaluation
        from grades.services import resolve_class_final_grade
        active_period = get_active_academic_period()
        if not active_period:
            return Response([])
        enrollments = (
            ClassEnrollment.objects
            .filter(student=request.user, status='enrolled')
            .select_related('cls__subject', 'cls__teacher', 'cls__classroom', 'cls__period')
            .prefetch_related('cls__schedules')
        )
        enrollments = enrollments.filter(cls__period=active_period)

        result = []
        assignment_map = canonical_assignment_map_for_period(
            active_period.id,
            [enr.cls_id for enr in enrollments],
        )
        for enr in enrollments:
            resolved = resolve_class_final_grade(request.user, enr.cls)
            t = resolve_assignment_teacher_for_class(enr.cls, assignment_map) if assignment_map is not None else enr.cls.teacher
            result.append({
                'enrollment_id': enr.id,
                'class_id': enr.cls.id,
                'subject_name': enr.cls.subject.name,
                'subject_code': enr.cls.subject.code,
                'credits': enr.cls.subject.credits,
                'teacher_name': (f"{t.first_name} {t.last_name}".strip() or t.username) if t else None,
                'period_name': enr.cls.period.name,
                'classroom': str(enr.cls.classroom) if enr.cls.classroom else None,
                'current_grade': float(resolved['final_grade']) if resolved['final_grade'] is not None and resolved['final_grade_visible'] else None,
                'final_grade_visible': resolved['final_grade_visible'],
                'passed': resolved['passed'],
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
        active_period = get_active_academic_period()
        if not active_period:
            return Response([])
        enrollments = (
            ClassEnrollment.objects
            .filter(student=request.user, status='enrolled')
            .select_related('cls__teacher', 'cls__subject', 'cls__period')
        )
        enrollments = enrollments.filter(cls__period=active_period)

        teachers_map = {}
        assignment_map = canonical_assignment_map_for_period(
            active_period.id,
            [enr.cls_id for enr in enrollments],
        )
        for enr in enrollments:
            t = resolve_assignment_teacher_for_class(enr.cls, assignment_map) if assignment_map is not None else enr.cls.teacher
            if not t:
                continue
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

        mode = _stripe_payment_mode()
        if mode == 'demo':
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
        publishable_key = getattr(settings, 'STRIPE_PUBLIC_KEY', '')
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        if not _stripe_payment_config_is_valid(mode, stripe_key, publishable_key, webhook_secret):
            return Response(
                {'detail': 'Stripe no está configurado para el modo de pruebas.' if mode == 'stripe_test' else 'Stripe no está configurado para pagos de producción.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        stripe_lib = _get_stripe_module()
        if stripe_lib is None:
            return Response(
                {'detail': 'Stripe SDK no está instalado.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            intent = _create_stripe_payment_intent(stripe_lib, fee, enrollment)
        except Exception as exc:
            return Response(
                {'detail': f'Error de Stripe: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        fee.stripe_payment_intent_id = intent['id']
        fee.stripe_payment_status = 'pending'
        fee.save(update_fields=['stripe_payment_intent_id', 'stripe_payment_status'])

        return Response({
            'mode': mode,
            'client_secret': intent.get('client_secret'),
            'amount': str(fee.final_amount),
            'currency': 'eur',
            'fee': EnrollmentFeeSerializer(fee).data,
        })


class EnrollmentConfirmPaymentView(generics.GenericAPIView):
    """POST /api/enrollment/career-enrollments/<pk>/confirm-payment/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)

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

        mode = _stripe_payment_mode()
        if mode == 'demo':
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
        _apply_stripe_payment_result(enrollment, fee, stripe_status)

        return Response({
            'status': fee.status,
            'stripe_status': stripe_status,
            'enrollment': CareerEnrollmentSerializer(enrollment).data,
            'fee': EnrollmentFeeSerializer(fee).data,
        })


class EnrollmentStripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        mode = _stripe_payment_mode()
        if mode not in ('stripe_test', 'stripe_live'):
            return HttpResponse(status=204)

        stripe_lib = _get_stripe_module()
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        if stripe_lib is None or not webhook_secret:
            return Response({'detail': 'Stripe webhook is not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        try:
            event = stripe_lib.Webhook.construct_event(payload, sig_header, webhook_secret)
        except Exception:
            return HttpResponse(status=400)

        event_type = event.get('type')
        intent = event.get('data', {}).get('object', {})
        if event_type not in ('payment_intent.succeeded', 'payment_intent.payment_failed'):
            return HttpResponse(status=200)

        fee_id = (intent.get('metadata') or {}).get('enrollment_fee_id')
        enrollment_id = (intent.get('metadata') or {}).get('career_enrollment_id')
        metadata = intent.get('metadata') or {}
        if not all(metadata.get(field) for field in ('source', 'payment_mode', 'student_id')):
            return HttpResponse(status=200)
        try:
            fee = EnrollmentFee.objects.select_related('career_enrollment').get(pk=fee_id) if fee_id else None
            enrollment = fee.career_enrollment if fee else CareerEnrollment.objects.get(pk=enrollment_id)
        except (EnrollmentFee.DoesNotExist, CareerEnrollment.DoesNotExist, TypeError, ValueError):
            return HttpResponse(status=200)

        if fee is None:
            fee = EnrollmentFee.objects.get(career_enrollment=enrollment)

        if intent.get('id') != fee.stripe_payment_intent_id:
            return HttpResponse(status=200)

        if metadata.get('source') != 'enrollment' or metadata.get('payment_mode') != mode or metadata.get('student_id') != str(enrollment.student_id):
            return HttpResponse(status=200)

        _apply_stripe_payment_result(
            enrollment,
            fee,
            'succeeded' if event_type == 'payment_intent.succeeded' else 'requires_payment_method',
            intent.get('id'),
        )
        return HttpResponse(status=200)


class EnrollmentStripeConfigView(APIView):
    """GET /api/enrollment/stripe/config/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        mode = _stripe_payment_mode()
        return Response({
            'mode': mode,
            'live_mode': mode == 'stripe_live',
            'publishable_key': getattr(settings, 'STRIPE_PUBLIC_KEY', '') if mode != 'demo' else '',
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


def _current_period_payload(period):
    if not period:
        return None
    return {'id': period.id, 'name': period.name, 'code': period.code}


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
            'teacher_name': _resolve_assignment_teacher_name(cls),
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
        text(485, y, _format_pdf_money(amount), 9, (0.09, 0.11, 0.16), True)

    # Fondo y tarjeta principal, alineados con la estética clara del frontend.
    rect(0, 0, 595, 842, (0.98, 0.98, 0.99))
    rounded_rect(48, 34, 499, 774, 10, (1.0, 1.0, 1.0), (0.88, 0.89, 0.92), 1)

    # Cabecera clara.
    top_rounded_rect(48, 722, 499, 86, 10, (0.94, 0.97, 1.0))
    line(48, 722, 547, 722, (0.88, 0.89, 0.92), 1)
    book_logo(74, 770, 0.95)
    text(94, 773, 'academix', 13, (0.09, 0.11, 0.16), True)
    text(74, 752, 'Comprobante de matrícula', 9, (0.39, 0.43, 0.51))

    text(477, 780, 'Receipt #', 7, (0.39, 0.43, 0.51))
    text(493, 763, f"#{enrollment.get('id') or '-'}", 13, (0.09, 0.11, 0.16), True)
    text(489, 745, _format_pdf_date(fee.get('paid_at') or enrollment.get('enrolled_at')), 8, (0.39, 0.43, 0.51))

    y = 690
    text(74, y, 'STUDENT', 7, (0.39, 0.43, 0.51), True)
    text(74, y - 18, student.get('full_name') or '-', 10, (0.09, 0.11, 0.16), True)
    text(74, y - 33, student.get('email') or '-', 9, (0.35, 0.39, 0.47))
    text(74, y - 48, f"DNI: {student.get('dni') or student.get('id') or '-'}", 7, (0.35, 0.39, 0.47))

    line(74, 638, 520, 638, (0.88, 0.89, 0.92), 1)

    text(74, 612, 'Career', 7, (0.39, 0.43, 0.51))
    text(74, 599, _truncate_pdf_text(career.get('name') or '-', 32), 9, (0.09, 0.11, 0.16), True)
    text(274, 612, 'Period', 7, (0.39, 0.43, 0.51))
    text(274, 599, _truncate_pdf_text(period.get('name') or '-', 24), 9, (0.09, 0.11, 0.16), True)
    text(74, 574, 'Fecha de matrícula', 7, (0.39, 0.43, 0.51))
    text(74, 561, _format_pdf_date(enrollment.get('enrolled_at')), 9, (0.09, 0.11, 0.16), True)
    text(274, 574, 'Estado', 7, (0.39, 0.43, 0.51))
    text(274, 561, 'Active' if enrollment.get('status') == 'active' else str(enrollment.get('status') or '-').title(), 9, (0.02, 0.51, 0.28), True)

    line(74, 536, 520, 536, (0.88, 0.89, 0.92), 1)
    text(74, 508, 'FEE DETAILS', 7, (0.39, 0.43, 0.51), True)

    y = 489
    for item in fee.get('line_items') or []:
        if y < 300:
            text(74, y, 'Detalle truncado. Consulta el ticket web para ver todas las líneas.', 8, (0.67, 0.48, 0.13))
            y -= 18
            break
        if item.get('type') == 'subject':
            label = _truncate_pdf_text(
                f"{item.get('subject_code', '')} {item.get('subject_name') or item.get('label') or 'Asignatura'}".strip(),
                42,
            )
            text(74, y, label, 9, (0.09, 0.11, 0.16))
            amount_text(y, item.get('subtotal') or '0.00')
            y -= 13
            text(74, y, f"{item.get('credits') or 0} ECTS × {_format_pdf_money(item.get('price_per_credit'))}/crédito", 7, (0.70, 0.72, 0.76))
            y -= 16
        else:
            text(74, y, _truncate_pdf_text(item.get('label') or 'Cargo administrativo', 42), 9, (0.09, 0.11, 0.16))
            amount_text(y, item.get('subtotal') or item.get('amount') or '0.00')
            y -= 18

    discount = Decimal(str(fee.get('discount_amount') or '0'))
    if discount > Decimal('0.00'):
        text(74, y, f"Descuento {fee.get('discount_reason') or ''}", 9, (0.02, 0.51, 0.28))
        text(485, y, f"-{_format_pdf_money(discount)}", 9, (0.02, 0.51, 0.28), True)
        y -= 18

    line(74, y + 4, 520, y + 4, (0.88, 0.89, 0.92), 1)
    text(74, y - 15, 'Total Paid', 10, (0.09, 0.11, 0.16), True)
    amount_text(y - 15, fee.get('final_amount') or '0.00')

    y -= 48
    line(74, y + 10, 520, y + 10, (0.88, 0.89, 0.92), 1)
    text(74, y - 14, 'ENROLLED CLASSES', 7, (0.39, 0.43, 0.51), True)
    y -= 34

    for cls in data.get('classes') or []:
        if y < 86:
            text(74, y, 'Lista truncada. Consulta el ticket web para ver todas las asignaturas.', 8, (0.67, 0.48, 0.13))
            y -= 14
            break
        text(74, y, _truncate_pdf_text(cls.get('subject_name') or 'Asignatura', 42), 9, (0.09, 0.11, 0.16), True)
        teacher = cls.get('teacher_name') or ''
        if teacher:
            text(432, y, _truncate_pdf_text(teacher, 22), 7, (0.35, 0.39, 0.47))
        y -= 22
        line(74, y + 8, 520, y + 8, (0.13, 0.13, 0.14), 0.5)

    line(74, 78, 520, 78, (0.88, 0.89, 0.92), 1)
    text(74, 54, 'This document serves as official proof of enrollment.', 8, (0.35, 0.39, 0.47))
    rounded_rect(472, 45, 48, 20, 10, (0.88, 0.97, 0.91))
    text(483, 51, 'Valid', 8, (0.02, 0.51, 0.28), True)

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
        class_ids = [row.cls_id for row in qs]
        assignment_map = {}
        if class_ids:
            period_id = qs.first().cls.period_id
            assignment_map = canonical_assignment_map_for_period(period_id, class_ids)
        serializer = ClassEnrollmentSerializer(qs, many=True, context={'canonical_assignment_map': assignment_map})
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        from academic.models import Class

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

        eligibility = resolve_convocation_eligibility(request.user, cls.subject, cls.period)
        if eligibility['convocation_eligibility'] == 'blocked':
            # Las asignaturas bloqueadas siguen visibles en la matrícula, pero el POST se rechaza antes de validar cupo/horario.
            return Response(
                {
                    'code': 'convocation_blocked',
                    'detail': 'Límite de convocatorias alcanzado.',
                    **eligibility,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        assignment_map = canonical_assignment_map_for_period(cls.period_id, [cls.id])
        target_assignment = assignment_map.get(cls.id)
        if not target_assignment:
            return Response(
                {
                    "code": "schedule_unavailable",
                    "detail": "La clase no tiene horario publicado disponible.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verificar solapamiento de horarios
        enrolled_classes = ClassEnrollment.objects.filter(
            student=request.user,
            cls__period=cls.period,
            status='enrolled',
        ).select_related('cls')

        enrolled_class_ids = [ce.cls_id for ce in enrolled_classes]
        enrolled_assignment_map = canonical_assignment_map_for_period(cls.period_id, enrolled_class_ids)
        DAY_NAMES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

        for enrolled_ce in enrolled_classes:
            existing_assignment = enrolled_assignment_map.get(enrolled_ce.cls_id)
            if not existing_assignment:
                continue
            if schedules_overlap(existing_assignment, target_assignment):
                day_name = DAY_NAMES[existing_assignment.slot.day_of_week] if existing_assignment.slot.day_of_week < 7 else str(existing_assignment.slot.day_of_week)
                return Response(
                    {
                        "detail": (
                            f"Solapamiento de horarios: la clase {cls.subject.name} "
                            f"({day_name} {target_assignment.slot.start_time}-{target_assignment.slot.end_time}) "
                            f"solapa con {enrolled_ce.cls.subject.name} "
                            f"({day_name} {existing_assignment.slot.start_time}-{existing_assignment.slot.end_time})."
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

        # Verificar periodo de modificación
        period = ce.cls.period
        if hasattr(period, 'enrollment_modification_deadline') and period.enrollment_modification_deadline:
            if timezone.now().date() > period.enrollment_modification_deadline:
                return Response(
                    {"detail": "El periodo de modificación de matrícula ha cerrado."},
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


class ConvocationGraceGrantView(APIView):
    permission_classes = [IsAdminOrManagement]

    def get(self, request, student_id):
        period_id = request.query_params.get('period')
        if not period_id:
            return Response({'detail': 'period es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

        student = get_object_or_404(User, pk=student_id, role='s')
        from academic.models import AcademicPeriod, Class

        period = get_object_or_404(AcademicPeriod, pk=period_id)
        career_enrollment = CareerEnrollment.objects.filter(student=student, period=period).select_related('career', 'period').first()
        if not career_enrollment:
            return Response({'detail': 'La matrícula de carrera no existe para ese periodo.'}, status=status.HTTP_404_NOT_FOUND)

        classes = (
            Class.objects.filter(subject__career=career_enrollment.career, period=period)
            .select_related('subject')
            .order_by('subject__name', 'id')
        )
        subjects = []
        seen_subject_ids = set()
        for cls in classes:
            if cls.subject_id in seen_subject_ids:
                continue
            seen_subject_ids.add(cls.subject_id)
            eligibility = resolve_convocation_eligibility(student, cls.subject, period)
            grace = ExceptionalConvocationGrace.objects.filter(
                student=student,
                subject=cls.subject,
                period=period,
            ).values('id', 'is_active').first()
            subjects.append({
                'id': cls.subject.id,
                'name': cls.subject.name,
                'code': cls.subject.code,
                **eligibility,
                'grace': grace,
            })

        return Response({
            'student': {'id': student.id, 'full_name': student.get_full_name() or student.username},
            'period': {'id': period.id, 'name': period.name},
            'career': {'id': career_enrollment.career.id, 'name': career_enrollment.career.name},
            'subjects': subjects,
        })

    def post(self, request, student_id):
        student = get_object_or_404(User, pk=student_id, role='s')
        subject_id = request.data.get('subject_id')
        period_id = request.data.get('period_id')
        reason = (request.data.get('reason') or '').strip()
        if not subject_id or not period_id or not reason:
            return Response({'detail': 'subject_id, period_id y reason son requeridos.'}, status=status.HTTP_400_BAD_REQUEST)

        from academic.models import Subject, AcademicPeriod
        subject = get_object_or_404(Subject, pk=subject_id)
        period = get_object_or_404(AcademicPeriod, pk=period_id)

        grace, created = ExceptionalConvocationGrace.objects.get_or_create(
            student=student,
            subject=subject,
            period=period,
            defaults={'granted_by': request.user, 'reason': reason, 'is_active': True},
        )
        if not created:
            grace.granted_by = request.user
            grace.reason = reason
            grace.is_active = True
            grace.save(update_fields=['granted_by', 'reason', 'is_active', 'updated_at'])

        eligibility = resolve_convocation_eligibility(student, subject, period)
        return Response({'grace': {'id': grace.id, 'is_active': grace.is_active}, **eligibility}, status=status.HTTP_201_CREATED)


class ConvocationGraceDetailView(APIView):
    permission_classes = [IsAdminOrManagement]

    def patch(self, request, pk):
        grace = get_object_or_404(ExceptionalConvocationGrace, pk=pk)
        if 'is_active' not in request.data:
            return Response({'detail': 'is_active es requerido.'}, status=status.HTTP_400_BAD_REQUEST)
        grace.is_active = bool(request.data.get('is_active'))
        grace.save(update_fields=['is_active', 'updated_at'])
        eligibility = resolve_convocation_eligibility(grace.student, grace.subject, grace.period)
        return Response({'grace': {'id': grace.id, 'is_active': grace.is_active}, **eligibility})


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

        mode = _stripe_payment_mode()

        if fee.final_amount <= Decimal('0.00'):
            _mark_enrollment_exempted(enrollment, fee)

        payload = {
            'enrollment': CareerEnrollmentSerializer(enrollment).data,
            'fee': EnrollmentFeeSerializer(fee).data,
            'next_step': 'payment' if fee.status == 'pending' else 'receipt',
        }
        if mode == 'stripe_test' and fee.status == 'pending':
            stripe_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
            publishable_key = getattr(settings, 'STRIPE_PUBLIC_KEY', '')
            webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
            if not _stripe_payment_config_is_valid(mode, stripe_key, publishable_key, webhook_secret):
                return Response(
                    {'detail': 'Stripe no está configurado para el modo de pruebas.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            stripe_lib = _get_stripe_module()
            if stripe_lib is None:
                return Response(
                    {'detail': 'Stripe SDK no está instalado.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            try:
                intent = _create_stripe_payment_intent(stripe_lib, fee, enrollment)
            except Exception as exc:
                return Response(
                    {'detail': f'Error de Stripe: {exc}'},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            fee.stripe_payment_intent_id = intent['id']
            fee.stripe_payment_status = 'pending'
            fee.save(update_fields=['stripe_payment_intent_id', 'stripe_payment_status'])
            payload['mode'] = mode
            payload['client_secret'] = intent.get('client_secret')
            payload['currency'] = 'eur'
        return Response(payload)
