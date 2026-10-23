from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers

from core.permissions import AdministradorORecepcionista
from ordenes.historial import operacion_sobre_orden, registrar_evento
from ordenes.models import HistorialOrden, Orden

from .models import Pago
from .serializers import PagoSerializer

Evento = HistorialOrden.TipoEvento


class PagoListCreateView(generics.ListCreateAPIView):
    serializer_class = PagoSerializer
    permission_classes = [AdministradorORecepcionista]

    def get_queryset(self):
        return Pago.objects.filter(orden_id=self.kwargs["pk"])

    def create(self, request, *args, **kwargs):
        with operacion_sobre_orden():
            return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        usuario = self.request.user
        # El bloqueo serializa los pagos de una misma orden: dos cobros
        # simultaneos no pueden superar juntos el saldo.
        orden = get_object_or_404(Orden.objects.select_for_update(), pk=self.kwargs["pk"])
        orden.exigir_no_cancelada()
        monto = serializer.validated_data["monto"]
        saldo = orden.saldo_pendiente()
        if monto > saldo:
            raise serializers.ValidationError(
                {"monto": f"Excede el saldo pendiente de la orden (${saldo})."}
            )

        pago = Pago(orden=orden, **serializer.validated_data)
        pago.registrar_autoria(usuario)
        pago.save()
        serializer.instance = pago

        estado_anterior = orden.estado
        if not orden.tiene_abono() and orden.total_pagado() >= orden.abono_requerido:
            orden.registrar_abono_minimo(timezone.localdate())
        orden.registrar_autoria(usuario)
        orden.save()

        registrar_evento(
            orden,
            Evento.PAGO,
            usuario,
            f"${monto} en {pago.get_metodo_display().lower()}. "
            f"Pagado ${orden.total_pagado()} de ${orden.valor_total} ({orden.estado_pago})",
        )
        if orden.estado != estado_anterior:
            registrar_evento(
                orden,
                Evento.CAMBIO_ESTADO,
                usuario,
                f"{estado_anterior} → {orden.estado}: abono minimo alcanzado. "
                f"Entrega estimada {orden.fecha_estimada_entrega}",
            )
