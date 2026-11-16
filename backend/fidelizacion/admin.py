from django.contrib import admin

from core.admin import AutoriaAdminMixin

from .models import Promocion, ReglaDescuento, SegmentoPromocion


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
