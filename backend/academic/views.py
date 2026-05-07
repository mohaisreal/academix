from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Career, Subject, AcademicPeriod, Classroom, Class, ClassSchedule
from .serializers import (
    CareerSerializer, SubjectSerializer, AcademicPeriodSerializer,
    ClassroomSerializer, ClassSerializer, ClassScheduleSerializer,
)
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

        schedule_data = []
        for i, cls in enumerate(classes):
            for sched in cls.schedules.all():
                schedule_data.append({
                    'schedule_id': sched.id,
                    'class_id': cls.id,
                    'subject_name': cls.subject.name,
                    'subject_code': cls.subject.code,
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
