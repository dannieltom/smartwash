from django.core.exceptions import PermissionDenied
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

MENSAJE_CALIFICACION_INMUTABLE = "Una calificacion no se puede modificar ni eliminar."


class CalificacionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied(MENSAJE_CALIFICACION_INMUTABLE)

    def delete(self):
        raise PermissionDenied(MENSAJE_CALIFICACION_INMUTABLE)


class Calificacion(models.Model):
    """Lo que opino el cliente de una orden entregada, desde el rastreo publico. Solo se crea."""

    orden = models.OneToOneField("ordenes.Orden", on_delete=models.PROTECT, related_name="calificacion")
    estrellas = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comentario = models.CharField(max_length=500, blank=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    objects = CalificacionQuerySet.as_manager()

    class Meta:
        verbose_name = "calificación"
        verbose_name_plural = "calificaciones"
        ordering = ("-creada_en", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estrellas__gte=1, estrellas__lte=5), name="calificacion_de_1_a_5_estrellas"
            ),
        ]

    def __str__(self):
        return f"{self.orden.codigo} · {self.estrellas} estrellas"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied(MENSAJE_CALIFICACION_INMUTABLE)
        kwargs["force_insert"] = True
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied(MENSAJE_CALIFICACION_INMUTABLE)
