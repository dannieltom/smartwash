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


class PromocionQuerySet(models.QuerySet):
    def disponibles(self, cliente, fecha):
        return self.filter(
            activa=True,
            vigente_desde__lte=fecha,
            vigente_hasta__gte=fecha,
            segmentos__clasificacion=cliente.clasificacion,
        )

    def mayor_descuento(self, cliente, monto, fecha):
        return max(
            (promocion.descuento_sobre(monto) for promocion in self.disponibles(cliente, fecha)),
            default=Decimal("0"),
        )


class Promocion(ModeloConAutoria):
    Tipo = ReglaDescuento.Tipo

    nombre = models.CharField(max_length=120)
    descripcion = models.CharField(max_length=255, blank=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    activa = models.BooleanField(default=True)
    vigente_desde = models.DateField()
    vigente_hasta = models.DateField()

    objects = PromocionQuerySet.as_manager()

    class Meta:
        ordering = ("-vigente_desde", "nombre")
        verbose_name = "promoción"
        verbose_name_plural = "promociones"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valor__gte=0), name="promocion_valor_no_negativo"
            ),
            models.CheckConstraint(
                condition=~models.Q(tipo="porcentaje") | models.Q(valor__lte=100),
                name="promocion_porcentaje_no_supera_100",
            ),
            models.CheckConstraint(
                condition=models.Q(vigente_hasta__gte=models.F("vigente_desde")),
                name="promocion_vigencia_coherente",
            ),
        ]

    def __str__(self):
        return self.nombre

    @property
    def clasificaciones(self):
        return sorted(segmento.clasificacion for segmento in self.segmentos.all())

    def esta_disponible(self, fecha):
        return self.activa and self.vigente_desde <= fecha <= self.vigente_hasta

    def descuento_sobre(self, monto):
        if self.tipo == self.Tipo.PORCENTAJE:
            return (monto * self.valor / 100).quantize(Decimal("0.01"))
        return min(self.valor, monto)


class SegmentoPromocion(models.Model):
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE, related_name="segmentos")
    clasificacion = models.CharField(max_length=30, choices=Cliente.Clasificacion.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("promocion", "clasificacion"), name="segmento_promocion_unico"
            ),
        ]

    def __str__(self):
        return f"{self.promocion} · {self.clasificacion}"


class ReglaInactividad(ModeloConAutoria):
    """Cliente sin ordenes durante `dias_sin_compra` recibe `puntos` de bonificacion."""

    nombre = models.CharField(max_length=120)
    dias_sin_compra = models.PositiveIntegerField()
    puntos = models.PositiveIntegerField()
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ("dias_sin_compra", "nombre")
        verbose_name = "regla de inactividad"
        verbose_name_plural = "reglas de inactividad"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(dias_sin_compra__gte=1),
                name="regla_inactividad_dias_positivos",
            ),
            models.CheckConstraint(
                condition=models.Q(puntos__gte=1), name="regla_inactividad_puntos_positivos"
            ),
        ]

    def __str__(self):
        return self.nombre


class BeneficioInactividad(models.Model):
    """Puntos ya otorgados. `ultima_actividad` identifica el periodo de inactividad:
    mientras el cliente no vuelva a comprar, una regla no se paga dos veces."""

    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name="beneficios_inactividad"
    )
    regla = models.ForeignKey(
        ReglaInactividad, on_delete=models.PROTECT, related_name="beneficios"
    )
    puntos = models.PositiveIntegerField()
    ultima_actividad = models.DateField()
    otorgado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-otorgado_en", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("cliente", "regla", "ultima_actividad"),
                name="beneficio_inactividad_unico_por_periodo",
            ),
        ]

    def __str__(self):
        return f"{self.cliente} · {self.regla} · +{self.puntos}"
