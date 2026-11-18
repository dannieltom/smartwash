from django.contrib import admin

from .models import Comunicacion


@admin.register(Comunicacion)
class ComunicacionAdmin(admin.ModelAdmin):
    list_display = ("enviada_en", "tipo", "cliente", "correo", "asunto")
    list_filter = ("tipo",)
    search_fields = ("cliente__nombre_completo", "cliente__documento", "correo", "orden__codigo")
    list_select_related = ("cliente",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
