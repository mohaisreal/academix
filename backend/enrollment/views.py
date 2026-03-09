from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.db.models import Avg

from .models import CareerEnrollment, ClassEnrollment
from .serializers import CareerEnrollmentSerializer, ClassEnrollmentSerializer
from academic.models import AcademicPeriod
from shared.permissions import IsAdminOrManagement, IsStudent

User = get_user_model()


class MyEnrollmentView(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        career_enrollment = (
            CareerEnrollment.objects
            .filter(student=request.user, status='active')
            .select_related('career', 'period')
            .first()
        )
        if not career_enrollment:
            return Response({'career_enrollment': None, 'class_enrollments': []})

        class_enrollments = (
            ClassEnrollment.objects
            .filter(student=request.user, cls__period=career_enrollment.period, status='enrolled')
            .select_related('cls__subject', 'cls__teacher', 'cls__classroom', 'cls__period')
            .prefetch_related('cls__schedules')
        )
        return Response({
            'career_enrollment': CareerEnrollmentSerializer(career_enrollment).data,
            'class_enrollments': ClassEnrollmentSerializer(class_enrollments, many=True).data,
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
            grades = Grade.objects.filter(student=request.user, evaluation__in=evals)
            avg = grades.aggregate(a=Avg('score'))['a']
            t = enr.cls.teacher
            result.append({
                'enrollment_id': enr.id,
                'class_id': enr.cls.id,
                'subject': {
                    'id': enr.cls.subject.id,
                    'name': enr.cls.subject.name,
                    'code': enr.cls.subject.code,
                    'credits': enr.cls.subject.credits,
                    'hours_per_week': enr.cls.subject.hours_per_week,
                },
                'teacher': {
                    'id': t.id,
                    'full_name': f"{t.first_name} {t.last_name}".strip() or t.username,
                    'email': t.email,
                    'profile_image': t.profile_image.url if t.profile_image else None,
                } if t else None,
                'period': {'id': enr.cls.period.id, 'name': enr.cls.period.name},
                'classroom': str(enr.cls.classroom) if enr.cls.classroom else None,
                'current_grade': round(float(avg), 1) if avg is not None else None,
                'status': enr.status,
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
            return Response({'error': f'Invalid status. Must be one of: {valid}'}, status=400)
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
