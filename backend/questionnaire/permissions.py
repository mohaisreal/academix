from rest_framework.permissions import BasePermission


class IsAdminOrManagement(BasePermission):
    """Allow access only to users with role 'a' (admin) or 'm' (management)."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ('a', 'm')


class IsStudent(BasePermission):
    """Allow access only to users with role 's' (student)."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 's'
