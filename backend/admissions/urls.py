from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import AdmissionApplicationViewSet, DocumentValidationView, PublicAdmissionResultsView

router = DefaultRouter()
router.register(r'applications', AdmissionApplicationViewSet, basename='admission-application')

urlpatterns = [
    path('', include(router.urls)),
    path('documents/<int:pk>/validate/', DocumentValidationView.as_view(), name='document-validate'),
    path('public/results/', PublicAdmissionResultsView.as_view(), name='public-admission-results'),
]
