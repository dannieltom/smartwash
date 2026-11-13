"""Comprobantes digitales de la orden (HU22).

Cada comprobante guarda una copia congelada de la orden en el momento en que se genera:
consultarlo despues muestra lo mismo aunque cambien tarifas, descuentos o pagos.
"""

from django.utils import timezone

from .estimacion import calcular_fecha_estimada
from .models import Comprobante


def importe(valor):
    return f"{valor:.2f}"


def fecha_y_hora(momento):
    return timezone.localtime(momento).isoformat() if momento else None


def prendas_de(orden):
    return orden.prendas.select_related("tipo_prenda", "material", "dano").prefetch_related(
        "servicios__tarifa__servicio", "novedades"
    )


def linea_de(prenda):
    return {
        "tipo_prenda": prenda.tipo_prenda.nombre,
        "material": prenda.material.nombre if prenda.material_id else None,
        "cantidad": prenda.cantidad,
        "servicios": [
            {"servicio": linea.tarifa.servicio.nombre, "valor": importe(linea.valor_aplicado)}
            for linea in prenda.servicios.all()
        ],
        "valor": importe(sum((linea.valor_aplicado for linea in prenda.servicios.all()), 0)),
    }


def observaciones_de(prenda):
    notas = [novedad.descripcion for novedad in prenda.novedades.all()]
    dano = getattr(prenda, "dano", None)
    if dano is not None:
        notas.append(f"{dano.get_tipo_display()}: {dano.descripcion}")
    return notas


def pagos_de(orden):
    return [
        {"fecha": fecha_y_hora(pago.creado_en), "metodo": pago.get_metodo_display(), "monto": importe(pago.monto)}
        for pago in orden.pagos.all()
    ]


def contenido_de_abono(orden):
    fecha_estimada = calcular_fecha_estimada(orden)
    return {
        "codigo": orden.codigo,
        "cliente": orden.cliente.nombre_completo,
        "prendas": [linea_de(prenda) for prenda in prendas_de(orden)],
        "subtotal": importe(orden.subtotal),
        "descuento": importe(orden.descuento),
        "total_servicio": importe(orden.valor_total),
        "total_pagado": importe(orden.total_pagado()),
        "saldo_pendiente": importe(orden.saldo_pendiente()),
        "pagos": pagos_de(orden),
        "fecha_estimada_entrega": fecha_estimada.isoformat() if fecha_estimada else None,
    }


def contenido_de_entrega(orden):
    return {
        "codigo": orden.codigo,
        "cliente": orden.cliente.nombre_completo,
        "estado": orden.estado,
        "estado_pago": orden.estado_pago,
        "fecha_entrega": fecha_y_hora(orden.fecha_entrega),
        "total_servicio": importe(orden.valor_total),
        "total_pagado": importe(orden.total_pagado()),
        "pagos": pagos_de(orden),
        "prendas": [
            {**linea_de(prenda), "observaciones": observaciones_de(prenda)} for prenda in prendas_de(orden)
        ],
    }


CONTENIDO = {
    Comprobante.Tipo.ABONO: contenido_de_abono,
    Comprobante.Tipo.ENTREGA: contenido_de_entrega,
}


def generar_comprobante(orden, tipo):
    """Crea el comprobante de ese tipo si la orden no lo tiene; si ya lo tiene, lo devuelve.

    Debe llamarse dentro de la transaccion del cambio que lo dispara: si falla, no queda
    ni el comprobante ni el cambio.
    """
    existente = orden.comprobantes.filter(tipo=tipo).first()
    if existente:
        return existente
    comprobante = Comprobante(orden=orden, tipo=tipo, contenido=CONTENIDO[tipo](orden))
    comprobante.save()
    return comprobante
