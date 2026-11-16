from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models

MENSAJE_TURNO_INMUTABLE = "Un turno no se modifica: solo se cierra una vez."


class TurnoQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied(MENSAJE_TURNO_INMUTABLE)

    def delete(self):
        raise PermissionDenied(MENSAJE_TURNO_INMUTABLE)


class Turno(models.Model):
    """Jornada de un operario. Se abre al iniciar turno y se cierra una sola vez."""

    class Cierre(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTOMATICO = "automatico", "Automatico"

    operario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="turnos")
    inicio = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True)
    cierre = models.CharField(max_length=20, choices=Cierre.choices, null=True, blank=True)

    objects = TurnoQuerySet.as_manager()

    class Meta:
        ordering = ("inicio", "id")
        indexes = [models.Index(fields=("operario", "inicio"))]
        constraints = [
            models.UniqueConstraint(
                fields=("operario",), condition=models.Q(fin__isnull=True), name="un_turno_abierto_por_operario"
            ),
            models.CheckConstraint(
                condition=models.Q(fin__isnull=True, cierre__isnull=True)
                | models.Q(fin__isnull=False, cierre__isnull=False),
                name="turno_cerrado_con_su_cierre",
            ),
        ]

    def __str__(self):
        return f"{self.operario} · {self.inicio:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            previo = Turno.objects.filter(pk=self.pk).values("operario_id", "inicio", "fin").first()
            if (
                previo is None
                or previo["fin"] is not None
                or (previo["operario_id"], previo["inicio"]) != (self.operario_id, self.inicio)
            ):
                raise PermissionDenied(MENSAJE_TURNO_INMUTABLE)
            kwargs["update_fields"] = ("fin", "cierre")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied(MENSAJE_TURNO_INMUTABLE)

    def cerrar(self, fin, cierre):
        self.fin, self.cierre = fin, cierre
        self.save()


class EtapaDeTrabajo(models.Model):
    """Tramo en que una orden estuvo en proceso o en control de calidad con un operario.

    La llenan las senales de turnos.signals; no se crea a mano.
    """

    class Estado(models.TextChoices):
        EN_PROCESO = "En proceso", "En proceso"
        CONTROL_CALIDAD = "Control de calidad", "Control de calidad"

    orden = models.ForeignKey("ordenes.Orden", on_delete=models.PROTECT, related_name="etapas_de_trabajo")
    operario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="etapas_de_trabajo"
    )
    estado = models.CharField(max_length=30, choices=Estado.choices)
    inicio = models.DateTimeField()
    fin = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("inicio", "id")
        indexes = [models.Index(fields=("operario", "inicio")), models.Index(fields=("inicio",))]
        constraints = [
            models.UniqueConstraint(
                fields=("orden",), condition=models.Q(fin__isnull=True), name="una_etapa_abierta_por_orden"
            ),
        ]

    def __str__(self):
        return f"{self.orden} · {self.estado} · {self.operario}"
