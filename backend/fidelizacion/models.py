from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from clientes.models import Cliente
from core.models import ModeloConAutoria


def puntos_por_consumo(valor):
    # La fraccion no suma: $15.900 dan 15 puntos.
    return int(valor // getattr(settings, "PUNTOS_CADA_PESOS", Decimal("1000")))


class ReglaDescuentoQuerySet(models.QuerySet):
    def aplicables(self, cliente, fecha):
        # A diferencia de las tarifas, vigente_hasta es inclusivo: una promocion
        # "hasta el 31" vale el 31.
        return self.filter(
            Q(vigente_hasta__isnull=True) | Q(vigente_hasta__gte=fecha),
            Q(clasificacion_cliente="") | Q(clasificacion_cliente=cliente.clasificacion),
            activa=True,
            vigente_desde__lte=fecha,
        )

    def mayor_descuento(self, cliente, monto, fecha):
        """Las reglas no se acumulan: se aplica solo la que mas descuenta."""
        return max(
            (regla.descuento_sobre(monto) for regla in self.aplicables(cliente, fecha)),
            default=Decimal("0"),
        )


class ReglaDescuento(ModeloConAutoria):

    class Tipo(models.TextChoices):
        PORCENTAJE = "porcentaje", "Porcentaje"
        MONTO_FIJO = "monto_fijo", "Monto fijo"

    nombre = models.CharField(max_length=120)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    clasificacion_cliente = models.CharField(
        max_length=30,
        choices=Cliente.Clasificacion.choices,
        blank=True,
        help_text="Vacio = aplica a cualquier clasificacion de cliente.",
    )
    activa = models.BooleanField(default=True)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField(null=True, blank=True)

    objects = ReglaDescuentoQuerySet.as_manager()

    class Meta:
        ordering = ("-vigente_desde", "nombre")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valor__gte=0), name="regla_descuento_valor_no_negativo"
            ),
            models.CheckConstraint(
                # Un monto fijo no tiene tope: es una suma en pesos, no un
                # porcentaje. Literal "porcentaje", no Tipo.PORCENTAJE: el
                # cuerpo de Meta no ve los nombres de la clase que lo contiene.
                condition=~models.Q(tipo="porcentaje") | models.Q(valor__lte=100),
                name="regla_descuento_porcentaje_no_supera_100",
            ),
            models.CheckConstraint(
                condition=models.Q(vigente_hasta__isnull=True)
                | models.Q(vigente_hasta__gt=models.F("vigente_desde")),
                name="regla_descuento_vigencia_coherente",
            ),
        ]

    def __str__(self):
        return self.nombre

    def descuento_sobre(self, monto):
        if self.tipo == self.Tipo.PORCENTAJE:
            return (monto * self.valor / 100).quantize(Decimal("0.01"))
        return min(self.valor, monto)
