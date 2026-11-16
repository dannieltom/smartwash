from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from ordenes.models import Orden

from .models import EtapaDeTrabajo

ESTADOS_CON_ETAPA = set(EtapaDeTrabajo.Estado.values)


# Una senal sobre Orden cubre todos los caminos que cambian su estado u operario (cambio de
# estado, novedad, decision, entrega, cancelacion, reasignacion) sin tocar cada vista.
@receiver(pre_save, sender=Orden)
def _guardar_estado_y_operario_previos(sender, instance, **kwargs):
    instance._previo_etapa = (
        Orden.objects.filter(pk=instance.pk).values("estado", "operario_id").first() if instance.pk else None
    )


@receiver(post_save, sender=Orden)
def _registrar_etapa_de_trabajo(sender, instance, created, **kwargs):
    previo = getattr(instance, "_previo_etapa", None) or {"estado": None, "operario_id": None}
    if (previo["estado"], previo["operario_id"]) == (instance.estado, instance.operario_id):
        return
    ahora = timezone.now()
    if previo["estado"] in ESTADOS_CON_ETAPA:
        # Sin etapa abierta (ordenes en proceso antes del despliegue) no hay nada que cerrar.
        EtapaDeTrabajo.objects.filter(orden=instance, fin__isnull=True).update(fin=ahora)
    if instance.estado in ESTADOS_CON_ETAPA and instance.operario_id:
        EtapaDeTrabajo.objects.create(
            orden=instance, operario_id=instance.operario_id, estado=instance.estado, inicio=ahora
        )
