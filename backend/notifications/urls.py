from django.urls import path
from . import views

urlpatterns = [
    path('', views.NotificationListView.as_view()),
    path('<int:pk>/mark-read/', views.MarkReadView.as_view()),
    path('mark-all-read/', views.MarkAllReadView.as_view()),
    path('unread-count/', views.UnreadCountView.as_view()),
    path('preferences/', views.EmailPreferenceView.as_view()),
    path('email-preferences/', views.EmailPreferenceView.as_view()),
    path('system-settings/', views.SystemSettingsView.as_view()),
    # CRUD de plantillas de correo
    path('email-templates/', views.EmailTemplateListCreateView.as_view()),
    path('email-templates/<int:pk>/', views.EmailTemplateDetailView.as_view()),
    path('email-templates/<int:pk>/preview/', views.EmailTemplatePreviewView.as_view()),
    path('email-templates/<int:pk>/send-test/', views.EmailTemplateSendTestView.as_view()),
]
