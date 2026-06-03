from datetime import timedelta
from decimal import Decimal, InvalidOperation
import re

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet
from rest_framework.mixins import (
    CreateModelMixin, RetrieveModelMixin,
    ListModelMixin,
)
from rest_framework.parsers import MultiPartParser, FormParser

from .models import AdmissionApplication, AdmissionPreference, AdmissionDocument
from .serializers import (
    AdmissionApplicationSerializer,
    AdmissionApplicationListSerializer,
    AdmissionPreferenceSerializer,
    AdmissionDocumentSerializer,
)
from .permissions import IsStudent, IsManagement, IsOwnerOrManagement
from .utils import compact_waitlist_positions, notify_next_waitlisted, get_waitlist_admission_expiry
from notifications.utils import create_notification


BLOCKING_ADMISSION_STATUSES = (
    'submitted',
    'under_review',
    'provisional_admitted',
    'provisional_waitlisted',
    'admitted',
    'waitlisted',
    'confirmed',
)

LOCKED_SEAT_ADMISSION_STATUSES = ('confirmed', 'completed')


def _parse_decimal(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'y', 'on')
    return bool(value)


def _mask_identifier(identifier):
    raw = str(identifier or '').strip()
    if not raw:
        return ''
    try:
        from notifications.models import SystemSettings
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
        pattern = getattr(settings_obj, 'admission_public_dni_mask_regex', '') or ''
        replacement = getattr(settings_obj, 'admission_public_dni_mask_replacement', '') or ''
        if pattern and replacement:
            return re.sub(pattern, replacement, raw)
    except Exception:
        pass
    if len(raw) <= 4:
        return raw[0] + '*' * max(len(raw) - 1, 0)
    return f'{raw[:3]}{"*" * max(len(raw) - 5, 3)}{raw[-2:]}'


class AdmissionApplicationViewSet(
    CreateModelMixin,
    RetrieveModelMixin,
    ListModelMixin,
    GenericViewSet,
):
    serializer_class = AdmissionApplicationSerializer

    def get_permissions(self):
        if self.action in ('create', 'submit', 'confirm', 'withdraw', 'set_preferences', 'update_academic_data'):
            return [IsStudent()]
        if self.action in ('review', 'provisional_resolve', 'definitive_resolve', 'generate_ranking', 'publish_ranking'):
            return [IsManagement()]
        return [IsOwnerOrManagement()]

    def get_queryset(self):
        user = self.request.user
        qs = AdmissionApplication.objects.select_related(
            'student', 'academic_period', 'assigned_career'
        ).prefetch_related('preferences__career', 'documents')

        if user.role in ('m', 'a'):
            status_filter = self.request.query_params.get('status')
            period_filter = self.request.query_params.get('period')
            route_filter = self.request.query_params.get('access_route')
            career_filter = self.request.query_params.get('career')
            search_filter = (self.request.query_params.get('search') or '').strip()
            if status_filter:
                qs = qs.filter(status=status_filter)
            if period_filter:
                qs = qs.filter(academic_period_id=period_filter)
            if route_filter:
                qs = qs.filter(access_route=route_filter)
            if career_filter:
                qs = qs.filter(
                    Q(assigned_career_id=career_filter) | Q(preferences__career_id=career_filter)
                ).distinct()
            if search_filter:
                qs = qs.filter(
                    Q(student__first_name__icontains=search_filter) |
                    Q(student__last_name__icontains=search_filter) |
                    Q(student__username__icontains=search_filter) |
                    Q(student__email__icontains=search_filter) |
                    Q(assigned_career__name__icontains=search_filter) |
                    Q(preferences__career__name__icontains=search_filter) |
                    Q(preferences__career__code__icontains=search_filter)
                ).distinct()
            return qs
        else:
            return qs.filter(student=user)

    def get_serializer_class(self):
        if self.action == 'list':
            return AdmissionApplicationListSerializer
        return AdmissionApplicationSerializer

    def perform_create(self, serializer):
        serializer.save(student=self.request.user)

    def create(self, request, *args, **kwargs):
        period = request.data.get('academic_period_id')
        if AdmissionApplication.objects.filter(
            student=request.user,
            status__in=BLOCKING_ADMISSION_STATUSES,
        ).exists():
            return Response(
                {"detail": "Ya tienes una preinscripción activa. No puedes crear una nueva hasta que la actual se resuelva, expire o sea rechazada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        from academic.models import AcademicPeriod
        try:
            period_obj = AcademicPeriod.objects.get(pk=period)
        except (AcademicPeriod.DoesNotExist, TypeError, ValueError):
            return Response(
                {"detail": "periodo académico no encontrado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        if period_obj.admission_open_date and now < period_obj.admission_open_date:
            return Response(
                {"detail": "La ventana de admisión para este periodo aún no está abierta."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if period_obj.admission_close_date and now > period_obj.admission_close_date:
            return Response(
                {"detail": "La ventana de admisión para este periodo ya está cerrada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().create(request, *args, **kwargs)

    # ---- Datos académicos ----

    @action(detail=True, methods=['patch'], url_path='academic-data')
    def update_academic_data(self, request, pk=None):
        """
        PATCH /api/admissions/applications/<id>/academic-data/
        Actualiza vía de acceso y datos académicos. Recalcula nota de admisión.
        """
        app = self.get_object()

        if app.student != request.user:
            return Response({"detail": "No tienes permiso."}, status=status.HTTP_403_FORBIDDEN)

        if app.status not in ('draft',):
            return Response(
                {"detail": "Solo puedes actualizar los datos académicos en estado borrador."},
                status=status.HTTP_400_BAD_REQUEST
            )

        allowed_fields = {
            'access_route', 'bachillerato_grade',
            'evau_obligatory_grade', 'evau_voluntary_subjects',
        }
        for field in allowed_fields:
            if field in request.data:
                setattr(app, field, request.data[field])

        # Recalcular nota de admisión automáticamente
        app.admission_score = app.calculate_admission_score()
        app.save(update_fields=list(allowed_fields) + ['admission_score', 'updated_at'])

        serializer = self.get_serializer(app)
        return Response(serializer.data)

    # ---- Preferencias de titulaciones ----

    @action(detail=True, methods=['get', 'post'], url_path='preferences')
    def set_preferences(self, request, pk=None):
        """
        GET  /api/admissions/applications/<id>/preferences/
        POST /api/admissions/applications/<id>/preferences/
             Body: [{"career_id": 1, "preference_order": 1}, ...]
             Reemplaza todas las preferencias existentes.
        """
        app = self.get_object()

        if request.method == 'GET':
            prefs = app.preferences.all()
            serializer = AdmissionPreferenceSerializer(prefs, many=True)
            return Response(serializer.data)

        if app.student != request.user:
            return Response({"detail": "No tienes permiso."}, status=status.HTTP_403_FORBIDDEN)

        if app.status != 'draft':
            return Response(
                {"detail": "Solo puedes modificar preferencias en estado borrador."},
                status=status.HTTP_400_BAD_REQUEST
            )

        items = request.data
        if not isinstance(items, list):
            return Response({"detail": "Se esperaba una lista de preferencias."}, status=status.HTTP_400_BAD_REQUEST)

        if len(items) > 10:
            return Response({"detail": "Máximo 10 preferencias por preinscripción."}, status=status.HTTP_400_BAD_REQUEST)

        # Validar cada ítem antes de escribir
        serializers_list = []
        orders_seen = set()
        careers_seen = set()
        for item in items:
            s = AdmissionPreferenceSerializer(data=item)
            if not s.is_valid():
                return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)
            order = s.validated_data['preference_order']
            career = s.validated_data['career']
            if order in orders_seen:
                return Response(
                    {"detail": f"Orden duplicado: {order}."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if career.id in careers_seen:
                return Response(
                    {"detail": f"Carrera duplicada: {career.name}."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            orders_seen.add(order)
            careers_seen.add(career.id)
            serializers_list.append(s)

        # Reemplazar preferencias
        app.preferences.all().delete()
        for s in serializers_list:
            s.save(application=app)

        prefs = app.preferences.all()
        return Response(AdmissionPreferenceSerializer(prefs, many=True).data)

    # ---- Enviar ----

    @action(detail=True, methods=['patch'], url_path='submit')
    def submit(self, request, pk=None):
        """PATCH /api/admissions/applications/<id>/submit/"""
        app = self.get_object()

        if app.student != request.user:
            return Response({"detail": "No tienes permiso."}, status=status.HTTP_403_FORBIDDEN)

        if app.status != 'draft':
            return Response(
                {"detail": f"Solo puedes enviar solicitudes en estado borrador. Estado actual: {app.status}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        app.status = 'submitted'
        app.submission_date = timezone.now()
        app.save(update_fields=['status', 'submission_date', 'updated_at'])

        serializer = self.get_serializer(app)
        return Response(serializer.data)

    # ---- Revisión (management) ----

    @action(detail=True, methods=['patch'], url_path='review')
    def review(self, request, pk=None):
        """PATCH /api/admissions/applications/<id>/review/"""
        app = self.get_object()
        app.status = 'under_review'
        app.save(update_fields=['status', 'updated_at'])
        return Response(self.get_serializer(app).data)

    # ---- Resolución provisional (management) ----

    @action(detail=True, methods=['patch'], url_path='provisional-resolve')
    def provisional_resolve(self, request, pk=None):
        """
        PATCH /api/admissions/applications/<id>/provisional-resolve/
        Body: {"status": "provisional_admitted|provisional_waitlisted|provisional_rejected",
               "preference_order": 2,   # requerido si admitted
               "notes": "..."}
        """
        app = self.get_object()

        if app.status not in ('submitted', 'under_review'):
            return Response(
                {"detail": "Solo se puede resolver provisionalmente desde 'submitted' o 'under_review'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_status = request.data.get('status')
        valid = ('provisional_admitted', 'provisional_waitlisted', 'provisional_rejected')
        if new_status not in valid:
            return Response(
                {"detail": f"Estado inválido. Opciones: {', '.join(valid)}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        notes = request.data.get('notes', '')

        if new_status == 'provisional_admitted':
            pref_order = request.data.get('preference_order')
            if not pref_order:
                return Response(
                    {"detail": "Se requiere 'preference_order' al admitir."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                pref = app.preferences.get(preference_order=pref_order)
            except AdmissionPreference.DoesNotExist:
                return Response(
                    {"detail": f"No existe la preferencia {pref_order}."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            app.assigned_career = pref.career
            app.assigned_preference_order = pref.preference_order
            pref.is_assigned = True
            pref.status = 'admitted'
            pref.save(update_fields=['is_assigned', 'status'])

            create_notification(
                app.student,
                'Resolución provisional — Admitido',
                f'Tu preinscripción ha sido admitida provisionalmente para {pref.career.name} '
                f'(opción {pref_order}). Puedes reclamar si detectás algún error.',
                'success',
                event_type='provisional_admitted',
            )

        elif new_status == 'provisional_waitlisted':
            create_notification(
                app.student,
                'Resolución provisional — Lista de espera',
                'Tu preinscripción ha quedado en lista de espera en la resolución provisional.',
                'info',
                event_type='provisional_waitlisted',
            )

        elif new_status == 'provisional_rejected':
            create_notification(
                app.student,
                'Resolución provisional — No admitido',
                'Tu preinscripción no ha sido admitida en la resolución provisional.',
                'warning',
                event_type='provisional_rejected',
            )

        app.status = new_status
        if notes:
            app.notes = notes
        app.save(update_fields=[
            'status', 'notes', 'assigned_career', 'assigned_preference_order', 'updated_at'
        ])

        return Response(self.get_serializer(app).data)

    # ---- Resolución definitiva (management) ----

    @action(detail=True, methods=['patch'], url_path='definitive-resolve')
    def definitive_resolve(self, request, pk=None):
        """
        PATCH /api/admissions/applications/<id>/definitive-resolve/
        Body: {"status": "admitted|waitlisted|rejected",
               "preference_order": 1,   # requerido si admitted
               "notes": "..."}
        """
        app = self.get_object()

        allowed_from = (
            'submitted', 'under_review',
            'provisional_admitted', 'provisional_waitlisted', 'provisional_rejected',
        )
        if app.status not in allowed_from:
            return Response(
                {"detail": "El estado actual no permite una resolución definitiva."},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_status = request.data.get('status')
        valid = ('admitted', 'waitlisted', 'rejected')
        if new_status not in valid:
            return Response(
                {"detail": f"Estado inválido. Opciones: {', '.join(valid)}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        notes = request.data.get('notes', '')

        if new_status == 'admitted':
            pref_order = request.data.get('preference_order')
            if not pref_order:
                return Response(
                    {"detail": "Se requiere 'preference_order' al admitir definitivamente."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                pref = app.preferences.get(preference_order=pref_order)
            except AdmissionPreference.DoesNotExist:
                return Response(
                    {"detail": f"No existe la preferencia {pref_order}."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Limpiar asignación anterior si cambió
            app.preferences.filter(is_assigned=True).update(is_assigned=False)
            app.assigned_career = pref.career
            app.assigned_preference_order = pref.preference_order
            pref.is_assigned = True
            pref.status = 'admitted'
            pref.save(update_fields=['is_assigned', 'status'])

            expiry_days = getattr(settings, 'ADMISSION_EXPIRY_DAYS', 7)
            app.admission_expiry_date = timezone.now() + timedelta(days=expiry_days)
            expiry_str = app.admission_expiry_date.strftime('%d/%m/%Y')

            create_notification(
                app.student,
                'Resolución definitiva — Plaza asignada',
                f'Has obtenido plaza en {pref.career.name} (opción {pref_order}). '
                f'Tienes hasta el {expiry_str} para confirmar la matrícula.',
                'success',
                event_type='admission_resolved',
            )

        elif new_status == 'waitlisted':
            app.preferences.filter(status='pending').update(status='waitlisted')
            create_notification(
                app.student,
                'Resolución definitiva — Lista de espera',
                'No has obtenido plaza en la resolución definitiva. Has quedado en lista de espera.',
                'info',
                event_type='waitlisted',
            )

        elif new_status == 'rejected':
            app.preferences.filter(status='pending').update(status='rejected')
            create_notification(
                app.student,
                'Resolución definitiva — No admitido',
                'Tu preinscripción no ha sido admitida en la resolución definitiva.',
                'error',
                event_type='rejected',
            )

        app.status = new_status
        if notes:
            app.notes = notes
        app.save(update_fields=[
            'status', 'notes', 'assigned_career', 'assigned_preference_order',
            'admission_expiry_date', 'updated_at'
        ])

        return Response(self.get_serializer(app).data)

    # ---- Confirmar plaza ----

    @action(detail=True, methods=['patch'], url_path='confirm')
    def confirm(self, request, pk=None):
        """PATCH /api/admissions/applications/<id>/confirm/"""
        app = self.get_object()

        if app.student != request.user:
            return Response({"detail": "No tienes permiso."}, status=status.HTTP_403_FORBIDDEN)

        if app.status in ('confirmed', 'completed'):
            return Response(self.get_serializer(app).data)

        if app.status != 'admitted':
            return Response(
                {"detail": "Solo puedes confirmar solicitudes en estado 'admitted'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if app.admission_expiry_date and app.admission_expiry_date <= timezone.now():
            app.status = 'expired'
            app.save(update_fields=['status', 'updated_at'])
            create_notification(
                app.student,
                'Plaza expirada',
                f'El plazo para confirmar tu plaza en {app.assigned_career.name} ha expirado.',
                'warning',
                event_type='admission_expired',
            )
            return Response(
                {"detail": "El plazo de confirmación ha expirado."},
                status=status.HTTP_400_BAD_REQUEST
            )

        app.status = 'confirmed'
        app.save(update_fields=['status', 'updated_at'])

        career_name = app.assigned_career.name if app.assigned_career else '—'
        create_notification(
            app.student,
            'Plaza confirmada',
            f'Plaza confirmada para {career_name}.',
            'success',
            event_type='admission_resolved',
        )

        return Response(self.get_serializer(app).data)

    # ---- Renunciar ----

    @action(detail=True, methods=['patch'], url_path='withdraw')
    def withdraw(self, request, pk=None):
        """PATCH /api/admissions/applications/<id>/withdraw/"""
        app = self.get_object()

        if app.student != request.user:
            return Response({"detail": "No tienes permiso."}, status=status.HTTP_403_FORBIDDEN)

        if app.status not in (
            'submitted',
            'under_review',
            'provisional_admitted',
            'provisional_waitlisted',
            'admitted',
            'waitlisted',
            'confirmed',
        ):
            return Response(
                {"detail": "Solo puedes renunciar si tu solicitud está enviada, en revisión, admitida, en lista de espera o confirmada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        released_career = app.assigned_career
        waitlisted_careers = list(
            app.preferences
            .filter(status='waitlisted')
            .select_related('career')
            .values_list('career_id', flat=True)
            .distinct()
        )
        app.status = 'withdrawn'
        app.save(update_fields=['status', 'updated_at'])
        app.preferences.exclude(status='rejected').update(status='withdrawn')

        if released_career:
            notify_next_waitlisted(released_career, app.academic_period)
        for career_id in waitlisted_careers:
            if released_career and career_id == released_career.id:
                continue
            compact_waitlist_positions(career_id, app.academic_period)

        return Response(self.get_serializer(app).data)

    # ---- Ranking y publicación de listas ----

    def _sync_application_results(self, affected_app_ids, now):
        if not affected_app_ids:
            return

        for app in AdmissionApplication.objects.filter(
            pk__in=affected_app_ids
        ).prefetch_related('preferences__career'):
            admitted_pref = app.preferences.filter(status='admitted').order_by('preference_order').first()
            waitlisted_exists = app.preferences.filter(status='waitlisted').exists()
            if admitted_pref:
                app.status = 'admitted'
                app.assigned_career = admitted_pref.career
                app.assigned_preference_order = admitted_pref.preference_order
                if not app.admission_expiry_date:
                    app.admission_expiry_date = get_waitlist_admission_expiry(now)
            elif waitlisted_exists:
                app.status = 'waitlisted'
                app.assigned_career = None
                app.assigned_preference_order = None
                app.admission_expiry_date = None
            else:
                app.status = 'rejected'
                app.assigned_career = None
                app.assigned_preference_order = None
                app.admission_expiry_date = None
            app.save(update_fields=[
                'status', 'assigned_career', 'assigned_preference_order',
                'admission_expiry_date', 'updated_at',
            ])

    def _score_preference(self, preference, score_source, question_ids):
        app = preference.application
        if score_source == 'questionnaire_average':
            if not question_ids:
                return Decimal('0.000')
            from questionnaire.models import QuestionAnswer
            values = []
            answers = QuestionAnswer.objects.filter(
                response__admission=app,
                question_id__in=question_ids,
            )
            for answer in answers:
                candidate = answer.text_value
                if candidate in (None, '') and answer.json_value is not None:
                    candidate = answer.json_value
                if isinstance(candidate, list):
                    for item in candidate:
                        parsed = _parse_decimal(item)
                        if parsed is not None:
                            values.append(parsed)
                else:
                    parsed = _parse_decimal(candidate)
                    if parsed is not None:
                        values.append(parsed)
            if not values:
                return Decimal('0.000')
            return (sum(values) / Decimal(len(values))).quantize(Decimal('0.001'))

        return (app.admission_score or Decimal('0.000')).quantize(Decimal('0.001'))

    def _locked_seat_count(self, career, period):
        """
        Cuenta plazas ya bloqueadas por estudiantes que confirmaron o completaron
        matrícula. Esas plazas no vuelven a la lista salvo renuncia explícita.
        """
        return AdmissionPreference.objects.filter(
            career=career,
            application__academic_period=period,
            status='admitted',
            application__status__in=LOCKED_SEAT_ADMISSION_STATUSES,
        ).count()

    @action(detail=False, methods=['post'], url_path='generate-ranking')
    def generate_ranking(self, request):
        """
        POST /api/admissions/applications/generate-ranking/
        Body:
          {
            "academic_period_id": 1,
            "career_id": 2,
            "score_source": "admission_score|questionnaire_average",
            "question_ids": [10, 11],
            "publish": false
          }
        """
        from academic.models import AcademicPeriod, Career

        period_id = request.data.get('academic_period_id')
        career_id = request.data.get('career_id')
        score_source = request.data.get('score_source', 'admission_score')
        question_ids = request.data.get('question_ids') or []
        publish = _parse_bool(request.data.get('publish', False))

        if score_source not in ('admission_score', 'questionnaire_average'):
            return Response(
                {"detail": "score_source debe ser 'admission_score' o 'questionnaire_average'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if score_source == 'questionnaire_average' and not isinstance(question_ids, list):
            return Response({"detail": "question_ids debe ser una lista."}, status=status.HTTP_400_BAD_REQUEST)
        if score_source == 'questionnaire_average':
            try:
                question_ids = [int(q) for q in question_ids if str(q).strip()]
            except (TypeError, ValueError):
                return Response({"detail": "question_ids solo puede contener IDs numéricos."}, status=status.HTTP_400_BAD_REQUEST)
            if not question_ids:
                return Response({"detail": "question_ids debe incluir al menos una pregunta numérica."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            period = AcademicPeriod.objects.get(pk=period_id)
            career = Career.objects.get(pk=career_id)
        except (AcademicPeriod.DoesNotExist, Career.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "periodo académico o carrera no encontrados."}, status=status.HTTP_400_BAD_REQUEST)

        candidates = list(
            AdmissionPreference.objects.select_related(
                'application__student',
                'application__academic_period',
                'career',
            )
            .filter(
                career=career,
                application__academic_period=period,
                application__status__in=BLOCKING_ADMISSION_STATUSES,
            )
            .exclude(application__status__in=(
                'withdrawn', 'expired', 'rejected',
                *LOCKED_SEAT_ADMISSION_STATUSES,
            ))
        )

        scored = [
            (pref, self._score_preference(pref, score_source, question_ids))
            for pref in candidates
        ]
        scored.sort(key=lambda item: (
            -item[1],
            item[0].preference_order,
            item[0].application.submission_date or item[0].application.created_at,
        ))

        now = timezone.now()
        spots = max(int(career.total_spots or 0), 0)
        locked_seats = self._locked_seat_count(career, period)
        available_spots = max(spots - locked_seats, 0)
        candidate_ids = [pref.pk for pref, _ in scored]

        with transaction.atomic():
            # Reinicia solo esta titulación/periodo. Otros resultados de titulaciones en la misma
            # solicitud se mantienen intactos, que es justo lo que permite
            # "admitido en una carrera y en espera en otra".
            if candidate_ids:
                reset_fields = {
                    'draft_result_status': None,
                    'draft_ranking_score': None,
                    'draft_rank_position': None,
                    'draft_waitlist_position': None,
                    'draft_generated_at': None,
                }
                if publish:
                    reset_fields.update({
                        'status': 'pending',
                        'ranking_score': None,
                        'rank_position': None,
                        'waitlist_position': None,
                        'published_at': None,
                        'is_assigned': False,
                    })
                AdmissionPreference.objects.filter(pk__in=candidate_ids).update(**reset_fields)

            affected_apps = set()
            result_rows = []
            for index, (pref, score_value) in enumerate(scored, start=1):
                admitted = index <= available_spots
                result_status = 'admitted' if admitted else 'waitlisted'
                rank_position = locked_seats + index
                waitlist_position = None if admitted else index - available_spots

                if publish:
                    pref.status = result_status
                    pref.ranking_score = score_value
                    pref.rank_position = rank_position
                    pref.waitlist_position = waitlist_position
                    pref.published_at = now
                    pref.is_assigned = admitted
                    pref.save(update_fields=[
                        'status', 'ranking_score', 'rank_position',
                        'waitlist_position', 'published_at', 'is_assigned',
                    ])
                    affected_apps.add(pref.application_id)
                else:
                    pref.draft_result_status = result_status
                    pref.draft_ranking_score = score_value
                    pref.draft_rank_position = rank_position
                    pref.draft_waitlist_position = waitlist_position
                    pref.draft_generated_at = now
                    pref.save(update_fields=[
                        'draft_result_status', 'draft_ranking_score', 'draft_rank_position',
                        'draft_waitlist_position', 'draft_generated_at',
                    ])

                result_rows.append({
                    'application_id': pref.application_id,
                    'student_name': pref.application.student.get_full_name(),
                    'dni_masked': _mask_identifier(getattr(pref.application.student, 'dni', '')),
                    'career_id': career.pk,
                    'career_name': career.name,
                    'status': result_status,
                    'score': str(score_value),
                    'rank_position': rank_position,
                    'waitlist_position': waitlist_position,
                    'published_at': pref.published_at.isoformat() if publish and pref.published_at else None,
                })

            if publish:
                self._sync_application_results(affected_apps, now)

        return Response({
            'career_id': career.pk,
            'career_name': career.name,
            'academic_period_id': period.pk,
            'academic_period_name': period.name,
            'capacity': spots,
            'locked_seats': locked_seats,
            'available_spots': available_spots,
            'score_source': score_source,
            'published': publish,
            'results': result_rows,
        })

    @action(detail=False, methods=['post'], url_path='publish-ranking')
    def publish_ranking(self, request):
        """
        POST /api/admissions/applications/publish-ranking/
        Body: {"academic_period_id": 1, "career_id": 2}
        """
        from academic.models import AcademicPeriod, Career

        period_id = request.data.get('academic_period_id')
        career_id = request.data.get('career_id')

        try:
            period = AcademicPeriod.objects.get(pk=period_id)
            career = Career.objects.get(pk=career_id)
        except (AcademicPeriod.DoesNotExist, Career.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "periodo académico o carrera no encontrados."}, status=status.HTTP_400_BAD_REQUEST)

        draft_rows = list(
            AdmissionPreference.objects.select_related(
                'application__student',
                'application__academic_period',
                'career',
            )
            .filter(
                career=career,
                application__academic_period=period,
                application__status__in=BLOCKING_ADMISSION_STATUSES,
                draft_result_status__in=('admitted', 'waitlisted'),
                draft_rank_position__isnull=False,
            )
            .exclude(application__status__in=(
                'withdrawn', 'expired', 'rejected',
                *LOCKED_SEAT_ADMISSION_STATUSES,
            ))
            .order_by('draft_rank_position', 'preference_order', 'application__created_at')
        )

        if not draft_rows:
            return Response(
                {"detail": "No hay un borrador de ranking pendiente para publicar en esta carrera y periodo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        spots = max(int(career.total_spots or 0), 0)
        locked_seats = self._locked_seat_count(career, period)
        available_spots = max(spots - locked_seats, 0)
        affected_apps = set()
        result_rows = []

        with transaction.atomic():
            for index, pref in enumerate(draft_rows, start=1):
                admitted = index <= available_spots
                result_status = 'admitted' if admitted else 'waitlisted'
                pref.status = result_status
                pref.ranking_score = pref.draft_ranking_score
                pref.rank_position = locked_seats + index
                pref.waitlist_position = None if admitted else index - available_spots
                pref.published_at = now
                pref.is_assigned = admitted
                pref.draft_result_status = None
                pref.draft_ranking_score = None
                pref.draft_rank_position = None
                pref.draft_waitlist_position = None
                pref.draft_generated_at = None
                pref.save(update_fields=[
                    'status', 'ranking_score', 'rank_position',
                    'waitlist_position', 'published_at', 'is_assigned',
                    'draft_result_status', 'draft_ranking_score', 'draft_rank_position',
                    'draft_waitlist_position', 'draft_generated_at',
                ])
                affected_apps.add(pref.application_id)
                result_rows.append({
                    'application_id': pref.application_id,
                    'student_name': pref.application.student.get_full_name(),
                    'dni_masked': _mask_identifier(getattr(pref.application.student, 'dni', '')),
                    'career_id': career.pk,
                    'career_name': career.name,
                    'status': result_status,
                    'score': str(pref.ranking_score),
                    'rank_position': pref.rank_position,
                    'waitlist_position': pref.waitlist_position,
                    'published_at': pref.published_at.isoformat() if pref.published_at else None,
                })

            self._sync_application_results(affected_apps, now)

        return Response({
            'career_id': career.pk,
            'career_name': career.name,
            'academic_period_id': period.pk,
            'academic_period_name': period.name,
            'capacity': spots,
            'locked_seats': locked_seats,
            'available_spots': available_spots,
            'published': len(result_rows),
            'published_at': now.isoformat(),
            'results': result_rows,
        })

    # ---- Documentos ----

    @action(
        detail=True,
        methods=['get', 'post'],
        url_path='documents',
        parser_classes=[MultiPartParser, FormParser],
    )
    def documents(self, request, pk=None):
        """
        GET  /api/admissions/applications/<id>/documents/
        POST /api/admissions/applications/<id>/documents/
        """
        app = self.get_object()

        if request.method == 'GET':
            docs = app.documents.all()
            return Response(AdmissionDocumentSerializer(docs, many=True).data)

        if app.student != request.user:
            return Response({"detail": "No tienes permiso."}, status=status.HTTP_403_FORBIDDEN)

        if app.status not in ('draft', 'submitted'):
            return Response(
                {"detail": "Solo puedes subir documentos cuando la solicitud está en borrador o enviada."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = AdmissionDocumentSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(application=app)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(
        detail=True,
        methods=['delete'],
        url_path=r'documents/(?P<doc_id>[0-9]+)',
        url_name='document-delete',
    )
    def remove_document(self, request, pk=None, doc_id=None):
        """DELETE /api/admissions/applications/<id>/documents/<doc_id>/"""
        app = self.get_object()

        if app.student != request.user:
            return Response({"detail": "No tienes permiso."}, status=status.HTTP_403_FORBIDDEN)

        if app.status != 'draft':
            return Response(
                {"detail": "Solo puedes eliminar documentos en borrador."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            doc = AdmissionDocument.objects.get(pk=doc_id, application=app)
        except AdmissionDocument.DoesNotExist:
            return Response({"detail": "Documento no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        doc.file.delete(save=False)
        doc.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


    # ---- Respuestas de cuestionarios ----

    @action(detail=True, methods=['get'], url_path='questionnaire-responses')
    def questionnaire_responses(self, request, pk=None):
        """GET /api/admissions/applications/<id>/questionnaire-responses/"""
        from questionnaire.models import QuestionnaireResponse
        from questionnaire.serializers import QuestionnaireResponseSerializer
        app = self.get_object()
        responses = QuestionnaireResponse.objects.filter(
            admission=app
        ).select_related('questionnaire').prefetch_related('answers__question')
        return Response(QuestionnaireResponseSerializer(responses, many=True).data)


class DocumentValidationView(generics.GenericAPIView):
    """POST /api/admissions/documents/<pk>/validate/"""
    permission_classes = [IsManagement]

    def post(self, request, pk=None, *args, **kwargs):
        try:
            doc = AdmissionDocument.objects.select_related(
                'application__student'
            ).get(pk=pk)
        except AdmissionDocument.DoesNotExist:
            return Response({"detail": "Documento no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        rejection_reason = request.data.get('rejection_reason', '')

        if new_status not in ('validated', 'rejected'):
            return Response({"detail": "Estado inválido. Use 'validated' o 'rejected'."}, status=status.HTTP_400_BAD_REQUEST)

        if new_status == 'rejected' and not rejection_reason:
            return Response(
                {"rejection_reason": ["Este campo es requerido al rechazar un documento."]},
                status=status.HTTP_400_BAD_REQUEST
            )

        doc.status = new_status
        doc.rejection_reason = rejection_reason if new_status == 'rejected' else ''
        doc.save(update_fields=['status', 'rejection_reason'])

        student = doc.application.student
        doc_type_display = doc.get_document_type_display()

        if new_status == 'validated':
            create_notification(
                student,
                'Documento validado',
                f'Tu documento {doc_type_display} ha sido validado.',
                'success',
                event_type='document_validated',
                context={'document_type': doc_type_display},
            )
        else:
            create_notification(
                student,
                'Documento rechazado',
                f'Tu documento {doc_type_display} ha sido rechazado: {rejection_reason}.',
                'warning',
                event_type='document_rejected',
                context={
                    'document_type': doc_type_display,
                    'rejection_reason': rejection_reason,
                },
            )

        return Response(AdmissionDocumentSerializer(doc).data)


class PublicAdmissionResultsView(APIView):
    """
    GET /api/admissions/public/results/?period=<id>&career=<id>&dni=<dni>

    Público: no requiere login. Expone solo resultados publicados y DNI
    enmascarado; nunca devuelve datos personales completos.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        period_id = request.query_params.get('period')
        career_id = request.query_params.get('career')
        dni = (request.query_params.get('dni') or '').strip()

        qs = (
            AdmissionPreference.objects.select_related(
                'application__student',
                'application__academic_period',
                'career',
            )
            .filter(
                published_at__isnull=False,
                status__in=('admitted', 'waitlisted', 'rejected'),
            )
            .order_by('career__name', 'rank_position', 'waitlist_position')
        )
        if period_id:
            qs = qs.filter(application__academic_period_id=period_id)
        if career_id:
            qs = qs.filter(career_id=career_id)
        if dni:
            qs = qs.filter(application__student__dni__iexact=dni)

        rows = []
        waitlist_positions = {}
        latest_publication = None
        for pref in qs:
            if pref.published_at and (latest_publication is None or pref.published_at > latest_publication):
                latest_publication = pref.published_at
            waitlist_position = None
            if pref.status == 'waitlisted':
                waitlist_key = (pref.application.academic_period_id, pref.career_id)
                waitlist_positions[waitlist_key] = waitlist_positions.get(waitlist_key, 0) + 1
                waitlist_position = waitlist_positions[waitlist_key]
            rows.append({
                'career_id': pref.career_id,
                'career_name': pref.career.name,
                'academic_period_id': pref.application.academic_period_id,
                'academic_period_name': pref.application.academic_period.name,
                'dni_masked': _mask_identifier(getattr(pref.application.student, 'dni', '')),
                'status': pref.status,
                'ranking_score': str(pref.ranking_score) if pref.ranking_score is not None else None,
                'rank_position': pref.rank_position,
                'waitlist_position': waitlist_position,
                'published_at': pref.published_at.isoformat() if pref.published_at else None,
            })

        return Response({
            'process_status': 'published' if rows else 'pending_publication',
            'latest_publication': latest_publication.isoformat() if latest_publication else None,
            'count': len(rows),
            'results': rows,
        })
