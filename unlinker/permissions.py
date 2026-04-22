from rest_framework.permissions import BasePermission


class HasUnlinkingPermissions(BasePermission):
    message = "Nie masz uprawnień do podglądu tego zasobu"

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        
        has_perm = user.has_perm("unlinker.can_unlinking")
        
        return has_perm