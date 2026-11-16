import re
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from clientes.models import Cliente
from fidelizacion.models import BeneficioInactividad, Promocion, ReglaInactividad
from fidelizacion.services import clientes_inactivos
from ordenes.models import HistorialOrden, Orden, OrdenServicio, Prenda
from pagos.models import Pago

CERO = Decimal("0")
DEVUELTO = re.compile(r"^\$(\d+(?:\.\d+)?)")
NOTA_SERVICIOS = (
    "Se calcula con las ordenes que pasaron a Recibida en el periodo, mientras que la venta "
    "es lo cobrado: un pago cubre la orden completa, asi que pueden no coincidir."
)


def dinero(valor):
    return f"{Decimal(valor):.2f}"


def _monto_devuelto(detalle):
    """La devolucion solo queda escrita en el historial: "$<monto> devueltos al cliente..."."""
    coincide = DEVUELTO.match(detalle)
    return Decimal(coincide[1]) if coincide else CERO


def ventas(periodo):
    """Lo cobrado en el periodo: pagos menos devoluciones, cada uno en el dia en que se registro."""
    cobrado = {
        fila["dia"]: fila["total"]
        for fila in Pago.objects.filter(creado_en__gte=periodo.inicio, creado_en__lt=periodo.fin)
        .annotate(dia=TruncDate("creado_en"))
        .values("dia")
        .annotate(total=Sum("monto"))
    }
    devuelto = {}
    devoluciones = HistorialOrden.objects.filter(
        tipo_evento=HistorialOrden.TipoEvento.DEVOLUCION,
        fecha__gte=periodo.inicio,
        fecha__lt=periodo.fin,
    ).values_list("fecha", "detalle")
    for fecha, detalle in devoluciones:
        dia = timezone.localtime(fecha).date()
        devuelto[dia] = devuelto.get(dia, CERO) + _monto_devuelto(detalle)

    por_dia = [
        {"fecha": dia.isoformat(), "total": dinero(cobrado.get(dia, CERO) - devuelto.get(dia, CERO))}
        for dia in periodo.dias
    ]
    total = sum(cobrado.values(), CERO) - sum(devuelto.values(), CERO)
    return {
        "periodo": periodo.como_dict(),
        "total": dinero(total),
        "por_dia": por_dia,
        "sin_datos": not cobrado and not devuelto,
    }


def _lineas_recibidas(periodo):
    return OrdenServicio.objects.filter(
        prenda__orden__abono_alcanzado_en__range=(periodo.desde, periodo.hasta)
    ).exclude(prenda__orden__estado=Orden.Estado.CANCELADA)


def _ordenados(filas, limite):
    filas.sort(key=lambda fila: (-fila["cantidad"], -Decimal(fila["valor"]), fila["nombre"]))
    return filas[:limite]


def servicios_y_prendas(periodo, limite):
    lineas = _lineas_recibidas(periodo)
    servicios = [
        {
            "id": fila["tarifa__servicio_id"],
            "nombre": fila["tarifa__servicio__nombre"],
            "cantidad": fila["cantidad"],
            "valor": dinero(fila["valor"]),
        }
        for fila in lineas.values("tarifa__servicio_id", "tarifa__servicio__nombre").annotate(
            cantidad=Sum("prenda__cantidad"), valor=Sum("valor_aplicado")
        )
    ]
    valor_por_tipo = {
        fila["prenda__tipo_prenda_id"]: fila["valor"]
        for fila in lineas.values("prenda__tipo_prenda_id").annotate(valor=Sum("valor_aplicado"))
    }
    prendas = (
        Prenda.objects.filter(orden__abono_alcanzado_en__range=(periodo.desde, periodo.hasta))
        .exclude(orden__estado=Orden.Estado.CANCELADA)
        .values("tipo_prenda_id", "tipo_prenda__nombre")
        .annotate(cantidad=Sum("cantidad"))
    )
    tipos_de_prenda = [
        {
            "id": fila["tipo_prenda_id"],
            "nombre": fila["tipo_prenda__nombre"],
            "cantidad": fila["cantidad"],
            "valor": dinero(valor_por_tipo.get(fila["tipo_prenda_id"], CERO)),
        }
        for fila in prendas
    ]
    return {
        "periodo": periodo.como_dict(),
        "servicios": _ordenados(servicios, limite),
        "tipos_de_prenda": _ordenados(tipos_de_prenda, limite),
        "sin_datos": not servicios and not tipos_de_prenda,
        "nota": NOTA_SERVICIOS,
    }


def clientes_frecuentes(periodo, limite):
    filas = (
        Orden.objects.exclude(estado=Orden.Estado.CANCELADA)
        .filter(creado_en__gte=periodo.inicio, creado_en__lt=periodo.fin)
        .values("cliente_id", "cliente__nombre_completo", "cliente__documento")
        .annotate(ordenes=Count("id"))
        .order_by("-ordenes", "cliente__nombre_completo", "cliente_id")[:limite]
    )
    clientes = [
        {
            "id": fila["cliente_id"],
            "nombre_completo": fila["cliente__nombre_completo"],
            "documento": fila["cliente__documento"],
            "ordenes": fila["ordenes"],
        }
        for fila in filas
    ]
    return {"periodo": periodo.como_dict(), "clientes": clientes, "sin_datos": not clientes}


ESTADOS_EN_ORDEN = (
    Orden.Estado.EN_ESPERA,
    Orden.Estado.RECIBIDA,
    Orden.Estado.CLASIFICADA,
    Orden.Estado.EN_PROCESO,
    Orden.Estado.CON_NOVEDAD,
    Orden.Estado.CONTROL_CALIDAD,
    Orden.Estado.LISTA,
    Orden.Estado.ENTREGADA,
    Orden.Estado.CANCELADA,
)


def ordenes_por_estado():
    cuenta = dict(Orden.objects.values_list("estado").annotate(total=Count("id")))
    estados = [
        {"estado": estado.value, "ordenes": cuenta.get(estado.value, 0)} for estado in ESTADOS_EN_ORDEN
    ]
    return {"estados": estados, "total": sum(fila["ordenes"] for fila in estados)}


def fidelizacion(periodo, hoy):
    clientes = dict(Cliente.objects.values_list("clasificacion").annotate(total=Count("id")))
    periodos_activos = ReglaInactividad.objects.filter(activa=True).values_list(
        "dias_sin_compra", flat=True
    )
    return {
        "periodo": periodo.como_dict(),
        "clientes_por_clasificacion": [
            {"clasificacion": clase.value, "clientes": clientes.get(clase.value, 0)}
            for clase in Cliente.Clasificacion
        ],
        "puntos_en_circulacion": Cliente.objects.aggregate(total=Sum("puntos"))["total"] or 0,
        "promociones_vigentes": Promocion.objects.filter(
            activa=True, vigente_desde__lte=hoy, vigente_hasta__gte=hoy
        ).count(),
        "puntos_por_inactividad": BeneficioInactividad.objects.filter(
            otorgado_en__gte=periodo.inicio, otorgado_en__lt=periodo.fin
        ).aggregate(total=Sum("puntos"))["total"]
        or 0,
        "clientes_inactivos": len(clientes_inactivos(min(periodos_activos), hoy))
        if periodos_activos
        else None,
    }
