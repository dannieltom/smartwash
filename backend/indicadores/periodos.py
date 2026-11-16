import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.utils import timezone
from rest_framework import serializers

MAX_DIAS_RANGO = 366
PARAMETROS = ("dia", "mes", "desde", "hasta")


@dataclass(frozen=True)
class Periodo:
    tipo: str
    desde: date
    hasta: date

    @property
    def inicio(self):
        return timezone.make_aware(datetime.combine(self.desde, time.min))

    @property
    def fin(self):
        return timezone.make_aware(datetime.combine(self.hasta + timedelta(days=1), time.min))

    @property
    def dias(self):
        return [self.desde + timedelta(days=n) for n in range((self.hasta - self.desde).days + 1)]

    def es_hoy(self, hoy):
        return self.tipo == "dia" and self.desde == hoy

    def como_dict(self):
        return {"tipo": self.tipo, "desde": self.desde.isoformat(), "hasta": self.hasta.isoformat()}


def _fecha(params, nombre):
    texto = params.get(nombre, "").strip()
    try:
        return date.fromisoformat(texto)
    except ValueError:
        raise serializers.ValidationError({nombre: "Usa el formato AAAA-MM-DD."}) from None


def _no_futuro(fecha, hoy, nombre):
    if fecha > hoy:
        raise serializers.ValidationError({nombre: "No se puede consultar una fecha futura."})


def periodo_de(params, hoy=None):
    """El periodo pedido con `dia`, `mes` (AAAA-MM) o `desde` y `hasta`; hoy si no pide ninguno.

    El mes en curso llega solo hasta hoy, que es el acumulado.
    """
    hoy = hoy or timezone.localdate()
    pedidos = [nombre for nombre in PARAMETROS if params.get(nombre, "").strip()]
    if not pedidos:
        return Periodo("dia", hoy, hoy)
    if len(pedidos) > 1 and ("dia" in pedidos or "mes" in pedidos):
        raise serializers.ValidationError(
            {"detail": "Usa dia, mes o el par desde y hasta, no varios a la vez."}
        )
    if "dia" in pedidos:
        dia = _fecha(params, "dia")
        _no_futuro(dia, hoy, "dia")
        return Periodo("dia", dia, dia)
    if "mes" in pedidos:
        coincide = re.fullmatch(r"(\d{4})-(\d{2})", params["mes"].strip())
        try:
            primero = date(int(coincide[1]), int(coincide[2]), 1)
        except (TypeError, ValueError):
            raise serializers.ValidationError({"mes": "Usa el formato AAAA-MM."}) from None
        _no_futuro(primero, hoy, "mes")
        siguiente = (primero.replace(day=28) + timedelta(days=4)).replace(day=1)
        return Periodo("mes", primero, min(siguiente - timedelta(days=1), hoy))
    if len(pedidos) < 2:
        raise serializers.ValidationError({"detail": "El rango necesita desde y hasta."})
    desde, hasta = _fecha(params, "desde"), _fecha(params, "hasta")
    if hasta < desde:
        raise serializers.ValidationError({"hasta": "El rango no puede terminar antes de empezar."})
    _no_futuro(hasta, hoy, "hasta")
    if (hasta - desde).days >= MAX_DIAS_RANGO:
        raise serializers.ValidationError(
            {"hasta": f"El rango no puede pasar de {MAX_DIAS_RANGO} dias."}
        )
    return Periodo("rango", desde, hasta)
