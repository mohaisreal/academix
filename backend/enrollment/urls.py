from django.urls import path
from . import views
from .views import (
    CareerEnrollmentListCreateView,
    EnrollmentFeeDetailView,
    EnrollmentConfirmPaymentView,
    EnrollmentStripeConfigView,
    EnrollmentPayView,
    EnrollmentReceiptView,
    EnrollmentReceiptPdfView,
    EnrollmentCompleteView,
    ClassEnrollmentCreateDeleteView,
    # Vista de contexto de casos excepcionales por estudiante.
    ConvocationGraceGrantView,
    ConvocationGraceDetailView,
)

urlpatterns = [
    path('my-enrollment/', views.MyEnrollmentView.as_view()),
    path('my-subjects/', views.MySubjectsView.as_view()),
    path('my-teachers/', views.MyTeachersView.as_view()),
    path('management/', views.EnrollmentManagementListCreate.as_view()),
    path('management/<int:pk>/', views.EnrollmentManagementDetail.as_view()),
    path('<int:pk>/status/', views.EnrollmentStatusView.as_view()),
    path('review/', views.EnrollmentReviewView.as_view()),
    path('review/<int:pk>/approve/', views.EnrollmentApproveView.as_view()),
    path('review/<int:pk>/reject/', views.EnrollmentRejectView.as_view()),
    # Matrícula y pago (GET + POST)
    path('career-enrollments/', CareerEnrollmentListCreateView.as_view(), name='career-enrollment-list-create'),
    path('career-enrollments/<int:pk>/fee/', EnrollmentFeeDetailView.as_view(), name='enrollment-fee'),
    path('career-enrollments/<int:pk>/pay/', EnrollmentPayView.as_view(), name='enrollment-pay'),
    path('career-enrollments/<int:pk>/confirm-payment/', EnrollmentConfirmPaymentView.as_view(), name='enrollment-confirm-payment'),
    path('career-enrollments/<int:pk>/receipt/', EnrollmentReceiptView.as_view(), name='enrollment-receipt'),
    path('career-enrollments/<int:pk>/receipt.pdf/', EnrollmentReceiptPdfView.as_view(), name='enrollment-receipt-pdf'),
    path('career-enrollments/<int:pk>/complete/', EnrollmentCompleteView.as_view(), name='enrollment-complete'),
    path('stripe/config/', EnrollmentStripeConfigView.as_view(), name='enrollment-stripe-config'),
    # Inscripción en clases (GET + POST + DELETE)
    path('class-enrollments/', ClassEnrollmentCreateDeleteView.as_view(), name='class-enrollment-list-create'),
    path('class-enrollments/<int:pk>/', ClassEnrollmentCreateDeleteView.as_view(), name='class-enrollment-delete'),
    path('students/<int:student_id>/exceptional-cases/', ConvocationGraceGrantView.as_view(), name='student-exceptional-cases'),
    path('students/<int:student_id>/convocation-graces/', ConvocationGraceGrantView.as_view(), name='convocation-grace-grant'),
    path('convocation-graces/<int:pk>/', ConvocationGraceDetailView.as_view(), name='convocation-grace-detail'),
]
