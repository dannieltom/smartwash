from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from clientes.models import Cliente

from .models import Promocion, ReglaDescuento, SegmentoPromocion


class ReglaDescuentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReglaDescuento
        fields = (
            "id",
            "nombre",
            "tipo",
            "valor",
            "clasificacion_cliente",
            "activa",
            "vigente_desde",
            "vigente_hasta",
        )

    def validate(self, attrs):
        tipo = attrs.get("tipo", getattr(self.instance, "tipo", None))
        valor = attrs.get("valor", getattr(self.instance, "valor", None))
        if valor is not None and valor < 0:
            raise serializers.ValidationError({"valor": "El valor del descuento no puede ser negativo."})
        if tipo == ReglaDescuento.Tipo.PORCENTAJE and valor is not None and valor > 100:
            raise serializers.ValidationError(
                {"valor": "Un descuento porcentual no puede superar el 100% del valor de la orden."}
            )

        desde = attrs.get("vigente_desde", getattr(self.instance, "vigente_desde", None))
        hasta = attrs.get("vigente_hasta", getattr(self.instance, "vigente_hasta", None))
        if desde and hasta and hasta <= desde:
            raise serializers.ValidationError(
                {"vigente_hasta": "La vigencia debe terminar despues de la fecha de inicio."}
            )
        return attrs

    def create(self, validated_data):
        instancia = ReglaDescuento(**validated_data)
        instancia.registrar_autoria(self.context["request"].user)
        instancia.save()
        return instancia

    def update(self, instance, validated_data):
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        instance.registrar_autoria(self.context["request"].user)
        instance.save()
        return instance


class PromocionSerializer(serializers.ModelSerializer):
    segmentos = serializers.ListField(
        source="clasificaciones",
        child=serializers.ChoiceField(choices=Cliente.Clasificacion.choices),
        allow_empty=False,
        error_messages={"empty": "Asigna la promocion al menos a un segmento de clientes."},
    )
    disponible = serializers.SerializerMethodField()

    class Meta:
        model = Promocion
        fields = (
            "id",
            "nombre",
            "descripcion",
            "tipo",
            "valor",
            "segmentos",
            "activa",
            "vigente_desde",
            "vigente_hasta",
            "disponible",
        )
        extra_kwargs = {
            campo: {"error_messages": {"required": "La vigencia debe tener fecha de inicio y de fin."}}
            for campo in ("vigente_desde", "vigente_hasta")
        }

    def get_disponible(self, promocion):
        return promocion.esta_disponible(timezone.localdate())

    def validate_segmentos(self, segmentos):
        return list(dict.fromkeys(segmentos))

    def validate(self, attrs):
        tipo = attrs.get("tipo", getattr(self.instance, "tipo", None))
        valor = attrs.get("valor", getattr(self.instance, "valor", None))
        if valor is not None and valor < 0:
            raise serializers.ValidationError({"valor": "El valor del descuento no puede ser negativo."})
        if tipo == Promocion.Tipo.PORCENTAJE and valor is not None and valor > 100:
            raise serializers.ValidationError(
                {"valor": "Un descuento porcentual no puede superar el 100% del valor de la orden."}
            )

        desde = attrs.get("vigente_desde", getattr(self.instance, "vigente_desde", None))
        hasta = attrs.get("vigente_hasta", getattr(self.instance, "vigente_hasta", None))
        if desde and hasta and hasta < desde:
            raise serializers.ValidationError(
                {"vigente_hasta": "La vigencia no puede terminar antes de la fecha de inicio."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        segmentos = validated_data.pop("clasificaciones")
        promocion = Promocion(**validated_data)
        promocion.registrar_autoria(self.context["request"].user)
        promocion.save()
        self._guardar_segmentos(promocion, segmentos)
        return promocion

    @transaction.atomic
    def update(self, instance, validated_data):
        segmentos = validated_data.pop("clasificaciones", None)
        for campo, valor in validated_data.items():
            setattr(instance, campo, valor)
        instance.registrar_autoria(self.context["request"].user)
        instance.save()
        if segmentos is not None:
            instance.segmentos.exclude(clasificacion__in=segmentos).delete()
            self._guardar_segmentos(instance, segmentos)
        return instance

    def _guardar_segmentos(self, promocion, segmentos):
        for clasificacion in segmentos:
            SegmentoPromocion.objects.get_or_create(
                promocion=promocion, clasificacion=clasificacion
            )
        promocion.refresh_from_db()
