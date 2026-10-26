from django.contrib import admin

from core.admin import AutoriaAdminMixin

from .historial import registrar_evento
from .models import HistorialOrden, Orden, OrdenServicio, Prenda

Evento = HistorialOrden.TipoEvento


def _nombre(usuario):
    return usuario.username if usuario else "sin operario"


def eventos_por_cambio(anterior, actual):
    eventos = []
    if anterior.operario_id != actual.operario_id:
        tipo = Evento.ASIGNACION if anterior.operario_id is None else Evento.REASIGNACION
        eventos.append(
            (tipo, f"{_nombre(anterior.operario)} → {_nombre(actual.operario)}")
        )
    if anterior.estado != actual.estado:
        tipo = Evento.ENTREGA if actual.estado == Orden.Estado.ENTREGADA else Evento.CAMBIO_ESTADO
        eventos.append((tipo, f"{anterior.estado} → {actual.estado}"))
    return eventos


def registrar_alta(obj, usuario):
    if isinstance(obj, Prenda):
        registrar_evento(obj.orden, Evento.PRENDA_AGREGADA, usuario, str(obj))
    elif isinstance(obj, OrdenServicio):
        orden = obj.prenda.orden
        orden.recalcular()
        orden.save()
        registrar_evento(
            obj.prenda.orden,
            Evento.SERVICIO_AGREGADO,
            usuario,
            f"{obj} (${obj.valor_aplicado})",
        )


class HistorialEnAltasMixin:
    # El admin envuelve cada guardado en una transaccion, asi que el cambio y
    # su registro se revierten juntos si algo falla.
    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        for obj in formset.new_objects:
            registrar_alta(obj, request.user)


class PrendaInline(admin.TabularInline):
    model = Prenda
    extra = 0


class OrdenServicioInline(admin.TabularInline):
    model = OrdenServicio
    extra = 0


class HistorialOrdenInline(admin.TabularInline):
    model = HistorialOrden
    fields = readonly_fields = ("fecha", "tipo_evento", "usuario", "detalle")
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Orden)
class OrdenAdmin(HistorialEnAltasMixin, AutoriaAdminMixin):
    list_display = (
        "codigo",
        "cliente",
        "estado",
        "estado_pago",
        "operario",
        "valor_total",
    )
    list_filter = ("estado", "estado_pago", "operario")
    search_fields = ("codigo", "cliente__documento", "cliente__nombre_completo")
    readonly_fields = AutoriaAdminMixin.readonly_fields + (
        "codigo",
        "estado_pago",
        "subtotal",
        "descuento",
        "descuento_novedad",
        "descuento_dano",
        "valor_total",
        "abono_requerido",
        "duracion_estimada_dias",
        "fecha_estimada_entrega",
        "abono_alcanzado_en",
    )
    inlines = [PrendaInline, HistorialOrdenInline]

    def get_readonly_fields(self, request, obj=None):
        # Una orden "Con novedad" solo sale con la decision del cliente (HU19).
        if obj is not None and obj.estado == Orden.Estado.CON_NOVEDAD:
            return (*super().get_readonly_fields(request, obj), "estado")
        return super().get_readonly_fields(request, obj)

    def save_model(self, request, obj, form, change):
        anterior = Orden.objects.get(pk=obj.pk) if change else None
        super().save_model(request, obj, form, change)
        if anterior is None:
            registrar_evento(
                obj, Evento.CREACION, request.user, f"Orden registrada para {obj.cliente}"
            )
            return
        for tipo, detalle in eventos_por_cambio(anterior, obj):
            registrar_evento(obj, tipo, request.user, detalle)


@admin.register(Prenda)
class PrendaAdmin(HistorialEnAltasMixin, AutoriaAdminMixin):
    list_display = ("orden", "tipo_prenda", "material", "cantidad")
    list_filter = ("tipo_prenda", "material")
    inlines = [OrdenServicioInline]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            registrar_alta(obj, request.user)


@admin.register(HistorialOrden)
class HistorialOrdenAdmin(admin.ModelAdmin):
    """Solo lectura: el historial no se crea, edita ni borra desde el admin."""

    list_display = ("orden", "tipo_evento", "usuario", "fecha")
    list_filter = ("tipo_evento",)
    search_fields = ("orden__codigo",)
    list_select_related = ("orden", "usuario")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
