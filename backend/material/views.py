from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.http import FileResponse
from django.utils.text import get_valid_filename
from urllib.parse import quote

from .models import Material
from .serializers import MaterialSerializer
from enrollment.models import ClassEnrollment
from notifications.utils import create_notification
from shared.permissions import IsTeacher


class MaterialViewSet(viewsets.ModelViewSet):
    serializer_class = MaterialSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [IsAuthenticated()]
        return [IsTeacher()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 't':
            return Material.objects.filter(uploaded_by=user).select_related('cls', 'uploaded_by')
        elif user.role == 's':
            from enrollment.models import ClassEnrollment
            enrolled_ids = ClassEnrollment.objects.filter(
                student=user, status='enrolled'
            ).values_list('cls_id', flat=True)
            return Material.objects.filter(cls__in=enrolled_ids).select_related('cls', 'uploaded_by')
        return Material.objects.select_related('cls', 'uploaded_by').all()

    def perform_create(self, serializer):
        file_obj = self.request.FILES.get('file')
        material = serializer.save(
            uploaded_by=self.request.user,
            original_filename=file_obj.name if file_obj else '',
        )
        subject_name = material.cls.subject.name
        uploaded_by = self.request.user.get_full_name() or self.request.user.username
        enrollments = (
            ClassEnrollment.objects
            .filter(cls=material.cls, status='enrolled')
            .select_related('student')
        )
        for enrollment in enrollments:
            if enrollment.student_id == self.request.user.id:
                continue
            create_notification(
                user=enrollment.student,
                title='Nuevo material disponible',
                message=f'Se ha añadido "{material.title}" a la clase de {subject_name}.',
                notif_type='info',
                event_type='material_added',
                context={
                    'subject_name': subject_name,
                    'material_title': material.title,
                    'uploaded_by': uploaded_by,
                    'class_name': str(material.cls),
                },
            )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=False, methods=['get'], url_path='class/(?P<class_id>[^/.]+)')
    def by_class(self, request, class_id=None):
        materials = Material.objects.filter(cls_id=class_id).select_related('cls', 'uploaded_by')
        serializer = self.get_serializer(materials, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        material = self.get_object()
        if not material.file:
            return Response({'error': 'File not found'}, status=404)

        try:
            file_handle = material.file.open('rb')
        except FileNotFoundError:
            return Response({'error': 'File not found'}, status=404)

        filename = get_valid_filename(material.original_filename or material.file.name.rsplit('/', 1)[-1])
        response = FileResponse(file_handle, as_attachment=True, filename=filename)
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
        return response
