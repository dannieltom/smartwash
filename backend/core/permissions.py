from rest_framework.permissions import SAFE_METHODS, BasePermission

from accounts.models import User


class SoloAdministradorEscribe(BasePermission):
    """Cualquier sesion consulta; solo el administrador crea o modifica."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.method in SAFE_METHODS or request.user.rol == User.Rol.ADMINISTRADOR


class SoloAdministrador(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == User.Rol.ADMINISTRADOR


class AdministradorORecepcionista(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol in (
            User.Rol.ADMINISTRADOR,
            User.Rol.RECEPCIONISTA,
        )


class RecepcionEscribe(BasePermission):
    """Cualquier sesion consulta; crean y modifican la recepcionista y el administrador."""

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.method in SAFE_METHODS or request.user.rol in (
            User.Rol.ADMINISTRADOR,
            User.Rol.RECEPCIONISTA,
        )


class SoloOperario(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.rol == User.Rol.OPERARIO


class OperarioSoloSusOrdenes(BasePermission):
    """El operario solo accede a las ordenes que tiene asignadas; los demas roles, a todas."""

    def has_object_permission(self, request, view, obj):
        if request.user.rol != User.Rol.OPERARIO:
            return True
        return obj.operario_id == request.user.pk
