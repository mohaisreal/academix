from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Material
from .serializers import MaterialSerializer
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
        serializer.save(uploaded_by=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    @action(detail=False, methods=['get'], url_path='class/(?P<class_id>[^/.]+)')
    def by_class(self, request, class_id=None):
        materials = Material.objects.filter(cls_id=class_id).select_related('cls', 'uploaded_by')
        serializer = self.get_serializer(materials, many=True)
        return Response(serializer.data)
