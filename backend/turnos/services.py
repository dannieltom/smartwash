from datetime import datetime, time, timedelta

from django.db.models import Exists, OuterRef
from django.utils import timezone

from ordenes.models import ESTADOS_FUERA_DE_BANDEJA, Orden

from .models import Turno


def inicio_del_dia(momento):
    """00:00 del dia local (America/Bogota) de `momento`."""
    return timezone.make_aware(datetime.combine(timezone.localtime(momento).date(), time.min))


def turno_vigente(operario, ahora=None):
    """El turno abierto del operario si empezo hoy; uno abierto de un dia anterior se cierra solo.

    El cierre es perezoso (al consultar o al iniciar otro turno): no hay tareas programadas.
    """
    ahora = ahora or timezone.now()
    abierto = Turno.objects.filter(operario=operario, fin__isnull=True).first()
    if abierto is None:
        return None
    if abierto.inicio >= inicio_del_dia(ahora):
        return abierto
    abierto.cerrar(inicio_del_dia(abierto.inicio) + timedelta(days=1) - timedelta(microseconds=1), Turno.Cierre.AUTOMATICO)
    return None


def esta_en_turno(ahora=None):
    """Expresion para anotar operarios: True si tienen un turno abierto que empezo hoy."""
    return Exists(
        Turno.objects.filter(operario=OuterRef("pk"), fin__isnull=True, inicio__gte=inicio_del_dia(ahora or timezone.now()))
    )


def ordenes_activas(operario):
    """Las ordenes de su bandeja: la misma definicion que BandejaOperarioView."""
    return Orden.objects.filter(operario=operario).exclude(estado__in=ESTADOS_FUERA_DE_BANDEJA)
