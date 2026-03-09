from django.urls import path
from . import views

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
]
