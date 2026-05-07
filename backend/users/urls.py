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
    RegisterView,
    VerifyEmailView,
    IdentityDocumentUploadView,
    IdentityVerificationListView,
    IdentityVerificationReviewView,
)

app_name = 'users'

urlpatterns = [
    # Endpoints de autenticación con verificación de correo
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/verify-email/', VerifyEmailView.as_view(), name='auth-verify-email'),
    path('auth/identity-documents/', IdentityDocumentUploadView.as_view(), name='auth-identity-documents'),

    # Endpoints de autenticación
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),

    # Endpoints de tokens JWT
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Endpoints del usuario actual
    path('me/', CurrentUserView.as_view(), name='current_user'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),

    # Endpoints de gestión de usuarios (administración)
    path('', UserListView.as_view(), name='user_list'),

    # Endpoints de listado por rol
    path('students/', StudentListView.as_view(), name='student_list'),
    path('teachers/', TeacherListView.as_view(), name='teacher_list'),
    path('identity-verifications/', IdentityVerificationListView.as_view(), name='identity_verification_list'),
    path('identity-verifications/<int:user_id>/review/', IdentityVerificationReviewView.as_view(), name='identity_verification_review'),

    path('<int:pk>/', UserDetailView.as_view(), name='user_detail'),
]
