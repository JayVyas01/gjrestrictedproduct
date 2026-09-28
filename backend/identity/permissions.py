"""Role checks for API views. Usage: permission_classes = [role_required(Role.LICENSEE)]."""

from rest_framework.permissions import BasePermission


def role_required(*roles: str) -> type[BasePermission]:
    class HasRole(BasePermission):
        def has_permission(self, request, view) -> bool:
            user = request.user
            return bool(user and user.is_authenticated and user.has_role(*roles))

    HasRole.__name__ = f"HasRole({', '.join(roles)})"
    return HasRole
