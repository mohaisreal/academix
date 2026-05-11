import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status

logger = logging.getLogger(__name__)
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from .models import (
    Question,
    QuestionAnswer,
    QuestionnaireResponse,
    QuestionnaireStep,
    Questionnaire,
    QuestionOption,
)
from .permissions import IsAdminOrManagement, IsStudent
from .serializers import (
    QuestionAnswerSerializer,
    QuestionnaireListSerializer,
    QuestionnaireResponseSerializer,
    QuestionnaireSerializer,
    QuestionnaireStepSerializer,
    QuestionnaireStepWriteSerializer,
    QuestionnaireWriteSerializer,
    QuestionOptionSerializer,
    QuestionOptionWriteSerializer,
    QuestionSerializer,
    QuestionWriteSerializer,
    ResponseUpdateSerializer,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _get_response_for_student(pk, user):
    """Return a QuestionnaireResponse owned by the given student or raise 404."""
    try:
        return QuestionnaireResponse.objects.select_related(
            'questionnaire', 'student'
        ).prefetch_related('answers__question').get(pk=pk, student=user)
    except QuestionnaireResponse.DoesNotExist:
        return None


# ---------------------------------------------------------------------------
# Cuestionario (CRUD de administración + listado/detalle de estudiantes)
# ---------------------------------------------------------------------------

class QuestionnaireViewSet(ModelViewSet):
    """
    list    GET  /api/questionnaire/questionnaires/
    retrieve GET  /api/questionnaire/questionnaires/<pk>/
    create  POST /api/questionnaire/questionnaires/          [admin/mgmt]
    update  PUT  /api/questionnaire/questionnaires/<pk>/     [admin/mgmt]
    partial PATCH /api/questionnaire/questionnaires/<pk>/    [admin/mgmt]
    destroy DELETE /api/questionnaire/questionnaires/<pk>/   [admin/mgmt]
    """

    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ('create', 'update', 'partial_update', 'destroy'):
            return [IsAdminOrManagement()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Questionnaire.objects.select_related('career', 'created_by').prefetch_related(
            'steps__questions__options'
        )

        # Los estudiantes solo ven cuestionarios activos.
        if hasattr(user, 'role') and user.role == 's':
            qs = qs.filter(is_active=True)

        flow_type = self.request.query_params.get('flow_type')
        if flow_type:
            qs = qs.filter(flow_type=flow_type)

        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return QuestionnaireListSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return QuestionnaireWriteSerializer
        return QuestionnaireSerializer

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='set-wizard', permission_classes=[IsAdminOrManagement])
    def set_wizard(self, request, pk=None):
        """
        POST /api/questionnaire/questionnaires/<pk>/set-wizard/
        Marca este cuestionario como asistente activo de preinscripción y
        desmarca cualquier otro que lo fuera.

        Requiere que el cuestionario tenga al menos una pregunta de tipo
        'career_select' (selección de titulación).
        """
        questionnaire = self.get_object()

        all_questions = Question.objects.filter(step__questionnaire=questionnaire)
        if not all_questions.filter(question_type='career_select').exists():
            return Response(
                {
                    'detail': (
                        'Este cuestionario no puede activarse como asistente de preinscripción. '
                        'Debe contener al menos una pregunta de tipo "career_select".'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        Questionnaire.objects.filter(is_preinscripcion_wizard=True).update(is_preinscripcion_wizard=False)
        questionnaire.is_preinscripcion_wizard = True
        questionnaire.save(update_fields=['is_preinscripcion_wizard', 'updated_at'])
        return Response(QuestionnaireSerializer(questionnaire).data)

    @action(detail=True, methods=['post'], url_path='unset-wizard', permission_classes=[IsAdminOrManagement])
    def unset_wizard(self, request, pk=None):
        """
        POST /api/questionnaire/questionnaires/<pk>/unset-wizard/
        Elimina este cuestionario como asistente de preinscripción (vuelve al asistente estático).
        """
        questionnaire = self.get_object()
        questionnaire.is_preinscripcion_wizard = False
        questionnaire.save(update_fields=['is_preinscripcion_wizard', 'updated_at'])
        return Response(QuestionnaireSerializer(questionnaire).data)

    @action(detail=True, methods=['get'], url_path='my-response', permission_classes=[IsStudent])
    def my_response(self, request, pk=None):
        """GET /api/questionnaire/questionnaires/<pk>/my-response/"""
        questionnaire = self.get_object()
        response = (
            QuestionnaireResponse.objects.prefetch_related('answers__question')
            .filter(questionnaire=questionnaire, student=request.user)
            .order_by('-updated_at')
            .first()
        )
        if response is None:
            return Response(
                {'detail': 'No response found for this questionnaire.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = QuestionnaireResponseSerializer(response)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Estudiante: iniciar una respuesta
# ---------------------------------------------------------------------------

class StartResponseView(APIView):
    """
    POST /api/questionnaire/questionnaires/<pk>/start/

    Crea o recupera el QuestionnaireResponse del estudiante para este
    questionnaire. For admissions flow, links the latest admitted/confirmed
    AdmissionApplication automatically.
    """

    permission_classes = [IsStudent]

    def post(self, request, pk=None):
        try:
            questionnaire = Questionnaire.objects.get(pk=pk, is_active=True)
        except Questionnaire.DoesNotExist:
            return Response(
                {'detail': 'Questionnaire not found or inactive.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        admission = None
        if questionnaire.flow_type == 'admissions':
            from admissions.models import AdmissionApplication

            blocking_statuses = (
                'submitted',
                'under_review',
                'provisional_admitted',
                'provisional_waitlisted',
                'admitted',
                'waitlisted',
                'confirmed',
            )

            if questionnaire.is_preinscripcion_wizard:
                period = _resolve_current_admission_period()
                blocking_qs = AdmissionApplication.objects.filter(
                    student=request.user,
                    status__in=blocking_statuses,
                )
                if period:
                    blocking_qs = blocking_qs.filter(academic_period=period)
                blocking_app = blocking_qs.order_by('-created_at').first()
                if blocking_app:
                    return Response(
                        {
                            'detail': (
                                'Ya tienes una preinscripción activa. '
                                'Solo puedes iniciar otra si la anterior fue rechazada, expiró o fue renunciada.'
                            ),
                            'admission_status': blocking_app.status,
                            'admission_id': blocking_app.pk,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                response_obj = (
                    QuestionnaireResponse.objects.filter(
                        questionnaire=questionnaire,
                        student=request.user,
                        status='draft',
                    )
                    .order_by('-updated_at')
                    .first()
                )
                created = False
                if response_obj is None:
                    response_obj = QuestionnaireResponse.objects.create(
                        questionnaire=questionnaire,
                        student=request.user,
                    )
                    created = True
                serializer = QuestionnaireResponseSerializer(response_obj)
                return Response(
                    serializer.data,
                    status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
                )

            admission = (
                AdmissionApplication.objects.filter(
                    student=request.user,
                    status__in=('admitted', 'confirmed'),
                )
                .order_by('-created_at')
                .first()
            )

        response_obj = (
            QuestionnaireResponse.objects.filter(
                questionnaire=questionnaire,
                student=request.user,
                status='draft',
            )
            .order_by('-updated_at')
            .first()
        )
        created = False
        if response_obj is None:
            response_obj = QuestionnaireResponse.objects.create(
                questionnaire=questionnaire,
                student=request.user,
                admission=admission,
            )
            created = True

        # Si la respuesta ya existía pero no tiene una admisión vinculada, vincúlala ahora.
        if not created and admission and response_obj.admission is None:
            response_obj.admission = admission
            response_obj.save(update_fields=['admission', 'updated_at'])

        # Ruta de recuperación: si la respuesta se envió antes de que existiera la lógica de autocreación
        # (o la utilidad falló silenciosamente), crea la admisión ahora.
        if (
            not created
            and response_obj.status == 'submitted'
            and response_obj.admission is None
            and questionnaire.is_preinscripcion_wizard
        ):
            _create_admission_from_questionnaire(response_obj)
            response_obj.refresh_from_db()

        serializer = QuestionnaireResponseSerializer(response_obj)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Estudiante: detalle de respuesta (obtener y actualizar current_step)
# ---------------------------------------------------------------------------

class ResponseDetailView(generics.RetrieveUpdateAPIView):
    """
    GET   /api/questionnaire/responses/<pk>/
    PATCH /api/questionnaire/responses/<pk>/
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return ResponseUpdateSerializer
        return QuestionnaireResponseSerializer

    def get_object(self):
        user = self.request.user
        try:
            obj = QuestionnaireResponse.objects.select_related(
                'questionnaire', 'student'
            ).prefetch_related('answers__question').get(
                pk=self.kwargs['pk']
            )
        except QuestionnaireResponse.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Response not found.')

        # Los estudiantes solo pueden acceder a sus propias respuestas; administración/gestión puede leer todas.
        if hasattr(user, 'role') and user.role == 's' and obj.student != user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('You do not have access to this response.')

        return obj

    def update(self, request, *args, **kwargs):
        # Solo el estudiante propietario puede modificar la respuesta.
        obj = self.get_object()
        if obj.student != request.user:
            return Response(
                {'detail': 'Only the response owner can update it.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if obj.status == 'submitted':
            return Response(
                {'detail': 'Submitted responses cannot be modified.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Estudiante: enviar una respuesta
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Utilidad: crear AdmissionApplication desde una respuesta del asistente de preinscripción
# ---------------------------------------------------------------------------

def _resolve_current_admission_period():
    from academic.models import AcademicPeriod

    now = timezone.now()
    return (
        AcademicPeriod.objects
        .filter(admission_open_date__lte=now, admission_close_date__gte=now)
        .order_by('-admission_open_date')
        .first()
    ) or (
        AcademicPeriod.objects
        .filter(is_active=True)
        .order_by('-start_date')
        .first()
    )


def _create_admission_from_questionnaire(response_obj):
    """
    Auto-creates an AdmissionApplication (and its career preferences) from a
    submitted QuestionnaireResponse whose questionnaire is flagged as
    is_preinscripcion_wizard=True.

    - Finds the active academic period with an open admission window; falls
      back to any active period if none has a window configured.
    - Skips silently if a period cannot be resolved or if the student already
      has an application for that period.
    - Extracts access_route from any `radio` answer whose value matches one
      of the ACCESS_ROUTE_CHOICES keys.
    - Extracts career preferences from any `career_select` answer (json_value
      is expected to be a list of career PKs in preference order).
    """
    from admissions.models import AdmissionApplication, AdmissionPreference
    student = response_obj.student
    now = timezone.now()

    logger.info(
        "Creating admission for student=%s from questionnaire response=%s",
        student.pk, response_obj.pk,
    )

    # Resolve academic period ------------------------------------------------
    period = _resolve_current_admission_period()
    if not period:
        logger.warning(
            "No active AcademicPeriod found — admission not created for response=%s",
            response_obj.pk,
        )
        return

    logger.info("Resolved period=%s [%s]", period.pk, period.name)

    # Omitir solo si el estudiante tiene una solicitud activa para este periodo. Una
    # solicitud rechazada/renunciada/caducada NO debe consumir el cuestionario
    # para siempre; los estudiantes pueden enviar una nueva preinscripción.
    if AdmissionApplication.objects.filter(
        student=student,
        academic_period=period,
        status__in=(
            'submitted',
            'under_review',
            'provisional_admitted',
            'provisional_waitlisted',
            'admitted',
            'waitlisted',
            'confirmed',
        ),
    ).exists():
        logger.info(
            "El estudiante=%s ya tiene una solicitud bloqueante para el periodo=%s — se omite",
            student.pk, period.pk,
        )
        return

    # Extrae access_route de las respuestas de radio --------------------------------
    valid_routes = {c[0] for c in AdmissionApplication.ACCESS_ROUTE_CHOICES}
    access_route = ''
    for ans in response_obj.answers.select_related('question').all():
        if ans.question.question_type == 'radio' and ans.text_value in valid_routes:
            access_route = ans.text_value
            break

    # Crea la solicitud -------------------------------------------------
    app = AdmissionApplication.objects.create(
        student=student,
        academic_period=period,
        access_route=access_route,
        status='submitted',
        submission_date=now,
    )
    logger.info("AdmissionApplication created: id=%s, route=%r", app.pk, access_route)

    # Crea preferencias de titulación a partir de respuestas career_select -------------------
    career_ids = []
    for ans in response_obj.answers.select_related('question').all():
        if ans.question.question_type == 'career_select' and ans.json_value:
            raw = ans.json_value
            if isinstance(raw, list):
                career_ids = [int(v) for v in raw if str(v).isdigit() or isinstance(v, int)]
            elif isinstance(raw, (int, str)) and str(raw).isdigit():
                career_ids = [int(raw)]
            if career_ids:
                break

    logger.info("Career preferences to create: %s", career_ids)

    for order, career_id in enumerate(career_ids[:10], start=1):
        try:
            AdmissionPreference.objects.create(
                application=app,
                career_id=career_id,
                preference_order=order,
            )
        except Exception as exc:
            logger.warning("Could not create preference order=%s career=%s: %s", order, career_id, exc)

    # Vincula la respuesta con la nueva solicitud --------------------------------
    response_obj.admission = app
    response_obj.save(update_fields=['admission', 'updated_at'])
    logger.info("Response=%s linked to admission=%s", response_obj.pk, app.pk)


class SubmitResponseView(APIView):
    """POST /api/questionnaire/responses/<pk>/submit/"""

    permission_classes = [IsStudent]

    def post(self, request, pk=None):
        response_obj = _get_response_for_student(pk, request.user)
        if response_obj is None:
            return Response(
                {'detail': 'Response not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if response_obj.status == 'submitted':
            return Response(
                {'detail': 'This response has already been submitted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Recoge todas las preguntas obligatorias de todos los pasos de este cuestionario.
        required_questions = Question.objects.filter(
            step__questionnaire=response_obj.questionnaire,
            is_required=True,
        ).values_list('id', 'label')

        # Recoge los ID de preguntas que tienen una respuesta no vacía. Las preguntas de pago
        # son especiales: solo se consideran respondidas cuando el estado de Stripe/demo
        # is confirmed as paid.
        answered_ids = set(
            QuestionAnswer.objects.filter(
                response=response_obj,
            ).exclude(
                text_value='',
                file_value='',
                json_value__isnull=True,
            ).values_list('question_id', flat=True)
        )
        answered_ids.update(
            QuestionAnswer.objects.filter(
                response=response_obj,
                question__question_type='stripe_payment',
                stripe_payment_status='paid',
            ).values_list('question_id', flat=True)
        )

        missing = [
            label
            for q_id, label in required_questions
            if q_id not in answered_ids
        ]

        if missing:
            return Response(
                {
                    'detail': 'The following required questions have not been answered.',
                    'missing_questions': missing,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        response_obj.status = 'submitted'
        response_obj.submitted_at = timezone.now()
        response_obj.save(update_fields=['status', 'submitted_at', 'updated_at'])

        # Autocrea AdmissionApplication para respuestas del asistente de preinscripción
        if response_obj.questionnaire.is_preinscripcion_wizard:
            _create_admission_from_questionnaire(response_obj)

        serializer = QuestionnaireResponseSerializer(response_obj)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Estudiante: alta/actualización masiva de respuestas
# ---------------------------------------------------------------------------

class BulkAnswerView(APIView):
    """
    POST /api/questionnaire/responses/<pk>/answers/
    PUT  /api/questionnaire/responses/<pk>/answers/

    Body: list of answer objects.
    [
      {"question": 12, "text_value": "John"},
      {"question": 13, "json_value": [1, 2, 3]},
      ...
    ]
    """

    permission_classes = [IsStudent]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def _process(self, request, pk):
        response_obj = _get_response_for_student(pk, request.user)
        if response_obj is None:
            return Response(
                {'detail': 'Response not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if response_obj.status == 'submitted':
            return Response(
                {'detail': 'Submitted responses cannot be modified.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = request.data
        # Admite tanto un cuerpo JSON con lista como multipart con una sola respuesta.
        if not isinstance(data, list):
            data = [data]

        saved = []
        errors = []

        for item in data:
            question_id = item.get('question')
            if not question_id:
                errors.append({'question': question_id, 'error': 'question field is required.'})
                continue

            try:
                question = Question.objects.get(pk=question_id)
            except Question.DoesNotExist:
                errors.append({'question': question_id, 'error': 'Question not found.'})
                continue

            # Verifica que esta pregunta pertenece a este cuestionario.
            if question.step.questionnaire_id != response_obj.questionnaire_id:
                errors.append({
                    'question': question_id,
                    'error': 'Question does not belong to this questionnaire.',
                })
                continue

            defaults = {
                'text_value': item.get('text_value', ''),
                'json_value': item.get('json_value', None),
            }

            # Gestiona subidas de ficheros (presentes en peticiones multipart).
            file_value = item.get('file_value', None)
            if file_value:
                defaults['file_value'] = file_value

            answer, _ = QuestionAnswer.objects.update_or_create(
                response=response_obj,
                question=question,
                defaults=defaults,
            )
            saved.append(QuestionAnswerSerializer(answer).data)

        result = {'saved': saved}
        if errors:
            result['errors'] = errors

        return_status = status.HTTP_207_MULTI_STATUS if errors else status.HTTP_200_OK
        return Response(result, status=return_status)

    def post(self, request, pk=None):
        return self._process(request, pk)

    def put(self, request, pk=None):
        return self._process(request, pk)


# ---------------------------------------------------------------------------
# Intento de pago de Stripe
# ---------------------------------------------------------------------------

def _is_production_stripe_enabled():
    """
    Real Pago de Stripes are deliberately gated to production.
    DEBUG=True must never create real PaymentIntents.
    """
    return bool(
        not settings.DEBUG
        and getattr(settings, 'STRIPE_LIVE_PAYMENTS_ENABLED', False)
    )


def _amount_to_minor_units(amount):
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        value = Decimal('0')
    return int(value * 100)


def _get_stripe_module():
    try:
        import stripe as stripe_lib
    except ImportError:
        return None
    stripe_lib.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
    return stripe_lib


def _demo_payment_response(answer, amount, currency):
    demo_intent_id = f'pi_demo_{answer.pk}_academix'
    answer.stripe_payment_intent_id = demo_intent_id
    answer.stripe_payment_status = 'pending'
    answer.save(update_fields=['stripe_payment_intent_id', 'stripe_payment_status'])
    return Response({
        'answer_id': answer.pk,
        'client_secret': None,
        'amount': amount,
        'currency': currency,
        'demo_mode': True,
    })


def _create_payment_intent_for_answer(answer, request):
    if answer.response.student != request.user:
        return Response(
            {'detail': 'You do not have access to this answer.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if answer.response.status == 'submitted':
        return Response(
            {'detail': 'Submitted responses cannot be modified.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if answer.question.question_type != 'stripe_payment':
        return Response(
            {'detail': 'This answer is not associated with a payment question.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    config = answer.question.config or {}
    amount = config.get('amount', 0)
    currency = str(config.get('currency', 'eur')).lower()
    description = config.get('description', 'Payment')

    # Desarrollo debe seguir siendo simulado por decisión de producto.
    if not _is_production_stripe_enabled():
        return _demo_payment_response(answer, amount, currency)

    stripe_key = getattr(settings, 'STRIPE_SECRET_KEY', '')
    if not stripe_key:
        return Response(
            {'detail': 'Stripe is not configured for production payments.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    stripe_lib = _get_stripe_module()
    if stripe_lib is None:
        return Response(
            {'detail': 'Stripe SDK is not installed.'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        intent = stripe_lib.PaymentIntent.create(
            amount=_amount_to_minor_units(amount),
            currency=currency,
            description=description,
            automatic_payment_methods={'enabled': True},
            metadata={
                'answer_id': str(answer.pk),
                'response_id': str(answer.response_id),
                'student_id': str(request.user.pk),
                'questionnaire_id': str(answer.response.questionnaire_id),
            },
        )
        answer.stripe_payment_intent_id = intent['id']
        answer.stripe_payment_status = 'pending'
        answer.save(update_fields=['stripe_payment_intent_id', 'stripe_payment_status'])

        return Response({
            'answer_id': answer.pk,
            'client_secret': intent['client_secret'],
            'amount': amount,
            'currency': currency,
            'demo_mode': False,
        })
    except Exception as exc:
        return Response(
            {'detail': f'Stripe error: {exc}'},
            status=status.HTTP_502_BAD_GATEWAY,
        )


class CreatePaymentIntentView(APIView):
    """
    POST /api/questionnaire/answers/<pk>/payment-intent/

    Creates a Pago con StripeIntent for stripe_payment answers.
    In development (DEBUG=True), returns demo mode instead of contacting Stripe.
    """

    permission_classes = [IsStudent]

    def post(self, request, pk=None):
        try:
            answer = QuestionAnswer.objects.select_related(
                'question', 'response__student'
            ).get(pk=pk)
        except QuestionAnswer.DoesNotExist:
            return Response(
                {'detail': 'Answer not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        return _create_payment_intent_for_answer(answer, request)


class CreateResponseQuestionPaymentIntentView(APIView):
    """
    POST /api/questionnaire/responses/<response_pk>/questions/<question_pk>/payment-intent/

    Creates or reuses the QuestionAnswer for a payment question, then creates a
    production Pago con StripeIntent or a development demo intent.
    """

    permission_classes = [IsStudent]

    def post(self, request, response_pk=None, question_pk=None):
        response_obj = _get_response_for_student(response_pk, request.user)
        if response_obj is None:
            return Response(
                {'detail': 'Response not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if response_obj.status == 'submitted':
            return Response(
                {'detail': 'Submitted responses cannot be modified.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            question = Question.objects.get(
                pk=question_pk,
                step__questionnaire=response_obj.questionnaire,
            )
        except Question.DoesNotExist:
            return Response(
                {'detail': 'No se encontró una pregunta de pago para esta respuesta.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if question.question_type != 'stripe_payment':
            return Response(
                {'detail': 'This question is not a payment question.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        answer, _ = QuestionAnswer.objects.get_or_create(
            response=response_obj,
            question=question,
            defaults={'stripe_payment_status': 'pending'},
        )
        return _create_payment_intent_for_answer(answer, request)


class ConfirmPaymentView(APIView):
    """
    POST /api/questionnaire/answers/<pk>/confirm-payment/

    Development confirms demo intents locally. Production retrieves the
    PaymentIntent from Stripe and only marks paid when Stripe says it succeeded.
    """

    permission_classes = [IsStudent]

    def post(self, request, pk=None):
        try:
            answer = QuestionAnswer.objects.select_related(
                'question', 'response__student'
            ).get(pk=pk)
        except QuestionAnswer.DoesNotExist:
            return Response(
                {'detail': 'Answer not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if answer.response.student != request.user:
            return Response(
                {'detail': 'You do not have access to this answer.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if answer.question.question_type != 'stripe_payment':
            return Response(
                {'detail': 'This answer is not associated with a payment question.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not _is_production_stripe_enabled():
            if not answer.stripe_payment_intent_id.startswith('pi_demo_'):
                return Response(
                    {'detail': 'Demo confirmation is only valid for demo payment intents.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            answer.stripe_payment_status = 'paid'
            answer.save(update_fields=['stripe_payment_status'])
            return Response({'answer_id': answer.pk, 'status': 'paid', 'demo_mode': True})

        if not answer.stripe_payment_intent_id:
            return Response(
                {'detail': 'No Pago con StripeIntent exists for this answer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        stripe_lib = _get_stripe_module()
        if stripe_lib is None or not getattr(settings, 'STRIPE_SECRET_KEY', ''):
            return Response(
                {'detail': 'Stripe is not configured for production payments.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            intent = stripe_lib.PaymentIntent.retrieve(answer.stripe_payment_intent_id)
        except Exception as exc:
            return Response(
                {'detail': f'Stripe error: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if intent['status'] == 'succeeded':
            answer.stripe_payment_status = 'paid'
        elif intent['status'] in ('requires_payment_method', 'canceled'):
            answer.stripe_payment_status = 'failed'
        else:
            answer.stripe_payment_status = 'pending'
        answer.save(update_fields=['stripe_payment_status'])
        return Response({
            'answer_id': answer.pk,
            'status': answer.stripe_payment_status,
            'stripe_status': intent['status'],
            'demo_mode': False,
        })


class StripeConfigView(APIView):
    """
    GET /api/questionnaire/stripe/config/

    Returns the publishable Stripe key at runtime. This avoids baking production
    keys into the Astro build and keeps development in demo mode.
    """

    permission_classes = [IsStudent]

    def get(self, request):
        live_mode = _is_production_stripe_enabled()
        return Response({
            'live_mode': live_mode,
            'publishable_key': getattr(settings, 'STRIPE_PUBLIC_KEY', '') if live_mode else '',
        })


class StripeWebhookView(APIView):
    """
    POST /api/questionnaire/stripe/webhook/

    Production webhook for payment_intent.succeeded / payment_intent.payment_failed.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        if not _is_production_stripe_enabled():
            return HttpResponse(status=204)

        stripe_lib = _get_stripe_module()
        webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
        if stripe_lib is None or not webhook_secret:
            return Response(
                {'detail': 'Stripe webhook is not configured.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
        try:
            event = stripe_lib.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError:
            return HttpResponse(status=400)
        except Exception:
            return HttpResponse(status=400)

        event_type = event.get('type')
        intent = event.get('data', {}).get('object', {})
        answer_id = (intent.get('metadata') or {}).get('answer_id')
        if answer_id and event_type in ('payment_intent.succeeded', 'payment_intent.payment_failed'):
            try:
                answer = QuestionAnswer.objects.get(pk=answer_id)
                answer.stripe_payment_intent_id = intent.get('id', answer.stripe_payment_intent_id)
                answer.stripe_payment_status = (
                    'paid' if event_type == 'payment_intent.succeeded' else 'failed'
                )
                answer.save(update_fields=['stripe_payment_intent_id', 'stripe_payment_status'])
            except QuestionAnswer.DoesNotExist:
                logger.warning("Stripe webhook referenced missing answer_id=%s", answer_id)

        return HttpResponse(status=200)


# ---------------------------------------------------------------------------
# Admin: QuestionnaireStep CRUD
# ---------------------------------------------------------------------------

class StepListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/questionnaire/questionnaires/<questionnaire_pk>/steps/
    POST /api/questionnaire/questionnaires/<questionnaire_pk>/steps/
    """

    permission_classes = [IsAdminOrManagement]

    def get_queryset(self):
        return QuestionnaireStep.objects.filter(
            questionnaire_id=self.kwargs['questionnaire_pk']
        ).prefetch_related('questions__options')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QuestionnaireStepWriteSerializer
        return QuestionnaireStepSerializer

    def perform_create(self, serializer):
        try:
            questionnaire = Questionnaire.objects.get(pk=self.kwargs['questionnaire_pk'])
        except Questionnaire.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Questionnaire not found.')
        serializer.save(questionnaire=questionnaire)


class StepDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/questionnaire/steps/<pk>/
    PATCH  /api/questionnaire/steps/<pk>/
    DELETE /api/questionnaire/steps/<pk>/
    """

    permission_classes = [IsAdminOrManagement]
    queryset = QuestionnaireStep.objects.prefetch_related('questions__options')

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return QuestionnaireStepWriteSerializer
        return QuestionnaireStepSerializer


# ---------------------------------------------------------------------------
# Administración: CRUD de preguntas
# ---------------------------------------------------------------------------

class QuestionListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/questionnaire/steps/<step_pk>/questions/
    POST /api/questionnaire/steps/<step_pk>/questions/
    """

    permission_classes = [IsAdminOrManagement]

    def get_queryset(self):
        return Question.objects.filter(
            step_id=self.kwargs['step_pk']
        ).prefetch_related('options')

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QuestionWriteSerializer
        return QuestionSerializer

    def perform_create(self, serializer):
        try:
            step = QuestionnaireStep.objects.get(pk=self.kwargs['step_pk'])
        except QuestionnaireStep.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Step not found.')
        serializer.save(step=step)


class QuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/questionnaire/questions/<pk>/
    PATCH  /api/questionnaire/questions/<pk>/
    DELETE /api/questionnaire/questions/<pk>/
    """

    permission_classes = [IsAdminOrManagement]
    queryset = Question.objects.prefetch_related('options')

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return QuestionWriteSerializer
        return QuestionSerializer


# ---------------------------------------------------------------------------
# Admin: QuestionOption CRUD
# ---------------------------------------------------------------------------

class OptionListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/questionnaire/questions/<question_pk>/options/
    POST /api/questionnaire/questions/<question_pk>/options/
    """

    permission_classes = [IsAdminOrManagement]

    def get_queryset(self):
        return QuestionOption.objects.filter(question_id=self.kwargs['question_pk'])

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QuestionOptionWriteSerializer
        return QuestionOptionSerializer

    def perform_create(self, serializer):
        try:
            question = Question.objects.get(pk=self.kwargs['question_pk'])
        except Question.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Question not found.')
        serializer.save(question=question)


class OptionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/questionnaire/options/<pk>/
    PATCH  /api/questionnaire/options/<pk>/
    DELETE /api/questionnaire/options/<pk>/
    """

    permission_classes = [IsAdminOrManagement]
    queryset = QuestionOption.objects.all()

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return QuestionOptionWriteSerializer
        return QuestionOptionSerializer


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------

class QuestionnaireExportView(APIView):
    """
    GET /api/questionnaire/questionnaires/<pk>/export/
    Returns the full questionnaire structure as a portable JSON blob.
    IDs are stripped so the same JSON can be imported elsewhere.
    """
    permission_classes = [IsAdminOrManagement]

    def get(self, request, pk=None):
        try:
            questionnaire = Questionnaire.objects.prefetch_related(
                'steps__questions__options'
            ).get(pk=pk)
        except Questionnaire.DoesNotExist:
            return Response({'detail': 'Questionnaire not found.'}, status=status.HTTP_404_NOT_FOUND)

        data = {
            'title': questionnaire.title,
            'description': questionnaire.description,
            'flow_type': questionnaire.flow_type,
            'is_preinscripcion_wizard': questionnaire.is_preinscripcion_wizard,
            'steps': [
                {
                    'title': step.title,
                    'description': step.description,
                    'order': step.order,
                    'questions': [
                        {
                            'label': q.label,
                            'help_text': q.help_text,
                            'question_type': q.question_type,
                            'is_required': q.is_required,
                            'order': q.order,
                            'config': q.config,
                            'depends_on_order': q.depends_on.order if q.depends_on else None,
                            'depends_on_value': q.depends_on_value,
                            'options': [
                                {'label': opt.label, 'value': opt.value, 'order': opt.order}
                                for opt in q.options.all()
                            ],
                        }
                        for q in step.questions.all()
                    ],
                }
                for step in questionnaire.steps.all()
            ],
        }
        return Response(data)


class QuestionnaireImportView(APIView):
    """
    POST /api/questionnaire/import/
    Body: a JSON blob exported via /export/.
    Creates a NEW questionnaire (never overwrites).
    Returns the created questionnaire.
    """
    permission_classes = [IsAdminOrManagement]

    def post(self, request):
        data = request.data
        if not isinstance(data, dict):
            return Response({'detail': 'Expected a JSON object.'}, status=status.HTTP_400_BAD_REQUEST)

        title = data.get('title', 'Imported Questionnaire')
        flow_type = data.get('flow_type', 'admissions')
        if flow_type not in ('admissions', 'enrollment'):
            return Response({'detail': 'flow_type must be admissions or enrollment.'}, status=status.HTTP_400_BAD_REQUEST)

        questionnaire = Questionnaire.objects.create(
            title=f"{title} (imported)",
            description=data.get('description', ''),
            flow_type=flow_type,
            is_preinscripcion_wizard=False,  # no activar automáticamente los importados
            created_by=request.user,
        )

        for step_data in data.get('steps', []):
            step = QuestionnaireStep.objects.create(
                questionnaire=questionnaire,
                title=step_data.get('title', ''),
                description=step_data.get('description', ''),
                order=step_data.get('order', 0),
            )
            # Primera pasada: crea preguntas sin depends_on
            created_questions = []
            for q_data in step_data.get('questions', []):
                q = Question.objects.create(
                    step=step,
                    label=q_data.get('label', ''),
                    help_text=q_data.get('help_text', ''),
                    question_type=q_data.get('question_type', 'text'),
                    is_required=q_data.get('is_required', True),
                    order=q_data.get('order', 0),
                    config=q_data.get('config', {}),
                )
                for opt_data in q_data.get('options', []):
                    QuestionOption.objects.create(
                        question=q,
                        label=opt_data.get('label', ''),
                        value=opt_data.get('value', ''),
                        order=opt_data.get('order', 0),
                    )
                created_questions.append((q, q_data.get('depends_on_order')))

            # Segunda pasada: enlaza depends_on por orden dentro del paso
            order_to_question = {q.order: q for q, _ in created_questions}
            for q, dep_order in created_questions:
                if dep_order is not None and dep_order in order_to_question:
                    q.depends_on = order_to_question[dep_order]
                    q.save(update_fields=['depends_on'])

        serializer = QuestionnaireSerializer(questionnaire)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Asistente activo de preinscripción
# ---------------------------------------------------------------------------

class WizardQuestionnaireView(APIView):
    """
    GET /api/questionnaire/wizard/
    Devuelve el cuestionario activo marcado como asistente de preinscripción.
    Devuelve 404 si ninguno está configurado (se usa el asistente estático por defecto).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            questionnaire = Questionnaire.objects.prefetch_related(
                'steps__questions__options'
            ).get(is_preinscripcion_wizard=True, is_active=True)
        except Questionnaire.DoesNotExist:
            return Response(
                {'detail': 'No hay asistente de preinscripción configurado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = QuestionnaireSerializer(questionnaire)
        return Response(serializer.data)
