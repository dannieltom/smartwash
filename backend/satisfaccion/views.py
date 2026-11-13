from datetime import datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Avg
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle
from rest_framework.views import APIView

from core.permissions import AdministradorORecepcionista
from ordenes.models import Orden
from ordenes.views import MENSAJE_CODIGO_NO_ENCONTRADO

from .models import Calificacion
from .serializers import CalificacionSerializer, CalificarSerializer

MENSAJE_YA_CALIFICADA = "Esta orden ya fue calificada."


class CalificarPorCodigoThrottle(SimpleRateThrottle):
    """Por codigo y no solo por IP: frena a quien insiste sobre una misma orden."""

    scope = "calificar-orden-codigo"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": view.kwargs["codigo"].strip().upper()}


@method_decorator(csrf_protect, name="dispatch")
class CalificarOrdenView(APIView):
    """Publica: quien tiene el codigo de una orden entregada la califica una sola vez."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle, CalificarPorCodigoThrottle]
    throttle_scope = "calificar-orden"

    def post(self, request, codigo):
        orden = Orden.objects.filter(codigo=codigo).first()
        if orden is None:
            raise NotFound(MENSAJE_CODIGO_NO_ENCONTRADO)
        datos = CalificarSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        if orden.estado != Orden.Estado.ENTREGADA:
            raise serializers.ValidationError({"detail": "Solo puedes calificar una orden ya entregada."})
        if Calificacion.objects.filter(orden=orden).exists():
            raise serializers.ValidationError({"detail": MENSAJE_YA_CALIFICADA})
        try:
            # Dos envios simultaneos pasan la verificacion anterior; el OneToOne decide.
            with transaction.atomic():
                calificacion = datos.save(orden=orden)
        except IntegrityError:
            raise serializers.ValidationError({"detail": MENSAJE_YA_CALIFICADA})
        return Response(CalificarSerializer(calificacion).data, status=status.HTTP_201_CREATED)


def limite_de_fecha(request, campo, al_final_del_dia):
    """AAAA-MM-DD o fecha y hora ISO (sin zona = hora de Bogota). Un dia en `hasta` lo incluye completo."""
    texto = request.query_params.get(campo)
    if not texto:
        return None
    try:
        # Primero la fecha sola: parse_datetime tambien acepta "2026-11-13" y lo toma como las 00:00.
        dia = parse_date(texto)
        momento = (
            datetime.combine(dia + timedelta(days=1) if al_final_del_dia else dia, time.min)
            if dia
            else parse_datetime(texto)
        )
    except ValueError:
        momento = None
    if momento is None:
        raise serializers.ValidationError({campo: "Usa una fecha AAAA-MM-DD o una fecha y hora ISO."})
    return timezone.make_aware(momento) if timezone.is_naive(momento) else momento


class CalificacionesView(APIView):
    permission_classes = [AdministradorORecepcionista]

    def get(self, request):
        desde = limite_de_fecha(request, "desde", al_final_del_dia=False)
        hasta = limite_de_fecha(request, "hasta", al_final_del_dia=True)
        if desde and hasta and desde >= hasta:
            raise serializers.ValidationError({"hasta": "Debe ser posterior a desde."})

        calificaciones = Calificacion.objects.select_related("orden__cliente")
        if desde:
            calificaciones = calificaciones.filter(creada_en__gte=desde)
        if hasta:
            calificaciones = calificaciones.filter(creada_en__lt=hasta)
        promedio = calificaciones.aggregate(promedio=Avg("estrellas"))["promedio"]
        return Response(
            {
                "promedio": None if promedio is None else round(float(promedio), 1),
                "total": calificaciones.count(),
                "calificaciones": CalificacionSerializer(calificaciones, many=True).data,
            }
        )
