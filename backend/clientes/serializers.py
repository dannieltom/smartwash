from rest_framework import serializers

from catalogo.serializers import ConAutoriaSerializer

from .models import Cliente


class ClienteSerializer(ConAutoriaSerializer):
    class Meta:
        model = Cliente
        fields = (
            "id",
            "nombre_completo",
            "documento",
            "telefono",
            "correo",
            "clasificacion",
            "puntos",
        )
        # La clasificacion la recalcula RF38 y los puntos los suma la entrega de
        # la orden (HU26); quien registra o edita al cliente no fija ninguno.
        read_only_fields = ("clasificacion", "puntos")
        # Se desactiva el UniqueValidator de DRF: validate_documento compara sin
        # distinguir mayusculas ni espacios. El unique del modelo queda de respaldo.
        extra_kwargs = {"documento": {"validators": []}}

    def validate_documento(self, documento):
        documento = "".join(documento.split())
        repetidos = Cliente.objects.filter(documento__iexact=documento)
        if self.instance is not None:
            repetidos = repetidos.exclude(pk=self.instance.pk)
        if repetidos.exists():
            raise serializers.ValidationError(
                f'Ya existe un cliente con el documento "{documento}".'
            )
        return documento

    def validate_nombre_completo(self, nombre):
        return " ".join(nombre.split())
