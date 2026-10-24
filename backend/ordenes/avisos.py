import logging

from django.core.mail import send_mail
from django.db import DatabaseError, transaction

from .historial import registrar_evento
from .models import HistorialOrden

logger = logging.getLogger(__name__)


def pesos(valor):
    return f"${valor:,.0f}".replace(",", ".")


def mensaje_orden_lista(orden):
    cuerpo = (
        f"Hola {orden.cliente.nombre_completo}, tu orden {orden.codigo} esta lista para "
        "recoger en SmartWash."
    )
    saldo = orden.saldo_pendiente()
    if saldo > 0:
        cuerpo += f" Saldo pendiente por pagar al recogerla: {pesos(saldo)}."
    return f"Tu orden {orden.codigo} esta lista", cuerpo


def avisar_orden_lista(orden):
    """Corre despues del commit: si el correo falla, la orden sigue lista y queda constancia."""
    correo = orden.cliente.correo
    if not correo:
        resultado = "El cliente no tiene correo registrado; avisar por telefono."
    else:
        asunto, cuerpo = mensaje_orden_lista(orden)
        try:
            # ponytail: envio sincrono dentro de la peticion (hasta 10 s si Resend
            # tarda); pasar a una cola si el volumen de avisos lo exige.
            send_mail(asunto, cuerpo, None, [correo])
            resultado = f"Aviso de orden lista enviado a {correo}."
        except Exception:
            logger.exception("No se pudo enviar el aviso de orden lista de %s", orden.codigo)
            resultado = f"No se pudo enviar el aviso a {correo}; avisar por telefono."
    try:
        with transaction.atomic():
            registrar_evento(orden, HistorialOrden.TipoEvento.NOTIFICACION, None, resultado)
    except DatabaseError:
        logger.exception("No se registro el aviso de orden lista de %s", orden.codigo)
