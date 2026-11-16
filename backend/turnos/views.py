from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from core.permissions import SoloAdministrador, SoloOperario
from ordenes.serializers import nombre_usuario

from .models import EtapaDeTrabajo, Turno
from .services import inicio_del_dia, ordenes_activas, turno_vigente

DIAS_MAXIMOS_DEL_RANGO = 31


def estado_del_turno(operario, turno):
    return {
        "en_turno": turno is not None,
        "inicio": serializers.DateTimeField().to_representation(turno.inicio) if turno else None,
        "ordenes_en_curso": ordenes_activas(operario).count(),
    }


class IniciarTurnoView(APIView):
    permission_classes = [SoloOperario]
    exento_de_turno = True

    def post(self, request):
        with transaction.atomic():
            if turno_vigente(request.user) is not None:
                raise serializers.ValidationError({"detail": "Ya tienes un turno iniciado."})
            turno = Turno.objects.create(operario=request.user, inicio=timezone.now())
        return Response(estado_del_turno(request.user, turno), status=status.HTTP_201_CREATED)


class TerminarTurnoView(APIView):
    """Se puede terminar en cualquier momento: sus ordenes siguen asignadas."""

    permission_classes = [SoloOperario]
    exento_de_turno = True

    def post(self, request):
        turno = turno_vigente(request.user)
        if turno is None:
            raise serializers.ValidationError({"detail": "No tienes un turno iniciado."})
        turno.cerrar(timezone.now(), Turno.Cierre.MANUAL)
        return Response(estado_del_turno(request.user, None))


class TurnoActualView(APIView):
    permission_classes = [SoloOperario]
    exento_de_turno = True

    def get(self, request):
        return Response(estado_del_turno(request.user, turno_vigente(request.user)))


def rango_de_consulta(request):
    """desde/hasta en ISO (sin zona = hora de Bogota). Por defecto, hoy 00:00 hasta ahora."""
    ahora = timezone.now()
    limites = {}
    for campo, por_defecto in (("desde", inicio_del_dia(ahora)), ("hasta", ahora)):
        texto = request.query_params.get(campo)
        if not texto:
            limites[campo] = por_defecto
            continue
        valor = parse_datetime(texto)
        if valor is None:
            raise serializers.ValidationError({campo: "Usa una fecha y hora ISO, p. ej. 2026-11-13T16:00."})
        limites[campo] = timezone.make_aware(valor) if timezone.is_naive(valor) else valor
    desde, hasta = limites["desde"], limites["hasta"]
    if desde >= hasta:
        raise serializers.ValidationError({"hasta": "Debe ser posterior a desde."})
    if hasta - desde > timedelta(days=DIAS_MAXIMOS_DEL_RANGO):
        raise serializers.ValidationError({"hasta": f"El rango no puede pasar de {DIAS_MAXIMOS_DEL_RANGO} dias."})
    return desde, hasta


def que_se_solapa(queryset, desde, hasta):
    return queryset.filter(Q(fin__isnull=True) | Q(fin__gt=desde), inicio__lt=hasta)


class TurnoSerializer(serializers.ModelSerializer):
    operario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Turno
        fields = ("operario", "operario_nombre", "inicio", "fin", "cierre")
        read_only_fields = fields

    def get_operario_nombre(self, turno) -> str:
        return nombre_usuario(turno.operario)


class EtapaDeTrabajoSerializer(serializers.ModelSerializer):
    operario_nombre = serializers.SerializerMethodField()
    orden_codigo = serializers.CharField(source="orden.codigo", read_only=True)
    cliente_nombre = serializers.CharField(source="orden.cliente.nombre_completo", read_only=True)

    class Meta:
        model = EtapaDeTrabajo
        fields = ("operario", "operario_nombre", "orden", "orden_codigo", "cliente_nombre", "estado", "inicio", "fin")
        read_only_fields = fields

    def get_operario_nombre(self, etapa) -> str:
        return nombre_usuario(etapa.operario)


class TurnosView(APIView):
    permission_classes = [SoloAdministrador]
    exento_de_turno = True

    def get(self, request):
        desde, hasta = rango_de_consulta(request)
        turnos = que_se_solapa(Turno.objects.select_related("operario"), desde, hasta)
        return Response(TurnoSerializer(turnos, many=True).data)


class ActividadOperariosView(APIView):
    """Que orden trabajaba cada operario en un rango (p. ej. hoy de 4 a 6 de la tarde)."""

    permission_classes = [SoloAdministrador]

    def get(self, request):
        desde, hasta = rango_de_consulta(request)
        turnos = que_se_solapa(Turno.objects.select_related("operario"), desde, hasta)
        etapas = que_se_solapa(
            EtapaDeTrabajo.objects.select_related("operario", "orden__cliente"), desde, hasta
        )
        operario = request.query_params.get("operario")
        if operario:
            if not User.objects.filter(pk=operario if operario.isdigit() else None, rol=User.Rol.OPERARIO).exists():
                raise serializers.ValidationError({"operario": "Selecciona un operario."})
            turnos, etapas = turnos.filter(operario_id=operario), etapas.filter(operario_id=operario)
        return Response(
            {
                "turnos": TurnoSerializer(turnos, many=True).data,
                "etapas": EtapaDeTrabajoSerializer(etapas, many=True).data,
            }
        )
