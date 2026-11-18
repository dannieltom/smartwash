from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import generics
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from clientes.models import Cliente
from core.permissions import AdministradorORecepcionista, SoloAdministrador
from ordenes.serializers import pesos
from ordenes.views import ConsultaPorDocumentoThrottle, cliente_del_portal

from .models import Promocion, ReglaDescuento, ReglaInactividad, descuento_por_puntos
from .serializers import (
    BeneficioPublicoSerializer,
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
MENSAJE_SIN_INFORMACION = (
    "No hay información disponible con esos datos. Revisa tu cédula y el correo que registraste."
)
MENSAJE_SIN_BENEFICIOS = "Aún no tienes puntos ni beneficios disponibles para canjear."


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


@method_decorator(csrf_protect, name="dispatch")
class MisPuntosView(APIView):
    """Publica, con el mismo acceso y limite de intentos que la consulta de pedidos del portal."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle, ConsultaPorDocumentoThrottle]
    throttle_scope = "consulta-documento"

    def post(self, request):
        cliente = cliente_del_portal(request.data)
        if cliente is None:
            raise NotFound(MENSAJE_SIN_INFORMACION)
        beneficios = Promocion.objects.disponibles(cliente, timezone.localdate()).order_by(
            "vigente_hasta", "nombre"
        )
        datos = BeneficioPublicoSerializer(beneficios, many=True).data
        return Response(
            {
                "puntos": cliente.puntos,
                "valor_puntos": pesos(descuento_por_puntos(cliente.puntos)),
                "beneficios": datos,
                "mensaje": None if cliente.puntos or datos else MENSAJE_SIN_BENEFICIOS,
            }
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
