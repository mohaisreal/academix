from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    UserRegistrationView,
    UserLoginView,
    UserLogoutView,
    CurrentUserView,
    ChangePasswordView,
    UserListView,
    UserDetailView,
    CustomTokenObtainPairView,
    StudentListView,
    TeacherListView,
)

app_name = 'users'

urlpatterns = [
    # Authentication endpoints
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),

    # JWT token endpoints
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Current user endpoints
    path('me/', CurrentUserView.as_view(), name='current_user'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),

    # User management endpoints (admin)
    path('', UserListView.as_view(), name='user_list'),

    # Role-specific list endpoints
    path('students/', StudentListView.as_view(), name='student_list'),
    path('teachers/', TeacherListView.as_view(), name='teacher_list'),

    path('<int:pk>/', UserDetailView.as_view(), name='user_detail'),
]
