from rest_framework.permissions import BasePermission


class IsAdminOrManagement(BasePermission):
    """Permite acceso solo a usuarios con rol 'a' (admin) o 'm' (gestión)."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ('a', 'm')


class IsStudent(BasePermission):
    """Permite acceso solo a usuarios con rol 's' (estudiante)."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 's'
