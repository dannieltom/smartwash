import logging
from datetime import datetime, time, timedelta

from django.db import transaction
from django.db.models import F, Max, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from clientes.models import Cliente
from ordenes.models import Orden

from .models import BeneficioInactividad, ReglaInactividad

logger = logging.getLogger(__name__)


class SinReglasDeInactividad(Exception):
    pass


class ProcesoInactividadFallido(Exception):
    pass


def clientes_inactivos(dias, hoy=None):
    """Clientes sin ordenes (las canceladas no cuentan) en los ultimos `dias` dias.

    Quien nunca compro cuenta desde que se registro. Devuelve
    (cliente, ultima_actividad, dias_inactivo), del mas inactivo al menos.
    """
    hoy = hoy or timezone.localdate()
    primer_instante_activo = timezone.make_aware(
        datetime.combine(hoy - timedelta(days=dias - 1), time.min)
    )
    clientes = (
        Cliente.objects.annotate(
            ultima=Coalesce(
                Max("ordenes__creado_en", filter=~Q(ordenes__estado=Orden.Estado.CANCELADA)),
                F("creado_en"),
            )
        )
        .filter(ultima__lt=primer_instante_activo)
        .order_by("ultima", "id")
    )
    resultado = []
    for cliente in clientes:
        ultima = timezone.localtime(cliente.ultima).date()
        resultado.append((cliente, ultima, (hoy - ultima).days))
    return resultado


def asignar_beneficios_por_inactividad(hoy=None):
    """Suma los puntos de cada regla activa a los clientes que le corresponden.

    Todo o nada: si algo falla se revierte y el estado anterior se conserva. El
    error queda en el log.
    """
    hoy = hoy or timezone.localdate()
    try:
        with transaction.atomic():
            return _asignar(hoy)
    except SinReglasDeInactividad:
        raise
    except Exception as error:
        logger.exception("Fallo la asignacion de beneficios por inactividad")
        raise ProcesoInactividadFallido from error


def _asignar(hoy):
    reglas = list(ReglaInactividad.objects.filter(activa=True))
    if not reglas:
        raise SinReglasDeInactividad
    beneficios = 0
    puntos = 0
    clientes = set()
    for regla in reglas:
        for cliente, ultima, _ in clientes_inactivos(regla.dias_sin_compra, hoy):
            _, creado = BeneficioInactividad.objects.get_or_create(
                cliente=cliente,
                regla=regla,
                ultima_actividad=ultima,
                defaults={"puntos": regla.puntos},
            )
            if not creado:
                continue
            Cliente.objects.filter(pk=cliente.pk).update(puntos=F("puntos") + regla.puntos)
            beneficios += 1
            puntos += regla.puntos
            clientes.add(cliente.pk)
    return {"beneficios": beneficios, "puntos": puntos, "clientes": len(clientes)}
