from rest_framework.permissions import BasePermission


class IsStudent(BasePermission):
    """El usuario autenticado tiene rol estudiante."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 's')


class IsManagement(BasePermission):
    """El usuario autenticado tiene rol management o administration."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in ('m', 'a')
        )


class IsOwnerOrManagement(BasePermission):
    """
    A nivel de objeto:
    - Si el usuario es management/administration: acceso total.
    - Si es estudiante: solo puede acceder a sus propios recursos.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.role in ('m', 'a'):
            return True
        # Para AdmissionApplication
        if hasattr(obj, 'student'):
            return obj.student == request.user
        # Para AdmissionDocument (acceder via aplicación)
        if hasattr(obj, 'application'):
            return obj.application.student == request.user
        return False
