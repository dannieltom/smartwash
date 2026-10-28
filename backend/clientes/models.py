from django.db import models

from core.models import ModeloConAutoria


class Cliente(ModeloConAutoria):
    class Clasificacion(models.TextChoices):
        OCASIONAL = "Ocasional", "Ocasional"
        FRECUENTE = "Frecuente", "Frecuente"
        VIP = "VIP", "VIP"

    nombre_completo = models.CharField(max_length=150)
    documento = models.CharField(max_length=20, unique=True)
    telefono = models.CharField(max_length=20)
    correo = models.EmailField(max_length=150, blank=True)
    clasificacion = models.CharField(
        max_length=30,
        choices=Clasificacion.choices,
        default=Clasificacion.OCASIONAL,
    )
    # db_default: las pruebas de migraciones de catalogo insertan clientes con el
    # esquema anterior, que no conoce esta columna.
    puntos = models.PositiveIntegerField(default=0, db_default=0)

    class Meta:
        ordering = ("nombre_completo",)

    def __str__(self):
        return f"{self.nombre_completo} ({self.documento})"
