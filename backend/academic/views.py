from django.db import transaction
from django.db.models import Prefetch, Q
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import (
    Career,
    Subject,
    Department,
    AcademicPeriod,
    Classroom,
    Class,
    ClassSchedule,
    SubjectOffering,
    TimeSlot,
    TimetableRun,
    ScheduleAssignment,
    ConstraintViolation,
    SchedulingConstraint,
    TeacherSubjectDecision,
)
from .serializers import (
    CareerSerializer, SubjectSerializer, AcademicPeriodSerializer,
    DepartmentSerializer,
    ClassroomSerializer, ClassSerializer, ClassScheduleSerializer,
    TimeSlotSerializer, TimetableRunSerializer, ScheduleAssignmentSerializer,
    ConstraintViolationSerializer,
    SchedulingConstraintSerializer,
    SubjectOfferingSerializer,
    TeacherSubjectSelectionSerializer,
    TeacherSubjectDecisionSerializer,
)
from .timetabling import generate_for_run, build_warning_summary_for_run
from .timetabling import delete_generated_classes_for_period
from .services import reconcile_teacher_decision_change
from .schedule_source import serialize_assignment_schedule, published_assignments_map_for_period
from shared.permissions import IsAdminOrManagement
from shared.periods import get_active_academic_period
from enrollment.services import resolve_convocation_eligibility

SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')
COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
          '#ec4899', '#14b8a6', '#f97316', '#06b6d4', '#a855f7']


def _teacher_display_name(teacher):
    if not teacher:
        return ''
    return f"{teacher.first_name} {teacher.last_name}".strip() or teacher.username


def _current_period_payload():
    period = get_active_academic_period()
    if not period:
        return None
    return {'id': period.id, 'name': period.name, 'code': period.code}


def _department_for_teacher(user):
    return Department.objects.filter(teacher=user).first()


def _subject_is_active_and_owned(subject, teacher):
    department = getattr(subject, 'department', None)
    return bool(subject.is_active and department and department.teacher_id == teacher.id)


class CareerViewSet(viewsets.ModelViewSet):
    queryset = Career.objects.all()
    serializer_class = CareerSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]

    @action(detail=True, methods=['get'], url_path='classes')
    def classes_by_career(self, request, pk=None):
        """GET /api/academic/careers/<id>/classes/?period=<period_id>"""
        career = self.get_object()
        period_id = request.query_params.get('period')

        qs = Class.objects.filter(
            Q(subject__careers=career) | Q(subject__career=career)
        ).select_related(
            'subject', 'teacher', 'period', 'classroom'
        ).prefetch_related(
            'subject__careers',
            Prefetch(
                'schedule_assignments',
                queryset=ScheduleAssignment.objects.filter(run__status='published').select_related('slot', 'run'),
                to_attr='published_schedule_assignments',
            )
        )

        if period_id:
            qs = qs.filter(period_id=period_id)

        convocation_context = {}
        if period_id and request.user.role == 's':
            for cls in qs:
                convocation_context[cls.id] = resolve_convocation_eligibility(request.user, cls.subject, cls.period)

        serializer = ClassSerializer(qs, many=True, context={'request': request, 'convocation_context': convocation_context})
        return Response(serializer.data)


class SubjectOfferingViewSet(viewsets.ModelViewSet):
    """
    CRUD de SubjectOffering más las acciones activate / deactivate / select.

    Permisos:
      - create / activate / deactivate: IsAdminOrManagement
      - list / retrieve: IsAuthenticated
      - select: solo docente (role='t')
    """
    serializer_class = SubjectOfferingSerializer
    pagination_class = None
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        if self.action in ('activate', 'deactivate', 'create', 'partial_update'):
            return [IsAdminOrManagement()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = SubjectOffering.objects.select_related('subject', 'period', 'department').all()
        department = self.request.query_params.get('department')
        period = self.request.query_params.get('period')
        active = self.request.query_params.get('active')
        if department:
            qs = qs.filter(department_id=department)
        if period:
            qs = qs.filter(period_id=period)
        if active == 'true':
            qs = qs.filter(is_active=True)
        elif active == 'false':
            qs = qs.filter(is_active=False)
        return qs

    @action(detail=True, methods=['patch'], url_path='activate')
    def activate(self, request, pk=None):
        """PATCH /offerings/<id>/activate/ — gestión activa la oferta."""
        offering = self.get_object()
        offering.is_active = True
        offering.save(update_fields=['is_active', 'updated_at'])
        return Response(SubjectOfferingSerializer(offering).data)

    @action(detail=True, methods=['patch'], url_path='deactivate')
    def deactivate(self, request, pk=None):
        """PATCH /offerings/<id>/deactivate/ — gestión desactiva la oferta."""
        offering = self.get_object()
        offering.is_active = False
        offering.save(update_fields=['is_active', 'updated_at'])
        return Response(SubjectOfferingSerializer(offering).data)

    @action(detail=True, methods=['post'], url_path='select', permission_classes=[IsAuthenticated])
    def select(self, request, pk=None):
        """POST /offerings/<id>/select/ — el docente selecciona una oferta."""
        if request.user.role != 't':
            return Response(
                {'detail': 'Only teachers can select offerings.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        offering = self.get_object()
        if not offering.is_active:
            return Response(
                {'detail': 'Cannot select an inactive offering.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        period = offering.period
        if TeacherSubjectDecision.objects.filter(teacher=request.user, offering=offering).exists():
            return Response(
                {'detail': 'You have already selected this offering.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        decision = TeacherSubjectDecision.objects.create(
            teacher=request.user,
            offering=offering,
            period=period,
            decision='pending',
        )
        serializer = TeacherSubjectDecisionSerializer(decision, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TeacherSubjectSelectionSubmitView(APIView):
    """
    Endpoint heredado para envío masivo. Se mantiene por compatibilidad hacia atrás.
    El código nuevo debe usar SubjectOfferingViewSet.select por cada oferta.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != 't':
            return Response({'detail': 'Only teachers can submit subject selection.'}, status=status.HTTP_403_FORBIDDEN)

        period = get_active_academic_period()
        if not period:
            return Response({'detail': 'An active admission period is required.'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {'detail': 'Legacy submit endpoint is deprecated. Use POST /offerings/<id>/select/ per offering.'},
            status=status.HTTP_410_GONE,
        )


class TeacherSubjectDecisionReviewView(APIView):
    """
    PATCH /api/academic/teacher-subject-selection/decisions/<pk>/review/

    Cuerpo: {'action': 'approved' | 'rejected'}

    El frontend envía `action`, que se traduce al campo `decision` del serializador.
    Cualquier otro valor de `action` devuelve 400.
    """
    permission_classes = [IsAdminOrManagement]

    VALID_ACTIONS = ('approved', 'rejected')

    def patch(self, request, pk):
        decision = get_object_or_404(
            TeacherSubjectDecision.objects.select_related('offering__department', 'teacher'),
            pk=pk,
        )

        action = request.data.get('action')
        if action not in self.VALID_ACTIONS:
            return Response(
                {'detail': "action must be 'approved' or 'rejected'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        previous_decision = decision.decision
        with transaction.atomic():
            serializer = TeacherSubjectDecisionSerializer(decision, data={'decision': action}, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save(decided_by=request.user)
            reconcile_teacher_decision_change(decision, previous_decision)
        updated = TeacherSubjectDecisionSerializer(decision, context={'request': request}).data
        return Response(updated)


class TeacherSubjectDecisionListView(APIView):
    """GET /api/academic/teacher-subject-selection/decisions/

    Alcance por rol:
      t → solo sus propios registros
      m / a → todos los registros
      cualquier otro rol autenticado → 403
    Filtros: ?period=<id>  (por defecto, periodo activo)
             ?teacher=<id> (opcional)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = TeacherSubjectDecision.objects.select_related(
            'offering__subject', 'offering__department', 'teacher', 'decided_by'
        )
        u = request.user
        if u.role == 't':
            qs = qs.filter(teacher=u)
        elif u.role not in ('m', 'a'):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        period = request.query_params.get('period') or getattr(
            get_active_academic_period(), 'id', None
        )
        if period:
            qs = qs.filter(period_id=period)

        teacher_id = request.query_params.get('teacher')
        if teacher_id:
            qs = qs.filter(teacher_id=teacher_id)

        data = TeacherSubjectDecisionSerializer(
            qs, many=True, context={'request': request}
        ).data
        return Response(data)


class SubjectViewSet(viewsets.ModelViewSet):
    serializer_class = SubjectSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]

    def get_queryset(self):
        qs = Subject.objects.select_related('career', 'department', 'department__teacher').prefetch_related('careers').all()
        career_id = self.request.query_params.get('career')
        if career_id:
            qs = qs.filter(Q(careers__id=career_id) | Q(career_id=career_id)).distinct()
        return qs


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.select_related('teacher').all()
    serializer_class = DepartmentSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]


class AcademicPeriodViewSet(viewsets.ModelViewSet):
    queryset = AcademicPeriod.objects.all()
    serializer_class = AcademicPeriodSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]

    def get_queryset(self):
        qs = AcademicPeriod.objects.all().order_by('-start_date', '-id')
        is_active = self.request.query_params.get('is_active')
        if is_active in {'true', 'false'}:
            qs = qs.filter(is_active=(is_active == 'true'))
        return qs

    def perform_create(self, serializer):
        instance = serializer.save()
        # Solo puede haber un periodo activo a la vez, incluidos los periodos recién creados.
        # La interfaz avisa de esto; el backend también debe imponerlo.
        if instance.is_active:
            AcademicPeriod.objects.exclude(pk=instance.pk).update(is_active=False)

    def perform_update(self, serializer):
        instance = serializer.save()
        # Solo puede haber un periodo activo a la vez.
        if instance.is_active:
            AcademicPeriod.objects.exclude(pk=instance.pk).update(is_active=False)


class ClassroomViewSet(viewsets.ModelViewSet):
    serializer_class = ClassroomSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]

    def get_queryset(self):
        qs = Classroom.objects.all().order_by('id')
        room_type = self.request.query_params.get('type') or self.request.query_params.get('room_type')
        if room_type:
            qs = qs.filter(type=room_type)
        return qs


class ClassViewSet(viewsets.ModelViewSet):
    serializer_class = ClassSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]

    def get_queryset(self):
        return Class.objects.select_related(
            'subject__career', 'teacher', 'period', 'classroom'
        ).prefetch_related('schedules', 'subject__careers').all()

    @action(detail=False, methods=['get'], url_path='my-classes')
    def my_classes(self, request):
        if request.user.role != 't':
            return Response({'error': 'Only teachers can access this endpoint'}, status=403)
        active_period = get_active_academic_period()
        if not active_period:
            return Response([])
        qs = self.get_queryset().filter(teacher=request.user)
        qs = qs.filter(period=active_period)
        # Registra el recuento de calificaciones pendientes.
        from grades.models import Evaluation, Grade
        from enrollment.models import ClassEnrollment
        from django.db.models import Avg
        result = []
        for cls in qs:
            enrolled_ids = ClassEnrollment.objects.filter(
                cls=cls, status='enrolled'
            ).values_list('student_id', flat=True)
            evals = Evaluation.objects.filter(cls=cls)
            total_expected = len(enrolled_ids) * evals.count()
            graded = Grade.objects.filter(evaluation__in=evals).count()
            pending = max(0, total_expected - graded)
            avg = Grade.objects.filter(
                evaluation__in=evals, student__in=enrolled_ids
            ).aggregate(a=Avg('score'))['a']
            data = ClassSerializer(cls).data
            data['student_count'] = len(enrolled_ids)
            data['pending_grades'] = pending
            data['avg_score'] = round(float(avg), 1) if avg else None
            result.append(data)
        return Response(result)

    @action(detail=False, methods=['get'], url_path='my-schedule')
    def my_schedule(self, request):
        from enrollment.models import ClassEnrollment
        role = request.user.role
        if role == 's':
            classes = Class.objects.filter(
                id__in=ClassEnrollment.objects.filter(
                    student=request.user, status='enrolled'
                ).values_list('cls_id', flat=True)
            ).select_related('subject', 'teacher', 'classroom', 'period').prefetch_related('schedules')
        elif role == 't':
            classes = Class.objects.filter(teacher=request.user).select_related(
                'subject', 'classroom', 'period'
            ).prefetch_related('schedules')
        else:
            return Response({'error': 'Only students and teachers have schedules'}, status=403)

        active_period = get_active_academic_period()
        if active_period:
            classes = classes.filter(period=active_period)
        else:
            fallback_period_id = classes.order_by('-period__start_date', '-period_id').values_list(
                'period_id', flat=True
            ).first()
            if not fallback_period_id:
                return Response([])
            classes = classes.filter(period_id=fallback_period_id)

        class_ids = [cls.id for cls in classes]
        assignments_by_period_and_class = {}
        for period_id in {cls.period_id for cls in classes}:
            assignments_by_period_and_class[period_id] = published_assignments_map_for_period(
                period_id,
                class_ids,
            )

        schedule_data = []
        for i, cls in enumerate(classes):
            assignments = assignments_by_period_and_class.get(cls.period_id, {}).get(cls.id, [])
            if assignments:
                for assignment in assignments:
                    teacher = cls.teacher or assignment.teacher
                    classroom = assignment.classroom or cls.classroom
                    schedule_data.append({
                        'schedule_id': assignment.slot_id,
                        'assignment_id': assignment.id,
                        'source': assignment.source,
                        'class_id': cls.id,
                        'subject_name': cls.subject.name,
                        'subject_code': cls.subject.code,
                        'period_name': cls.period.name,
                    'teacher_name': _teacher_display_name(teacher),
                        'classroom': str(classroom) if classroom else '',
                        'day_of_week': assignment.slot.day_of_week,
                        'day_name': assignment.slot.get_day_of_week_display(),
                        'start_time': assignment.slot.start_time.strftime('%H:%M'),
                        'end_time': assignment.slot.end_time.strftime('%H:%M'),
                        'color': COLORS[i % len(COLORS)],
                    })
                continue

            for sched in cls.schedules.all():
                schedule_data.append({
                    'schedule_id': sched.id,
                    'assignment_id': None,
                    'source': 'legacy',
                    'class_id': cls.id,
                    'subject_name': cls.subject.name,
                    'subject_code': cls.subject.code,
                    'period_name': cls.period.name,
                    'teacher_name': _teacher_display_name(cls.teacher),
                    'classroom': str(cls.classroom) if cls.classroom else '',
                    'day_of_week': sched.day_of_week,
                    'day_name': sched.get_day_of_week_display(),
                    'start_time': sched.start_time.strftime('%H:%M'),
                    'end_time': sched.end_time.strftime('%H:%M'),
                    'color': COLORS[i % len(COLORS)],
                })
        return Response(schedule_data)


class ClassScheduleViewSet(viewsets.ModelViewSet):
    queryset = ClassSchedule.objects.select_related('cls').all()
    serializer_class = ClassScheduleSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]


class TimeSlotViewSet(viewsets.ModelViewSet):
    queryset = TimeSlot.objects.select_related('period').all()
    serializer_class = TimeSlotSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]


class TimetableRunViewSet(viewsets.ModelViewSet):
    serializer_class = TimetableRunSerializer

    def get_queryset(self):
        qs = TimetableRun.objects.select_related('period').all()
        period = self.request.query_params.get('period')
        run_status = self.request.query_params.get('status')
        if period:
            qs = qs.filter(period_id=period)
        if run_status:
            qs = qs.filter(status=run_status)
        return qs

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        run = self.get_object()
        if run.status == 'published':
            return Response({'detail': 'No se puede eliminar una ejecución publicada.'}, status=status.HTTP_400_BAD_REQUEST)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        run = self.get_object()
        run = generate_for_run(run)
        payload = TimetableRunSerializer(run).data
        if run.status == 'failed':
            preconditions = (run.metadata or {}).get('generator', {}).get('precondition_errors', [])
            preparation_errors = (run.metadata or {}).get('generator', {}).get('class_preparation_errors', [])
            reason_map = {
                'missing_classes': 'faltan clases para el periodo',
                'missing_teachers': 'faltan docentes asignados en una o más clases',
                'missing_classrooms': 'faltan aulas asignadas en una o más clases',
                'missing_time_slots': 'faltan franjas horarias del periodo',
                'class_preparation_insufficient_subjects': 'faltan materias activas para preparar clases del periodo',
                'class_preparation_insufficient_classrooms': 'faltan aulas disponibles para preparar clases del periodo',
            }
            reasons_source = [*preconditions, *preparation_errors]
            if reasons_source:
                reasons = [reason_map[key] for key in reasons_source if key in reason_map]
                if reasons:
                    payload['detail'] = f"No se pudo generar: {', '.join(reasons)}."
            return Response(payload, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        with transaction.atomic():
            run = TimetableRun.objects.select_for_update().select_related('period').get(pk=pk)
            if run.status == 'failed':
                return Response({'detail': 'Cannot publish a failed run.'}, status=status.HTTP_400_BAD_REQUEST)
            warning_summary = build_warning_summary_for_run(run)
            if warning_summary.get('blocks_publish') or warning_summary.get('hard_violations', 0) > 0:
                return Response(
                    {
                        'detail': 'Cannot publish a run with hard infringements.',
                        'warning_summary': warning_summary,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            TimetableRun.objects.select_for_update().filter(period=run.period, status='published').exclude(id=run.id).update(
                status='completed'
            )
            run.status = 'published'
            run.save(update_fields=['status', 'updated_at'])
        return Response(TimetableRunSerializer(run).data)

    @action(detail=False, methods=['post'], url_path='cleanup/generated-classes')
    def cleanup_generated_classes(self, request):
        if not settings.DEBUG:
            return Response({'detail': 'Unavailable outside DEBUG.'}, status=status.HTTP_404_NOT_FOUND)
        if getattr(request.user, 'role', None) not in ('a', 'm'):
            return Response({'detail': 'Forbidden.'}, status=status.HTTP_403_FORBIDDEN)

        period_id = request.data.get('period') or request.query_params.get('period')
        if not period_id:
            return Response({'detail': 'period is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            period = AcademicPeriod.objects.get(pk=period_id)
        except AcademicPeriod.DoesNotExist:
            return Response({'detail': 'Period not found.'}, status=status.HTTP_404_NOT_FOUND)

        deleted_count = delete_generated_classes_for_period(period, scope=request.data.get('scope', 'period'))
        return Response({'deleted_classes': deleted_count})


class ScheduleAssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ScheduleAssignmentSerializer
    pagination_class = None

    def get_queryset(self):
        qs = ScheduleAssignment.objects.select_related('run', 'cls__subject__career', 'slot', 'classroom', 'teacher').prefetch_related('cls__subject__careers').all()
        run = self.request.query_params.get('run')
        period = self.request.query_params.get('period')
        cls = self.request.query_params.get('cls')
        career = self.request.query_params.get('career')
        if run:
            qs = qs.filter(run_id=run)
        if period:
            qs = qs.filter(run__period_id=period)
        if cls:
            qs = qs.filter(cls_id=cls)
        if career:
            qs = qs.filter(Q(cls__subject__careers__id=career) | Q(cls__subject__career_id=career)).distinct()
        return qs.order_by('id')

    def get_permissions(self):
        return [IsAuthenticated()]


class ConstraintViolationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConstraintViolationSerializer

    def get_queryset(self):
        qs = ConstraintViolation.objects.select_related('run', 'assignment').all()
        run = self.request.query_params.get('run')
        assignment = self.request.query_params.get('assignment')
        severity = self.request.query_params.get('severity')
        if run:
            qs = qs.filter(run_id=run)
        if assignment:
            qs = qs.filter(assignment_id=assignment)
        if severity:
            qs = qs.filter(severity=severity)
        return qs

    def get_permissions(self):
        return [IsAuthenticated()]


class SchedulingConstraintViewSet(viewsets.ModelViewSet):
    serializer_class = SchedulingConstraintSerializer

    def get_queryset(self):
        qs = SchedulingConstraint.objects.select_related('period', 'teacher', 'classroom', 'career').all()
        period = self.request.query_params.get('period')
        is_active = self.request.query_params.get('is_active')
        if period:
            qs = qs.filter(period_id=period)
        if is_active in {'true', 'false'}:
            qs = qs.filter(is_active=(is_active == 'true'))
        return qs

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]
