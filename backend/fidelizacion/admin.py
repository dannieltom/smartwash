from django.contrib import admin

from core.admin import AutoriaAdminMixin

from .models import (
    BeneficioInactividad,
    ComunicacionPromocional,
    Promocion,
    ReglaDescuento,
    ReglaInactividad,
    SegmentoPromocion,
)


@admin.register(ReglaDescuento)
class ReglaDescuentoAdmin(AutoriaAdminMixin):
    list_display = ("nombre", "tipo", "valor", "clasificacion_cliente", "activa", "vigente_desde")
    list_filter = ("tipo", "activa", "clasificacion_cliente")
    search_fields = ("nombre",)


class SegmentoPromocionInline(admin.TabularInline):
    model = SegmentoPromocion
    extra = 1


@admin.register(Promocion)
class PromocionAdmin(AutoriaAdminMixin):
    list_display = ("nombre", "tipo", "valor", "activa", "vigente_desde", "vigente_hasta")
    list_filter = ("tipo", "activa")
    search_fields = ("nombre",)
    inlines = [SegmentoPromocionInline]


@admin.register(ReglaInactividad)
class ReglaInactividadAdmin(AutoriaAdminMixin):
    list_display = ("nombre", "dias_sin_compra", "puntos", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre",)


@admin.register(BeneficioInactividad)
class BeneficioInactividadAdmin(admin.ModelAdmin):
    list_display = ("cliente", "regla", "puntos", "ultima_actividad", "otorgado_en")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ComunicacionPromocional)
class ComunicacionPromocionalAdmin(admin.ModelAdmin):
    list_display = ("promocion", "cliente", "correo", "enviada_en")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
