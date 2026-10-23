from datetime import timedelta
from decimal import ROUND_CEILING, Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.db.models import Count, Sum
from django.utils import timezone
from django.utils.crypto import get_random_string

from catalogo.models import Material, Tarifa, TipoPrenda
from clientes.models import Cliente
from core.models import ModeloConAutoria
from fidelizacion.models import ReglaDescuento

PORCENTAJE_ABONO = Decimal("30")
# Sin 0/O ni 1/I: el codigo se dicta por telefono y se copia a mano.
ALFABETO_CODIGO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def duracion_estimada_dias(servicios_distintos):
    base = getattr(settings, "ORDEN_DURACION_BASE_DIAS", Decimal("1"))
    adicional = getattr(settings, "ORDEN_DURACION_POR_SERVICIO_ADICIONAL", Decimal("0.5"))
    if servicios_distintos == 0:
        return 0
    return int((base + adicional * (servicios_distintos - 1)).to_integral_value(ROUND_CEILING))


def sumar_dias_habiles(desde, dias):
    # Lunes (0) a sabado (5); los festivos no se descuentan.
    laborales = getattr(settings, "ORDEN_DIAS_LABORALES", {0, 1, 2, 3, 4, 5})
    fecha = desde
    while dias > 0:
        fecha += timedelta(days=1)
        if fecha.weekday() in laborales:
            dias -= 1
    return fecha


class Orden(ModeloConAutoria):
    class Estado(models.TextChoices):
        RECIBIDA = "Recibida", "Recibida"
        CLASIFICADA = "Clasificada", "Clasificada"
        EN_PROCESO = "En proceso", "En proceso"
        CONTROL_CALIDAD = "Control de calidad", "Control de calidad"
        LISTA = "Lista para entrega", "Lista para entrega"
        ENTREGADA = "Entregada", "Entregada"
        CANCELADA = "Cancelada", "Cancelada"
        EN_ESPERA = "En espera", "En espera"
        CON_NOVEDAD = "Con novedad", "Con novedad"

    # Entregada no figura: solo se llega por /entrega, que verifica las prendas.
    TRANSICIONES = {
        Estado.RECIBIDA: (Estado.CLASIFICADA,),
        Estado.CLASIFICADA: (Estado.EN_PROCESO,),
        Estado.EN_PROCESO: (Estado.CONTROL_CALIDAD,),
        Estado.CONTROL_CALIDAD: (Estado.LISTA, Estado.EN_PROCESO),
    }
    ESTADOS_CANCELABLES = (Estado.EN_ESPERA, Estado.RECIBIDA, Estado.CLASIFICADA)

    class EstadoPago(models.TextChoices):
        PENDIENTE = "Pendiente", "Pendiente"
        PARCIAL = "Parcial", "Parcial"
        PAGADA = "Pagada", "Pagada"

    # El modelo acordado expone id_orden como codigo de rastreo. Un serial es
    # enumerable: cualquiera prueba 1, 2, 3 y ve las ordenes de otros.
    codigo = models.CharField(max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(
        Cliente, on_delete=models.PROTECT, related_name="ordenes"
    )
    recepcionista = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ordenes_recibidas",
    )
    # Nullable porque asignar operario es un paso posterior (HU10) y HU23 exige
    # un abono antes de hacerlo.
    operario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ordenes_asignadas",
    )
    estado = models.CharField(
        max_length=30, choices=Estado.choices, default=Estado.EN_ESPERA
    )
    estado_pago = models.CharField(
        max_length=20, choices=EstadoPago.choices, default=EstadoPago.PENDIENTE
    )
    fecha_estimada_entrega = models.DateField(null=True, blank=True)
    fecha_entrega = models.DateTimeField(null=True, blank=True)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    abono_requerido = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duracion_estimada_dias = models.PositiveSmallIntegerField(default=0)
    # Dia en que la orden alcanzo el abono minimo y paso a "Recibida". Se
    # conserva aunque el total suba despues: el abono se exige una sola vez.
    abono_alcanzado_en = models.DateField(null=True, blank=True)
    motivo_cancelacion = models.CharField(max_length=255, blank=True)
    numero_reprocesos = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "orden"
        verbose_name_plural = "ordenes"
        ordering = ("-creado_en",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valor_total__gte=0),
                name="orden_valor_total_no_negativo",
            )
        ]

    def __str__(self):
        return f"{self.codigo} - {self.cliente}"

    def save(self, *args, **kwargs):
        if not self.codigo:
            # ponytail: sin reintento; con 32^8 combinaciones un choque es
            # improbable y el unique de la base lo detiene si ocurre.
            self.codigo = f"SW-{get_random_string(8, ALFABETO_CODIGO)}"
        # Se deriva de los pagos en cada guardado: nadie lo fija a mano.
        self.estado_pago = self.calcular_estado_pago()
        # Ultima barrera: ningun camino (API, admin, shell) guarda una orden
        # que rompa las reglas de pago.
        self.validar_reglas_de_pago()
        super().save(*args, **kwargs)

    def clean(self):
        self.validar_reglas_de_pago()

    def validar_reglas_de_pago(self):
        if self.operario_id is not None:
            self.exigir_abono()
        # Sin excepcion de rol: ni el administrador entrega sin cobrar.
        if self.estado == self.Estado.ENTREGADA:
            self.exigir_pago_completo()

    def exigir_pago_completo(self):
        if self.pago_completo():
            return
        raise ValidationError(
            {
                "estado": "No se puede entregar la orden mientras el pago no este completo "
                f"(saldo pendiente ${self.saldo_pendiente()})."
            }
        )

    def exigir_abono(self):
        if self.tiene_abono():
            return
        falta = max(self.abono_requerido - self.total_pagado(), Decimal("0"))
        raise ValidationError(
            {
                "operario": f"La orden requiere un abono minimo de ${self.abono_requerido} "
                f"antes de asignarse a un operario (faltan ${falta})."
            }
        )

    def exigir_no_cancelada(self):
        if self.estado == self.Estado.CANCELADA:
            raise ValidationError(
                {"estado": "La orden esta cancelada; la cancelacion es definitiva."}
            )

    def cancelar(self, motivo):
        self.exigir_no_cancelada()
        if self.estado not in self.ESTADOS_CANCELABLES:
            raise ValidationError(
                {
                    "estado": f'La orden esta "{self.estado}": el servicio ya inicio '
                    "y no se puede cancelar."
                }
            )
        self.estado = self.Estado.CANCELADA
        self.motivo_cancelacion = motivo
        self.operario = None

    def cambiar_estado(self, nuevo):
        self.exigir_no_cancelada()
        if self.estado == self.Estado.CON_NOVEDAD:
            raise ValidationError(
                {
                    "estado": "La orden tiene una novedad pendiente: no avanza hasta que "
                    "se registre la decision del cliente."
                }
            )
        if self.estado == self.Estado.EN_ESPERA:
            falta = max(self.abono_requerido - self.total_pagado(), Decimal("0"))
            raise ValidationError(
                {
                    "estado": "La orden esta en espera: requiere un abono minimo de "
                    f"${self.abono_requerido} (faltan ${falta})."
                }
            )
        if nuevo not in self.TRANSICIONES.get(self.estado, ()):
            raise ValidationError(
                {"estado": f'No se puede pasar de "{self.estado}" a "{nuevo}".'}
            )
        if nuevo == self.Estado.EN_PROCESO and self.operario_id is None:
            raise ValidationError(
                {"operario": "La orden necesita un operario asignado para pasar a En proceso."}
            )
        # Un reproceso no cuesta: solo se cuenta.
        if self.estado == self.Estado.CONTROL_CALIDAD and nuevo == self.Estado.EN_PROCESO:
            self.numero_reprocesos += 1
        self.estado = nuevo

    def total_pagado(self):
        if self.pk is None:
            return Decimal("0")
        return self.pagos.aggregate(total=Sum("monto"))["total"] or Decimal("0")

    def saldo_pendiente(self):
        return max(self.valor_total - self.total_pagado(), Decimal("0"))

    def pago_completo(self):
        return self.total_pagado() >= self.valor_total

    def tiene_abono(self):
        return self.abono_alcanzado_en is not None

    def calcular_estado_pago(self):
        pagado = self.total_pagado()
        if pagado == 0:
            return self.EstadoPago.PENDIENTE
        if pagado >= self.valor_total:
            return self.EstadoPago.PAGADA
        return self.EstadoPago.PARCIAL

    def registrar_abono_minimo(self, fecha):
        """La orden en espera pasa a "Recibida" y desde ese dia corre la fecha estimada."""
        self.abono_alcanzado_en = fecha
        if self.estado == self.Estado.EN_ESPERA:
            self.estado = self.Estado.RECIBIDA
        self.fecha_estimada_entrega = sumar_dias_habiles(fecha, self.duracion_estimada_dias)

    def recalcular(self):
        """Valor, abono y duracion a partir de las lineas. No guarda."""
        lineas = OrdenServicio.objects.filter(prenda__orden=self)
        self.subtotal = lineas.aggregate(total=Sum("valor_aplicado"))["total"] or Decimal("0")
        self.descuento = ReglaDescuento.objects.mayor_descuento(
            self.cliente, self.subtotal, timezone.localdate()
        )
        self.valor_total = self.subtotal - self.descuento
        if not self.tiene_abono():
            self.abono_requerido = (self.valor_total * PORCENTAJE_ABONO / 100).to_integral_value(
                ROUND_CEILING
            )
        self.duracion_estimada_dias = duracion_estimada_dias(
            lineas.values("tarifa__servicio").distinct().count()
        )
        if self.tiene_abono():
            self.fecha_estimada_entrega = sumar_dias_habiles(
                self.abono_alcanzado_en, self.duracion_estimada_dias
            )


RANGO_CLASIFICACION = (
    Cliente.Clasificacion.OCASIONAL,
    Cliente.Clasificacion.FRECUENTE,
    Cliente.Clasificacion.VIP,
)


def clasificacion_por_consumo(cliente):
    """Clasifica por las ordenes cerradas del cliente; nunca baja de la que ya tiene.

    Una orden solo llega a "Entregada" con el pago completo (HU24), asi que
    entregada equivale a cerrada. valor_total es lo cobrado, con el descuento.
    """
    consumo = cliente.ordenes.filter(estado=Orden.Estado.ENTREGADA).aggregate(
        ordenes=Count("id"), total=Sum("valor_total")
    )
    ordenes, total = consumo["ordenes"], consumo["total"] or Decimal("0")
    if ordenes >= getattr(settings, "CLIENTE_VIP_MIN_ORDENES", 10) or total >= getattr(
        settings, "CLIENTE_VIP_MIN_CONSUMO", Decimal("500000")
    ):
        calculada = Cliente.Clasificacion.VIP
    elif ordenes >= getattr(settings, "CLIENTE_FRECUENTE_MIN_ORDENES", 3):
        calculada = Cliente.Clasificacion.FRECUENTE
    else:
        calculada = Cliente.Clasificacion.OCASIONAL
    return max(cliente.clasificacion, calculada, key=RANGO_CLASIFICACION.index)


class Prenda(ModeloConAutoria):
    orden = models.ForeignKey(Orden, on_delete=models.CASCADE, related_name="prendas")
    tipo_prenda = models.ForeignKey(
        TipoPrenda, on_delete=models.PROTECT, related_name="prendas"
    )
    # Nulo en la base solo por las prendas guardadas antes de existir el
    # material; la API lo exige en toda prenda nueva.
    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, null=True, blank=True, related_name="prendas"
    )
    cantidad = models.PositiveIntegerField(default=1)
    peso = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Kilos de UNA prenda. La API lo exige; es nulo solo en prendas anteriores.",
    )
    talla = models.CharField(max_length=20, blank=True)
    genero = models.CharField(max_length=20, blank=True)
    color = models.CharField(max_length=40, blank=True)
    estado_inicial = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("id",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(cantidad__gt=0), name="prenda_cantidad_positiva"
            ),
            models.CheckConstraint(
                condition=models.Q(peso__isnull=True) | models.Q(peso__gt=0),
                name="prenda_peso_positivo",
            ),
        ]

    def __str__(self):
        nombre = f"{self.tipo_prenda} · {self.material}" if self.material_id else str(self.tipo_prenda)
        return f"{self.cantidad} x {nombre}"


class OrdenServicio(ModeloConAutoria):
    prenda = models.ForeignKey(
        Prenda, on_delete=models.CASCADE, related_name="servicios"
    )
    tarifa = models.ForeignKey(
        Tarifa, on_delete=models.PROTECT, related_name="ordenes_servicio"
    )
    # Lo cobrado por esta linea (precio de una prenda x cantidad), congelado al
    # registrarla: si la tarifa o el factor cambian despues, la orden conserva
    # su valor. El desglose permite auditar el calculo; es nulo en las lineas
    # anteriores a que existiera.
    valor_aplicado = models.DecimalField(max_digits=10, decimal_places=2)
    valor_base = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    precio_por_kilo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    peso = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    nivel_dificultad = models.CharField(max_length=80, blank=True)
    factor = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    es_excepcion = models.BooleanField(null=True, blank=True)

    class Meta:
        verbose_name = "servicio de la prenda"
        verbose_name_plural = "servicios de la prenda"
        ordering = ("id",)
        constraints = [
            models.UniqueConstraint(
                fields=("prenda", "tarifa"), name="orden_servicio_unico_por_prenda"
            ),
            models.CheckConstraint(
                condition=models.Q(valor_aplicado__gte=0),
                name="orden_servicio_valor_no_negativo",
            ),
        ]

    def __str__(self):
        return f"{self.prenda} - {self.tarifa.servicio}"


MENSAJE_HISTORIAL_INMUTABLE = "El historial de una orden no se puede modificar ni eliminar."


class HistorialOrdenQuerySet(models.QuerySet):
    # update() y delete() masivos no pasan por save()/delete() del modelo.
    def update(self, **kwargs):
        raise PermissionDenied(MENSAJE_HISTORIAL_INMUTABLE)

    def delete(self):
        raise PermissionDenied(MENSAJE_HISTORIAL_INMUTABLE)


class HistorialOrden(models.Model):
    """Registro inmutable de lo que le ocurre a una orden.

    No se crea a mano: se usa ordenes.historial.registrar_evento, dentro de la
    misma transaccion que el cambio que se registra.
    """

    class TipoEvento(models.TextChoices):
        CREACION = "creacion", "Creación"
        PAGO = "pago", "Pago"
        ASIGNACION = "asignacion", "Asignación"
        REASIGNACION = "reasignacion", "Reasignación"
        CAMBIO_ESTADO = "cambio_estado", "Cambio de estado"
        PRENDA_AGREGADA = "prenda_agregada", "Prenda agregada"
        SERVICIO_AGREGADO = "servicio_agregado", "Servicio agregado"
        ENTREGA = "entrega", "Entrega"
        NOVEDAD = "novedad", "Novedad"
        DECISION_NOVEDAD = "decision_novedad", "Decisión sobre la novedad"
        NOTIFICACION = "notificacion", "Notificación al cliente"
        CANCELACION = "cancelacion", "Cancelación"
        DEVOLUCION = "devolucion", "Devolución"

    # PROTECT en ambos: borrar la orden o el usuario dejaria el historial
    # incompleto o sin autor.
    orden = models.ForeignKey(
        Orden, on_delete=models.PROTECT, related_name="historial", editable=False
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="eventos_de_orden",
        editable=False,
    )
    tipo_evento = models.CharField(
        max_length=30, choices=TipoEvento.choices, editable=False
    )
    detalle = models.TextField(blank=True, editable=False)
    fecha = models.DateTimeField(auto_now_add=True)

    objects = HistorialOrdenQuerySet.as_manager()

    class Meta:
        verbose_name = "evento de la orden"
        verbose_name_plural = "historial de ordenes"
        ordering = ("fecha", "id")

    def __str__(self):
        return f"{self.orden.codigo} · {self.get_tipo_evento_display()} · {self.fecha:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionDenied(MENSAJE_HISTORIAL_INMUTABLE)
        # Una instancia nueva con el pk de un registro existente haria UPDATE.
        kwargs["force_insert"] = True
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied(MENSAJE_HISTORIAL_INMUTABLE)


class NovedadQuerySet(models.QuerySet):
    def pendientes(self):
        # "No continuar" deja la orden retenida: la novedad sigue abierta hasta otra decision o la cancelacion.
        return self.filter(
            models.Q(decision__isnull=True) | models.Q(decision="no_continuar"),
            orden__estado=Orden.Estado.CON_NOVEDAD,
        )


class Novedad(ModeloConAutoria):
    class Origen(models.TextChoices):
        PROCESO = "proceso", "Durante el proceso"
        ENTREGA = "entrega", "Detectada en la entrega"

    class Decision(models.TextChoices):
        CONTINUAR = "continuar", "Continuar igual"
        REPROCESAR = "reprocesar", "Reprocesar"
        NO_CONTINUAR = "no_continuar", "No continuar"

    orden = models.ForeignKey(Orden, on_delete=models.PROTECT, related_name="novedades")
    prenda = models.ForeignKey(Prenda, on_delete=models.PROTECT, related_name="novedades")
    descripcion = models.TextField()
    origen = models.CharField(max_length=20, choices=Origen.choices)
    # A donde vuelve la orden si el cliente decide continuar igual (HU19).
    estado_anterior = models.CharField(max_length=30, choices=Orden.Estado.choices)
    decision = models.CharField(max_length=20, choices=Decision.choices, null=True, blank=True)
    decision_observacion = models.TextField(blank=True)
    decidida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="decisiones_de_novedad",
    )
    decidida_en = models.DateTimeField(null=True, blank=True)

    objects = NovedadQuerySet.as_manager()

    class Meta:
        verbose_name_plural = "novedades"
        ordering = ("creado_en", "id")

    def __str__(self):
        return f"{self.orden.codigo} · {self.prenda} · {self.get_origen_display()}"


class FotoNovedad(ModeloConAutoria):
    # ponytail: base64 en la base por decision del PO (max. 500 KB); pasar a
    # almacenamiento de objetos cambia solo este modelo y la vista de la foto.
    novedad = models.OneToOneField(Novedad, on_delete=models.CASCADE, related_name="foto")
    contenido = models.TextField()
    tipo = models.CharField(max_length=20)
    tamano = models.PositiveIntegerField(help_text="Bytes de la imagen decodificada.")

    class Meta:
        verbose_name = "foto de la novedad"
        verbose_name_plural = "fotos de novedades"

    def __str__(self):
        return f"Foto de {self.novedad}"
