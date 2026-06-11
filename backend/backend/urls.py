"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles import finders
from django.http import FileResponse, Http404
import mimetypes
from users.views import health_check, RegisterView, VerifyEmailView, IdentityDocumentUploadView


def dev_static_serve(request, path):
    absolute_path = finders.find(path.lstrip('/'))
    if not absolute_path:
        raise Http404

    content_type, _ = mimetypes.guess_type(absolute_path)
    return FileResponse(open(absolute_path, 'rb'), content_type=content_type)

urlpatterns = [
    # Interfaz de administración
    path('admin/', admin.site.urls),

    # Endpoints de API
    path('api/users/', include('users.urls')),
    # Endpoints de autenticación con verificación de correo (duplicados aquí para el prefijo /api/auth/)
    path('api/auth/register/', RegisterView.as_view(), name='api-auth-register'),
    path('api/auth/verify-email/', VerifyEmailView.as_view(), name='api-auth-verify-email'),
    path('api/auth/identity-documents/', IdentityDocumentUploadView.as_view(), name='api-auth-identity-documents'),
    path('api/health/', health_check, name='health_check'),

    # Gestión académica
    path('api/academic/', include('academic.urls')),
    path('api/enrollment/', include('enrollment.urls')),
    path('api/grades/', include('grades.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/messaging/', include('messaging.urls')),
    path('api/material/', include('material.urls')),
    path('api/admissions/', include('admissions.urls')),
    path('api/questionnaire/', include('questionnaire.urls')),
]

# Sirve ficheros multimedia en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Sirve ficheros estáticos del admin en backend-dev sin collectstatic
urlpatterns += [re_path(r'^static/(?P<path>.*)$', dev_static_serve)]
