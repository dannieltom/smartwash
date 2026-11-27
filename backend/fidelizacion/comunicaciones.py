import logging

from django.core.mail import send_mail
from django.db import DatabaseError, transaction
from django.utils import timezone

from clientes.models import Cliente
from notificaciones.models import Comunicacion
from ordenes.avisos import pesos
from ordenes.recordatorios import enviar_recordatorios

from .models import ComunicacionPromocional, Promocion

logger = logging.getLogger(__name__)


class ProcesoComunicacionesFallido(Exception):
    pass


def mensaje_promocion(cliente, promocion):
    if promocion.tipo == Promocion.Tipo.PORCENTAJE:
        beneficio = f"{promocion.valor.normalize():f}% de descuento"
    else:
        beneficio = f"{pesos(promocion.valor)} de descuento"
    cuerpo = (
        f"Hola {cliente.nombre_completo}, tienes {beneficio} en SmartWash con la promocion "
        f"{promocion.nombre}, valida hasta el {promocion.vigente_hasta:%d/%m/%Y}."
    )
    if promocion.descripcion:
        cuerpo += f" {promocion.descripcion}"
    return f"Promocion para ti: {promocion.nombre}", cuerpo


def enviar_promociones(hoy=None):
    """Avisa de cada promocion vigente a los clientes de sus segmentos que aun no
    la conocen. Solo registra lo que se envio, asi un fallo se reintenta despues."""
    hoy = hoy or timezone.localdate()
    resultado = {"enviados": 0, "sin_correo": 0, "fallidos": 0}
    promociones = (
        Promocion.objects.filter(activa=True, vigente_desde__lte=hoy, vigente_hasta__gte=hoy)
        .prefetch_related("segmentos")
        .order_by("vigente_hasta", "id")
    )
    for promocion in promociones:
        pendientes = Cliente.objects.filter(
            clasificacion__in=promocion.clasificaciones
        ).exclude(comunicaciones_promocionales__promocion=promocion)
        resultado["sin_correo"] += pendientes.filter(correo="").count()
        for cliente in pendientes.exclude(correo=""):
            asunto, cuerpo = mensaje_promocion(cliente, promocion)
            try:
                send_mail(asunto, cuerpo, None, [cliente.correo])
            except Exception:
                logger.exception(
                    "No se pudo enviar la promocion %s al cliente %s", promocion.pk, cliente.pk
                )
                resultado["fallidos"] += 1
                continue
            resultado["enviados"] += 1
            try:
                with transaction.atomic():
                    ComunicacionPromocional.objects.get_or_create(
                        cliente=cliente, promocion=promocion, defaults={"correo": cliente.correo}
                    )
                    Comunicacion.objects.create(
                        cliente=cliente,
                        tipo=Comunicacion.Tipo.PROMOCION,
                        promocion=promocion,
                        correo=cliente.correo,
                        asunto=asunto,
                        cuerpo=cuerpo,
                    )
            except DatabaseError:
                logger.exception(
                    "No se registro la promocion %s enviada al cliente %s", promocion.pk, cliente.pk
                )
    return resultado


def enviar_comunicaciones():
    """Recordatorios de ordenes no reclamadas y comunicaciones promocionales.

    Si la base falla se registra el error y no se aplica ningun cambio mas.
    """
    try:
        return {"recordatorios": enviar_recordatorios(), "promociones": enviar_promociones()}
    except DatabaseError as error:
        logger.exception("Fallo el envio de comunicaciones por un error de base de datos")
        raise ProcesoComunicacionesFallido from error
