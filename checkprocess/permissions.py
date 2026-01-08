from rest_framework.permissions import BasePermission


class HasPermCanSeeAdminPage(BasePermission):
    message = "Nie masz uprawnień do podglądu tego zasobu"

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        
        has_perm = user.has_perm("checkprocess.can_see_admin_page")
        
        return has_perm
    

class HasPermCanUpdateAdminPage(BasePermission):
    message = "Nie masz uprawnień do modyfikowania tego zasobu"

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        
        has_perm = user.has_perm("checkprocess.can_update_object_admin_page")
        
        return has_perm