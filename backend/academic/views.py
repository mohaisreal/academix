from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import (
    Career,
    Subject,
    AcademicPeriod,
    Classroom,
    Class,
    ClassSchedule,
    TimeSlot,
    TimetableRun,
    ScheduleAssignment,
    ConstraintViolation,
)
from .serializers import (
    CareerSerializer, SubjectSerializer, AcademicPeriodSerializer,
    ClassroomSerializer, ClassSerializer, ClassScheduleSerializer,
    TimeSlotSerializer, TimetableRunSerializer, ScheduleAssignmentSerializer,
    ConstraintViolationSerializer,
)
from .timetabling import generate_for_run
from shared.permissions import IsAdminOrManagement

SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')
COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
          '#ec4899', '#14b8a6', '#f97316', '#06b6d4', '#a855f7']


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
            subject__career=career
        ).select_related(
            'subject', 'teacher', 'period', 'classroom'
        ).prefetch_related('schedules')

        if period_id:
            qs = qs.filter(period_id=period_id)

        serializer = ClassSerializer(qs, many=True)
        return Response(serializer.data)


class SubjectViewSet(viewsets.ModelViewSet):
    serializer_class = SubjectSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]

    def get_queryset(self):
        qs = Subject.objects.select_related('career').all()
        career_id = self.request.query_params.get('career')
        if career_id:
            qs = qs.filter(career_id=career_id)
        return qs


class AcademicPeriodViewSet(viewsets.ModelViewSet):
    queryset = AcademicPeriod.objects.all()
    serializer_class = AcademicPeriodSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]

    def perform_create(self, serializer):
        instance = serializer.save()
        # Solo puede haber un periodo activo a la vez, incluidos los periodos recién creados
        # La interfaz avisa de esto; el backend también debe imponerlo.
        if instance.is_active:
            AcademicPeriod.objects.exclude(pk=instance.pk).update(is_active=False)

    def perform_update(self, serializer):
        instance = serializer.save()
        # Solo puede haber un periodo activo a la vez
        if instance.is_active:
            AcademicPeriod.objects.exclude(pk=instance.pk).update(is_active=False)


class ClassroomViewSet(viewsets.ModelViewSet):
    queryset = Classroom.objects.all()
    serializer_class = ClassroomSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]


class ClassViewSet(viewsets.ModelViewSet):
    serializer_class = ClassSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAdminOrManagement()]

    def get_queryset(self):
        return Class.objects.select_related(
            'subject__career', 'teacher', 'period', 'classroom'
        ).prefetch_related('schedules').all()

    @action(detail=False, methods=['get'], url_path='my-classes')
    def my_classes(self, request):
        if request.user.role != 't':
            return Response({'error': 'Only teachers can access this endpoint'}, status=403)
        active_period = AcademicPeriod.objects.filter(is_active=True).first()
        qs = self.get_queryset().filter(teacher=request.user)
        if active_period:
            qs = qs.filter(period=active_period)
        # Anota el recuento de notas pendientes
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
            enrolled_ids = ClassEnrollment.objects.filter(
                student=request.user, status='enrolled'
            ).values_list('cls_id', flat=True)
            classes = Class.objects.filter(id__in=enrolled_ids).select_related(
                'subject', 'teacher', 'classroom', 'period'
            ).prefetch_related('schedules')
        elif role == 't':
            active_period = AcademicPeriod.objects.filter(is_active=True).first()
            classes = Class.objects.filter(teacher=request.user).select_related(
                'subject', 'classroom', 'period'
            ).prefetch_related('schedules')
            if active_period:
                classes = classes.filter(period=active_period)
        else:
            return Response({'error': 'Only students and teachers have schedules'}, status=403)

        class_ids = [cls.id for cls in classes]
        published_assignments = ScheduleAssignment.objects.filter(
            run__period__in={cls.period_id for cls in classes},
            run__status='published',
            cls_id__in=class_ids,
        ).select_related(
            'run__period',
            'cls__subject',
            'cls__teacher',
            'cls__classroom',
            'slot',
            'teacher',
            'classroom',
        )
        assignments_by_class = {assignment.cls_id: assignment for assignment in published_assignments}

        schedule_data = []
        for i, cls in enumerate(classes):
            assignment = assignments_by_class.get(cls.id)
            if assignment:
                teacher = assignment.teacher or cls.teacher
                classroom = assignment.classroom or cls.classroom
                schedule_data.append({
                    'schedule_id': assignment.slot_id,
                    'assignment_id': assignment.id,
                    'source': assignment.source,
                    'class_id': cls.id,
                    'subject_name': cls.subject.name,
                    'subject_code': cls.subject.code,
                    'period_name': cls.period.name,
                    'teacher_name': (
                        f"{teacher.first_name} {teacher.last_name}".strip()
                        if teacher else ''
                    ),
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
                    'teacher_name': (
                        f"{cls.teacher.first_name} {cls.teacher.last_name}".strip()
                        if cls.teacher else ''
                    ),
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

    @action(detail=True, methods=['post'])
    def generate(self, request, pk=None):
        run = self.get_object()
        run = generate_for_run(run)
        payload = TimetableRunSerializer(run).data
        if run.status == 'failed':
            preconditions = (run.metadata or {}).get('generator', {}).get('precondition_errors', [])
            reason_map = {
                'missing_classes': 'faltan clases para el período',
                'missing_teachers': 'faltan docentes asignados en una o más clases',
                'missing_classrooms': 'faltan aulas asignadas en una o más clases',
                'missing_time_slots': 'faltan franjas horarias del período',
            }
            if preconditions:
                reasons = [reason_map[key] for key in preconditions if key in reason_map]
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
            TimetableRun.objects.select_for_update().filter(period=run.period, status='published').exclude(id=run.id).update(
                status='completed'
            )
            run.status = 'published'
            run.save(update_fields=['status', 'updated_at'])
        return Response(TimetableRunSerializer(run).data)


class ScheduleAssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ScheduleAssignmentSerializer

    def get_queryset(self):
        qs = ScheduleAssignment.objects.select_related('run', 'cls__subject', 'slot', 'classroom', 'teacher').all()
        run = self.request.query_params.get('run')
        period = self.request.query_params.get('period')
        cls = self.request.query_params.get('cls')
        if run:
            qs = qs.filter(run_id=run)
        if period:
            qs = qs.filter(run__period_id=period)
        if cls:
            qs = qs.filter(cls_id=cls)
        return qs

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
