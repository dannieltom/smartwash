from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from clientes.models import Cliente
from core.permissions import AdministradorORecepcionista, SoloAdministrador

from .models import Promocion, ReglaDescuento, ReglaInactividad
from .serializers import (
    ClienteInactivoSerializer,
    PromocionSerializer,
    ReglaDescuentoSerializer,
    ReglaInactividadSerializer,
)
from .comunicaciones import ProcesoComunicacionesFallido, enviar_comunicaciones
from .services import (
    ProcesoInactividadFallido,
    SinReglasDeInactividad,
    asignar_beneficios_por_inactividad,
    clientes_inactivos,
)

MENSAJE_SIN_REGLAS = "Configura al menos una regla de inactividad activa."
MENSAJE_PROCESO_FALLIDO = "No se pudo completar el proceso. No se aplico ningun cambio."


class ReglaDescuentoListCreateView(generics.ListCreateAPIView):
    queryset = ReglaDescuento.objects.all()
    serializer_class = ReglaDescuentoSerializer


class ReglaDescuentoDetailView(generics.RetrieveUpdateAPIView):
    queryset = ReglaDescuento.objects.all()
    serializer_class = ReglaDescuentoSerializer


class PromocionListCreateView(generics.ListCreateAPIView):
    permission_classes = [SoloAdministrador]
    queryset = Promocion.objects.prefetch_related("segmentos")
    serializer_class = PromocionSerializer


class PromocionDetailView(generics.RetrieveUpdateAPIView):
    """Sin destroy: una promocion se desactiva, no se borra."""

    permission_classes = [SoloAdministrador]
    queryset = Promocion.objects.prefetch_related("segmentos")
    serializer_class = PromocionSerializer


class PromocionesDisponiblesView(APIView):
    """Promociones que hoy le aplican a un cliente por su clasificacion."""

    permission_classes = [AdministradorORecepcionista]

    def get(self, request):
        cliente_id = request.query_params.get("cliente")
        if not cliente_id or not cliente_id.isdigit():
            raise ValidationError({"cliente": "Indica el cliente con el parametro cliente."})
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        promociones = (
            Promocion.objects.disponibles(cliente, timezone.localdate())
            .prefetch_related("segmentos")
            .order_by("vigente_hasta", "nombre")
        )
        return Response(
            PromocionSerializer(promociones, many=True, context={"request": request}).data
        )


class ReglaInactividadListCreateView(generics.ListCreateAPIView):
    permission_classes = [SoloAdministrador]
    queryset = ReglaInactividad.objects.all()
    serializer_class = ReglaInactividadSerializer


class ReglaInactividadDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [SoloAdministrador]
    queryset = ReglaInactividad.objects.all()
    serializer_class = ReglaInactividadSerializer


class ClientesInactivosView(APIView):
    """Inactivos segun el periodo mas corto entre las reglas activas."""

    permission_classes = [SoloAdministrador]

    def get(self, request):
        periodos = ReglaInactividad.objects.filter(activa=True).values_list(
            "dias_sin_compra", flat=True
        )
        if not periodos:
            return Response({"detail": MENSAJE_SIN_REGLAS}, status=status.HTTP_409_CONFLICT)
        inactivos = clientes_inactivos(min(periodos))
        datos = [
            {"cliente": cliente, "ultima_actividad": ultima, "dias_inactivo": dias}
            for cliente, ultima, dias in inactivos
        ]
        return Response(ClienteInactivoSerializer(datos, many=True).data)


class AsignarBeneficiosInactividadView(APIView):
    permission_classes = [SoloAdministrador]

    def post(self, request):
        try:
            resultado = asignar_beneficios_por_inactividad()
        except SinReglasDeInactividad:
            return Response({"detail": MENSAJE_SIN_REGLAS}, status=status.HTTP_409_CONFLICT)
        except ProcesoInactividadFallido:
            return Response(
                {"detail": MENSAJE_PROCESO_FALLIDO}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response(resultado)


class EnviarComunicacionesView(APIView):
    permission_classes = [SoloAdministrador]

    def post(self, request):
        try:
            return Response(enviar_comunicaciones())
        except ProcesoComunicacionesFallido:
            return Response(
                {"detail": MENSAJE_PROCESO_FALLIDO}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
