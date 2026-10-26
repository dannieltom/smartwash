import base64
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from clientes.models import Cliente
from core.permissions import (
    AdministradorORecepcionista,
    OperarioSoloSusOrdenes,
    RecepcionEscribe,
    SoloAdministrador,
    SoloAdministradorEscribe,
    SoloOperario,
)

from .avisos import avisar_orden_lista
from .historial import operacion_sobre_orden, registrar_evento
from .models import (
    CambioConfiguracionDescuento,
    ConfiguracionDescuentoNovedad,
    DanoPrenda,
    FotoDano,
    FotoNovedad,
    HistorialOrden,
    Novedad,
    Orden,
    Prenda,
    clasificacion_por_consumo,
)
from .serializers import (
    AgregarServicioSerializer,
    AsignacionSerializer,
    CambioEstadoSerializer,
    CancelacionSerializer,
    ConsultaPublicaSerializer,
    ConfiguracionDescuentoNovedadSerializer,
    DanoPrendaSerializer,
    DecisionNovedadSerializer,
    EntregaSerializer,
    HistorialOrdenSerializer,
    NovedadEntradaSerializer,
    NovedadSerializer,
    OperarioSerializer,
    OrdenAlertaSerializer,
    OrdenBandejaSerializer,
    OrdenConNovedadSerializer,
    OrdenHistorialClienteSerializer,
    OrdenSerializer,
    PagoDanoSerializer,
    PrendaEntradaSerializer,
    agregar_prenda,
    agregar_servicio,
    asignar_operario,
    exigir_orden_editable,
    guardar_recalculo,
    nombre_usuario,
    operarios_activos,
    registrar_danos,
    registrar_decision,
    registrar_novedades,
    sin_ceros,
)

Evento = HistorialOrden.TipoEvento


def ordenes_con_detalle():
    return Orden.objects.select_related("cliente").prefetch_related(
        "prendas__tipo_prenda",
        "prendas__material",
        "prendas__servicios__tarifa__servicio",
        "prendas__dano",
    )


class OrdenListCreateView(generics.ListCreateAPIView):
    serializer_class = OrdenSerializer
    permission_classes = [RecepcionEscribe]

    def get_queryset(self):
        ordenes = ordenes_con_detalle()
        if self.request.user.rol == User.Rol.OPERARIO:
            return ordenes.filter(operario=self.request.user)
        return ordenes


class AlertasVencimientoView(generics.ListAPIView):
    serializer_class = OrdenAlertaSerializer
    # Antes de "Recibida" no hay fecha estimada; despues de "Lista" ya no hay que alertar.
    ESTADOS_CON_ALERTA = (
        Orden.Estado.RECIBIDA,
        Orden.Estado.CLASIFICADA,
        Orden.Estado.EN_PROCESO,
        Orden.Estado.CONTROL_CALIDAD,
        Orden.Estado.LISTA,
        Orden.Estado.CON_NOVEDAD,
    )

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "hoy": self.hoy}

    def get_queryset(self):
        # localdate usa TIME_ZONE (America/Bogota): "hoy" es el de la lavanderia, no el de UTC.
        self.hoy = timezone.localdate()
        limite = self.hoy + timedelta(days=getattr(settings, "ORDEN_DIAS_ALERTA", 2))
        ordenes = Orden.objects.filter(
            estado__in=self.ESTADOS_CON_ALERTA,
            fecha_estimada_entrega__isnull=False,
            fecha_estimada_entrega__lte=limite,
        )
        if self.request.user.rol == User.Rol.OPERARIO:
            ordenes = ordenes.filter(operario=self.request.user)
        # La fecha mas antigua primero: las mas retrasadas encabezan la lista.
        return ordenes.select_related("cliente").order_by("fecha_estimada_entrega", "creado_en")


class ConsultaPublicaView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, codigo):
        orden = Orden.objects.filter(codigo=codigo).first()
        if orden is None:
            raise NotFound("No encontramos una orden con ese codigo. Revisa el comprobante.")
        return Response(ConsultaPublicaSerializer(orden).data)


class OrdenDetailView(generics.RetrieveAPIView):
    serializer_class = OrdenSerializer
    permission_classes = [IsAuthenticated, OperarioSoloSusOrdenes]

    def get_queryset(self):
        return ordenes_con_detalle()


class BandejaOperarioView(generics.ListAPIView):
    serializer_class = OrdenBandejaSerializer
    permission_classes = [SoloOperario]
    # Sin operario no hay "En espera"; se excluye igual por si un camino futuro lo permite.
    ESTADOS_FUERA_DE_BANDEJA = (
        Orden.Estado.EN_ESPERA,
        Orden.Estado.ENTREGADA,
        Orden.Estado.CANCELADA,
    )

    def get_queryset(self):
        # Una prenda danada o perdida ya no se procesa aunque la orden vuelva a proceso.
        por_procesar = Prenda.objects.filter(dano__isnull=True).select_related(
            "tipo_prenda", "material"
        ).prefetch_related("servicios__tarifa__servicio")
        return (
            Orden.objects.filter(operario=self.request.user)
            .exclude(estado__in=self.ESTADOS_FUERA_DE_BANDEJA)
            .prefetch_related(Prefetch("prendas", por_procesar))
            .order_by("fecha_estimada_entrega", "creado_en")
        )


def orden_para_editar(pk):
    # El bloqueo evita que dos recepcionistas recalculen el total a la vez.
    orden = get_object_or_404(Orden.objects.select_for_update(), pk=pk)
    exigir_orden_editable(orden)
    return orden


def respuesta_orden(orden):
    return Response(
        OrdenSerializer(ordenes_con_detalle().get(pk=orden.pk)).data,
        status=status.HTTP_201_CREATED,
    )


class AgregarPrendaView(APIView):
    permission_classes = [AdministradorORecepcionista]

    def post(self, request, pk):
        entrada = PrendaEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        with operacion_sobre_orden():
            orden = orden_para_editar(pk)
            prenda = agregar_prenda(orden, entrada.validated_data, request.user)
            guardar_recalculo(orden, request.user)
            registrar_evento(
                orden,
                Evento.PRENDA_AGREGADA,
                request.user,
                f"{prenda}. Nuevo total ${orden.valor_total}",
            )
        return respuesta_orden(orden)


class AgregarServicioView(APIView):
    permission_classes = [AdministradorORecepcionista]

    def post(self, request, pk, prenda_pk):
        with operacion_sobre_orden():
            orden = orden_para_editar(pk)
            prenda = get_object_or_404(Prenda, pk=prenda_pk, orden=orden)
            entrada = AgregarServicioSerializer(data=request.data, context={"prenda": prenda})
            entrada.is_valid(raise_exception=True)
            linea = agregar_servicio(prenda, entrada.validated_data["servicio"], request.user)
            guardar_recalculo(orden, request.user)
            registrar_evento(
                orden,
                Evento.SERVICIO_AGREGADO,
                request.user,
                f"{linea} (${linea.valor_aplicado}). Nuevo total ${orden.valor_total}",
            )
        return respuesta_orden(orden)


def reclasificar_cliente(cliente, usuario):
    """Actualiza la clasificacion por consumo y devuelve la nota para el historial."""
    anterior = cliente.clasificacion
    cliente.clasificacion = clasificacion_por_consumo(cliente)
    if cliente.clasificacion == anterior:
        return ""
    cliente.registrar_autoria(usuario)
    cliente.save(update_fields=["clasificacion", "actualizado_por", "actualizado_en"])
    return f". Cliente: {anterior} → {cliente.clasificacion}"


def entregar_orden(orden, usuario, detalle):
    """Cierra la orden y devuelve lo pagado de mas si los descuentos bajaron el total."""
    saldo_a_favor = orden.saldo_a_favor()
    anterior = orden.estado
    # save() exige el pago completo (HU24) e indica el saldo si falta.
    orden.estado = Orden.Estado.ENTREGADA
    orden.fecha_entrega = timezone.now()
    orden.registrar_autoria(usuario)
    orden.save()
    registrar_evento(
        orden,
        Evento.ENTREGA,
        usuario,
        f"{anterior} → Entregada. {detalle}" + reclasificar_cliente(orden.cliente, usuario),
    )
    if saldo_a_favor > 0:
        # Los pagos no se tocan: la devolucion queda solo en el historial, como en HU13.
        registrar_evento(
            orden,
            Evento.DEVOLUCION,
            usuario,
            f"${saldo_a_favor} devueltos al cliente: lo pagado supera el total con "
            f"descuentos (${orden.valor_total})",
        )


class RegistrarEntregaView(APIView):
    permission_classes = [AdministradorORecepcionista]

    def post(self, request, pk):
        entrada = EntregaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        with operacion_sobre_orden():
            orden = get_object_or_404(Orden.objects.select_for_update(), pk=pk)
            if orden.estado != Orden.Estado.LISTA:
                raise serializers.ValidationError(
                    {"estado": f'La orden esta "{orden.estado}"; solo se entrega desde "Lista para entrega".'}
                )
            novedades, danos = entrada.verificar_contra(orden)
            if danos:
                registrar_danos(orden, danos, request.user)
            if novedades:
                registrar_novedades(orden, novedades, Novedad.Origen.ENTREGA, request.user)
            else:
                verificadas = len(entrada.validated_data["prendas"])
                detalle = (
                    f"{verificadas} prendas verificadas, {len(danos)} con daño o pérdida"
                    if danos
                    else f"{verificadas} prendas verificadas, todas coinciden con lo solicitado"
                )
                entregar_orden(orden, request.user, detalle)
        return Response(OrdenSerializer(ordenes_con_detalle().get(pk=orden.pk)).data)


def puede_cambiar_estado(usuario, orden):
    if usuario.rol == User.Rol.ADMINISTRADOR:
        return True
    if orden.estado == Orden.Estado.RECIBIDA:
        return usuario.rol == User.Rol.RECEPCIONISTA
    return usuario.rol == User.Rol.OPERARIO and orden.operario_id == usuario.pk


class CambiarEstadoView(APIView):
    def post(self, request, pk):
        entrada = CambioEstadoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        nuevo = entrada.validated_data["estado"]
        with operacion_sobre_orden():
            orden = get_object_or_404(Orden.objects.select_for_update(), pk=pk)
            if not puede_cambiar_estado(request.user, orden):
                raise PermissionDenied("No tienes permiso para cambiar el estado de esta orden.")
            anterior = orden.estado
            orden.cambiar_estado(nuevo)
            orden.registrar_autoria(request.user)
            orden.save()
            detalle = f"{anterior} → {nuevo}"
            if nuevo == Orden.Estado.EN_PROCESO and anterior == Orden.Estado.CONTROL_CALIDAD:
                detalle += f" (reproceso {orden.numero_reprocesos})"
            registrar_evento(orden, Evento.CAMBIO_ESTADO, request.user, detalle)
            if nuevo == Orden.Estado.LISTA:
                transaction.on_commit(lambda: avisar_orden_lista(orden))
        return Response(OrdenSerializer(ordenes_con_detalle().get(pk=orden.pk)).data)


class CancelarOrdenView(APIView):
    permission_classes = [AdministradorORecepcionista]

    def post(self, request, pk):
        entrada = CancelacionSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        motivo = entrada.validated_data["motivo"]
        with operacion_sobre_orden():
            orden = get_object_or_404(Orden.objects.select_for_update(), pk=pk)
            anterior = orden.estado
            operario = orden.operario
            orden.cancelar(motivo)
            orden.registrar_autoria(request.user)
            orden.save()
            detalle = f"{anterior} → {orden.estado}. Motivo: {motivo}"
            if operario is not None:
                detalle += f". Sale de la bandeja de {nombre_usuario(operario)}"
            registrar_evento(orden, Evento.CANCELACION, request.user, detalle)
            # Los pagos no se tocan: la devolucion queda solo en el historial.
            pagado = orden.total_pagado()
            if pagado > 0:
                registrar_evento(
                    orden,
                    Evento.DEVOLUCION,
                    request.user,
                    f"${pagado} devueltos al cliente. Motivo: {motivo}",
                )
        return Response(OrdenSerializer(ordenes_con_detalle().get(pk=orden.pk)).data)


class AsignarOperarioView(APIView):
    permission_classes = [AdministradorORecepcionista]

    def post(self, request, pk):
        with operacion_sobre_orden():
            orden = get_object_or_404(Orden.objects.select_for_update(), pk=pk)
            # Se valida con la orden bloqueada para leer el estado del operario
            # dentro de la misma transaccion que la asignacion.
            entrada = AsignacionSerializer(data=request.data)
            entrada.is_valid(raise_exception=True)
            tipo, detalle = asignar_operario(
                orden, entrada.validated_data["operario"], request.user
            )
            registrar_evento(orden, tipo, request.user, detalle)
        return Response(OrdenSerializer(ordenes_con_detalle().get(pk=orden.pk)).data)


class OperariosActivosView(generics.ListAPIView):
    serializer_class = OperarioSerializer
    permission_classes = [AdministradorORecepcionista]

    def get_queryset(self):
        return operarios_activos().order_by("first_name", "last_name", "username")


class HistorialOrdenView(generics.ListAPIView):
    """Solo lectura: el historial no expone escritura por ningun metodo."""

    serializer_class = HistorialOrdenSerializer
    permission_classes = [AdministradorORecepcionista]

    def get_queryset(self):
        orden = get_object_or_404(Orden, pk=self.kwargs["pk"])
        return orden.historial.select_related("usuario")


class HistorialClienteView(APIView):
    permission_classes = [AdministradorORecepcionista]

    def get(self, request, pk):
        cliente = get_object_or_404(Cliente, pk=pk)
        ordenes = cliente.ordenes.order_by("-creado_en", "-id")
        # Las canceladas se listan pero no son compra.
        total = ordenes.exclude(estado=Orden.Estado.CANCELADA).aggregate(
            total=Sum("valor_total")
        )["total"]
        return Response(
            {
                "cliente": {"id": cliente.pk, "nombre_completo": cliente.nombre_completo},
                "numero_ordenes": ordenes.count(),
                "total_comprado": serializers.DecimalField(
                    max_digits=12, decimal_places=2
                ).to_representation(total or 0),
                "ordenes": OrdenHistorialClienteSerializer(ordenes, many=True).data,
            }
        )


def exigir_acceso_a_la_orden(usuario, orden):
    if usuario.rol == User.Rol.OPERARIO and orden.operario_id != usuario.pk:
        raise PermissionDenied("La orden no esta asignada a este operario.")


class NovedadesOrdenView(APIView):
    ESTADOS_CON_PROCESO = (Orden.Estado.EN_PROCESO, Orden.Estado.CONTROL_CALIDAD)

    def get(self, request, pk):
        orden = get_object_or_404(Orden, pk=pk)
        exigir_acceso_a_la_orden(request.user, orden)
        novedades = orden.novedades.select_related(
            "prenda__tipo_prenda", "prenda__material", "creado_por", "foto"
        )
        return Response(NovedadSerializer(novedades, many=True).data)

    def post(self, request, pk):
        if request.user.rol == User.Rol.RECEPCIONISTA:
            raise PermissionDenied(
                "Durante el proceso registran la novedad el operario asignado o el administrador."
            )
        exigir_acceso_a_la_orden(request.user, get_object_or_404(Orden, pk=pk))
        entrada = NovedadEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        with operacion_sobre_orden():
            orden = get_object_or_404(Orden.objects.select_for_update(), pk=pk)
            if orden.estado not in self.ESTADOS_CON_PROCESO:
                raise serializers.ValidationError(
                    {
                        "estado": f'La orden esta "{orden.estado}"; la novedad se registra '
                        'con la orden "En proceso" o "Control de calidad".'
                    }
                )
            prenda = orden.prendas.filter(pk=datos["prenda"]).first()
            if prenda is None:
                raise serializers.ValidationError({"prenda": "La prenda no pertenece a la orden."})
            registrar_novedades(
                orden,
                [(prenda, datos["descripcion"], datos["foto"])],
                Novedad.Origen.PROCESO,
                request.user,
            )
        novedad = orden.novedades.select_related("creado_por", "foto").last()
        return Response(NovedadSerializer(novedad).data, status=status.HTTP_201_CREATED)


class FotoNovedadView(APIView):
    def get(self, request, pk):
        foto = get_object_or_404(FotoNovedad.objects.select_related("novedad__orden"), novedad=pk)
        exigir_acceso_a_la_orden(request.user, foto.novedad.orden)
        return HttpResponse(base64.b64decode(foto.contenido), content_type=foto.tipo)


class OrdenesConNovedadView(generics.ListAPIView):
    serializer_class = OrdenConNovedadSerializer
    permission_classes = [AdministradorORecepcionista]

    def get_queryset(self):
        pendientes = Novedad.objects.pendientes().select_related(
            "prenda__tipo_prenda", "prenda__material", "creado_por", "foto"
        )
        return (
            Orden.objects.filter(estado=Orden.Estado.CON_NOVEDAD)
            .select_related("cliente", "operario")
            .prefetch_related(Prefetch("novedades", pendientes, to_attr="novedades_pendientes"))
        )


class DecisionNovedadView(APIView):
    permission_classes = [AdministradorORecepcionista]

    def post(self, request, pk):
        entrada = DecisionNovedadSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        with operacion_sobre_orden():
            orden = get_object_or_404(Orden.objects.select_for_update(), pk=pk)
            registrar_decision(orden, datos, request.user)
            if datos["decision"] == Novedad.Decision.ENTREGAR_CON_DESCUENTO:
                entregar_orden(
                    orden, request.user, "El cliente acepta las prendas con novedad con descuento"
                )
        return Response(OrdenSerializer(ordenes_con_detalle().get(pk=orden.pk)).data)


ETIQUETAS_CONFIGURACION = {
    "porcentaje_leve": ("Leve", " %"),
    "porcentaje_moderada": ("Moderada", " %"),
    "porcentaje_notoria": ("Notoria", " %"),
    "porcentaje_reproceso": ("Reproceso", " %"),
    "monto_minimo": ("Monto minimo", ""),
    "tope_porcentaje": ("Tope", " %"),
}


class DescuentosNovedadView(APIView):
    permission_classes = [SoloAdministradorEscribe]

    def get(self, request):
        configuracion = ConfiguracionDescuentoNovedad.actual()
        return Response(ConfiguracionDescuentoNovedadSerializer(configuracion).data)

    def patch(self, request):
        with transaction.atomic():
            configuracion = ConfiguracionDescuentoNovedad.objects.select_for_update().get(
                pk=ConfiguracionDescuentoNovedad.actual().pk
            )
            entrada = ConfiguracionDescuentoNovedadSerializer(
                configuracion, data=request.data, partial=True
            )
            entrada.is_valid(raise_exception=True)
            cambios = []
            for campo, (etiqueta, unidad) in ETIQUETAS_CONFIGURACION.items():
                anterior, nuevo = getattr(configuracion, campo), entrada.validated_data.get(campo)
                if nuevo is not None and nuevo != anterior:
                    cambios.append(
                        f"{etiqueta}: {sin_ceros(anterior)}{unidad} → {sin_ceros(nuevo)}{unidad}"
                    )
            configuracion.registrar_autoria(request.user)
            entrada.save()
            if cambios:
                CambioConfiguracionDescuento.objects.create(
                    usuario=request.user, detalle="; ".join(cambios)
                )
        return Response(ConfiguracionDescuentoNovedadSerializer(configuracion).data)


class CambiosDescuentosNovedadView(APIView):
    permission_classes = [SoloAdministrador]

    def get(self, request):
        cambios = CambioConfiguracionDescuento.objects.select_related("usuario")
        return Response(
            [
                {"fecha": c.fecha, "usuario_nombre": nombre_usuario(c.usuario), "detalle": c.detalle}
                for c in cambios
            ]
        )


class DanosView(generics.ListAPIView):
    serializer_class = DanoPrendaSerializer
    permission_classes = [AdministradorORecepcionista]

    def get_queryset(self):
        danos = DanoPrenda.objects.select_related(
            "orden__cliente",
            "prenda__tipo_prenda",
            "prenda__material",
            "operario",
            "creado_por",
            "pagado_por",
            "foto",
        )
        estado = self.request.query_params.get("estado")
        if estado in DanoPrenda.Estado.values:
            danos = danos.filter(estado=estado)
        # Lo pendiente de pago primero: es lo que hay que atender.
        return danos.order_by("-estado", "-creado_en", "-id")


class PagoDanoView(APIView):
    permission_classes = [SoloAdministrador]

    def post(self, request, pk):
        entrada = PagoDanoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        with operacion_sobre_orden():
            dano = get_object_or_404(DanoPrenda.objects.select_for_update(), pk=pk)
            if dano.estado == DanoPrenda.Estado.PAGADO:
                raise serializers.ValidationError({"estado": "Este caso ya esta pagado."})
            dano.estado = DanoPrenda.Estado.PAGADO
            dano.pagado_por = request.user
            dano.pagado_en = timezone.now()
            dano.observacion_pago = entrada.validated_data["observacion"]
            dano.registrar_autoria(request.user)
            dano.save()
            registrar_evento(
                dano.orden,
                Evento.PAGO_DANO,
                request.user,
                f"${dano.valor_declarado} pagados al cliente por {dano.get_tipo_display().lower()} "
                f"de {dano.prenda}. {dano.observacion_pago}",
            )
        return Response(DanoPrendaSerializer(dano).data)


class FotoDanoView(APIView):
    permission_classes = [AdministradorORecepcionista]

    def get(self, request, pk):
        foto = get_object_or_404(FotoDano, dano=pk)
        return HttpResponse(base64.b64decode(foto.contenido), content_type=foto.tipo)
