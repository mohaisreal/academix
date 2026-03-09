from django.urls import path
from . import views

urlpatterns = [
    path('', views.NotificationListView.as_view()),
    path('<int:pk>/mark-read/', views.MarkReadView.as_view()),
    path('mark-all-read/', views.MarkAllReadView.as_view()),
    path('unread-count/', views.UnreadCountView.as_view()),
]
