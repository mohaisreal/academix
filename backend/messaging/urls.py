from django.urls import path
from . import views

urlpatterns = [
    path('inbox/', views.InboxView.as_view()),
    path('sent/', views.SentView.as_view()),
    path('threads/', views.ThreadListView.as_view()),
    path('compose/', views.ComposeView.as_view()),
    path('unread-count/', views.UnreadMessageCountView.as_view()),
    path('<int:pk>/', views.MessageThreadView.as_view()),
    path('<int:pk>/reply/', views.ReplyView.as_view()),
    path('<int:pk>/mark-read/', views.MarkMessageReadView.as_view()),
]
