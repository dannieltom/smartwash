import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import DatabaseError, transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from notificaciones.models import Comunicacion

from .avisos import pesos
from .historial import registrar_evento
from .models import HistorialOrden, Orden

logger = logging.getLogger(__name__)

MAX_RECORDATORIOS = 3
INICIO_DETALLE = "Recordatorio de orden no reclamada"
SUFIJO_LISTA = "→ Lista para entrega"


def dias_para_recordar():
    return getattr(settings, "DIAS_RECORDATORIO_ORDEN_LISTA", 3)


def ordenes_por_recordar(ahora=None):
    """Ordenes que siguen "Lista para entrega" desde hace al menos N dias y a las
    que ya les toca otro recordatorio: pasaron N dias del anterior y no se llego
    al maximo."""
    ahora = ahora or timezone.now()
    limite = ahora - timedelta(days=dias_para_recordar())
    historial = "historial"
    return (
        Orden.objects.filter(estado=Orden.Estado.LISTA)
        .annotate(
            lista_desde=Max(
                f"{historial}__fecha",
                filter=Q(
                    historial__tipo_evento=HistorialOrden.TipoEvento.CAMBIO_ESTADO,
                    historial__detalle__endswith=SUFIJO_LISTA,
                ),
            ),
            recordatorios=Count(
                historial,
                filter=Q(
                    historial__tipo_evento=HistorialOrden.TipoEvento.NOTIFICACION,
                    historial__detalle__startswith=INICIO_DETALLE,
                ),
            ),
            ultimo_recordatorio=Max(
                f"{historial}__fecha",
                filter=Q(
                    historial__tipo_evento=HistorialOrden.TipoEvento.NOTIFICACION,
                    historial__detalle__startswith=INICIO_DETALLE,
                ),
            ),
        )
        .filter(lista_desde__lte=limite, recordatorios__lt=MAX_RECORDATORIOS)
        .filter(Q(ultimo_recordatorio__isnull=True) | Q(ultimo_recordatorio__lte=limite))
        .select_related("cliente")
        .order_by("lista_desde", "id")
    )


def mensaje_recordatorio(orden, dias):
    cuerpo = (
        f"Hola {orden.cliente.nombre_completo}, tu orden {orden.codigo} lleva {dias} dias "
        "lista para recoger en SmartWash."
    )
    saldo = orden.saldo_pendiente()
    if saldo > 0:
        cuerpo += f" Saldo pendiente por pagar al recogerla: {pesos(saldo)}."
    return f"Recuerda recoger tu orden {orden.codigo}", cuerpo


def enviar_recordatorios(ahora=None):
    """Un fallo de envio no frena al resto: queda en el log y se reintenta en la
    siguiente corrida, porque el recordatorio solo se registra si se envio."""
    ahora = ahora or timezone.now()
    resultado = {"enviados": 0, "sin_correo": 0, "fallidos": 0}
    for orden in ordenes_por_recordar(ahora):
        correo = orden.cliente.correo
        if not correo:
            resultado["sin_correo"] += 1
            continue
        dias = (ahora - orden.lista_desde).days
        asunto, cuerpo = mensaje_recordatorio(orden, dias)
        try:
            send_mail(asunto, cuerpo, None, [correo])
        except Exception:
            logger.exception("No se pudo enviar el recordatorio de la orden %s", orden.codigo)
            resultado["fallidos"] += 1
            continue
        resultado["enviados"] += 1
        try:
            with transaction.atomic():
                registrar_evento(
                    orden,
                    HistorialOrden.TipoEvento.NOTIFICACION,
                    None,
                    f"{INICIO_DETALLE} enviado a {correo} "
                    f"({orden.recordatorios + 1} de {MAX_RECORDATORIOS}).",
                )
                Comunicacion.objects.create(
                    cliente=orden.cliente,
                    tipo=Comunicacion.Tipo.RECORDATORIO,
                    orden=orden,
                    correo=correo,
                    asunto=asunto,
                    cuerpo=cuerpo,
                )
        except DatabaseError:
            logger.exception("No se registro el recordatorio de la orden %s", orden.codigo)
    return resultado
