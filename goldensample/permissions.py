from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied

class GoldenAdminPerms(BasePermission):
    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            raise PermissionDenied("Musisz się zalogować, aby modyfikować wzorce")

        if not user.has_perm('goldensample.can_update_create_goldens'):
            raise PermissionDenied("Nie ma uprawnień do modyfikacji listy wzorców")

        return True