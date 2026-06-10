from django.urls import path
from . import views

urlpatterns = [
    path('my-grades/', views.MyGradesView.as_view()),
    path('my-file/', views.MyFileView.as_view()),
    path('files/', views.StudentFilesView.as_view()),
    path('files/<int:student_id>/', views.StudentFileDetailView.as_view()),
    path('classes/<int:class_id>/students/<int:student_id>/final-grade/', views.StudentFinalGradeView.as_view()),
    path('evaluations/', views.EvaluationListCreateView.as_view()),
    path('evaluations/<int:pk>/', views.EvaluationDetailView.as_view()),
    path('evaluations/<int:eval_id>/submissions/', views.EvaluationSubmissionCreateView.as_view()),
    path('marking/<int:eval_id>/', views.MarkingView.as_view()),
    path('reports/<int:class_id>/', views.ClassReportView.as_view()),
    path('statistics/', views.StatisticsView.as_view()),
]
