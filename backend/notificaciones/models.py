from django.db import models


class Comunicacion(models.Model):
    """Inmutable: cada correo enviado a un cliente, para auditar las campanas.
    Solo se registra lo que efectivamente salio."""

    class Tipo(models.TextChoices):
        ORDEN_LISTA = "orden_lista", "Aviso de orden lista"
        RECORDATORIO = "recordatorio", "Recordatorio de orden no reclamada"
        PROMOCION = "promocion", "Promocion"

    cliente = models.ForeignKey(
        "clientes.Cliente", on_delete=models.PROTECT, related_name="comunicaciones"
    )
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    orden = models.ForeignKey(
        "ordenes.Orden",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="comunicaciones",
    )
    promocion = models.ForeignKey(
        "fidelizacion.Promocion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="comunicaciones_enviadas",
    )
    correo = models.EmailField(max_length=150)
    asunto = models.CharField(max_length=255)
    cuerpo = models.TextField()
    enviada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-enviada_en", "-id")
        verbose_name = "comunicación"
        verbose_name_plural = "comunicaciones"
        indexes = [models.Index(fields=("tipo", "enviada_en"))]

    def __str__(self):
        return f"{self.get_tipo_display()} → {self.cliente}"
