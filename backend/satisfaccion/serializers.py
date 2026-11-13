from rest_framework import serializers

from .models import Calificacion


class CalificarSerializer(serializers.ModelSerializer):
    estrellas = serializers.IntegerField(
        min_value=1,
        max_value=5,
        error_messages={
            "required": "Elige de 1 a 5 estrellas.",
            "min_value": "Elige de 1 a 5 estrellas.",
            "max_value": "Elige de 1 a 5 estrellas.",
            "invalid": "Elige de 1 a 5 estrellas.",
        },
    )
    comentario = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        error_messages={"max_length": "El comentario no puede pasar de 500 caracteres."},
    )

    class Meta:
        model = Calificacion
        fields = ("estrellas", "comentario")


class CalificacionSerializer(serializers.ModelSerializer):
    orden_id = serializers.IntegerField(source="orden.id", read_only=True)
    orden_codigo = serializers.CharField(source="orden.codigo", read_only=True)
    cliente_nombre = serializers.CharField(source="orden.cliente.nombre_completo", read_only=True)

    class Meta:
        model = Calificacion
        fields = ("orden_id", "orden_codigo", "cliente_nombre", "estrellas", "comentario", "creada_en")
        read_only_fields = fields
