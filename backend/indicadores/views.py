from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from core.listas import entero
from core.permissions import AdministradorORecepcionista, SoloAdministrador

from . import services
from .periodos import periodo_de

LIMITE_POR_DEFECTO = 10
LIMITE_MAXIMO = 50


def limite_de(params):
    return min(entero(params, "limite", LIMITE_POR_DEFECTO), LIMITE_MAXIMO)


class VentasView(APIView):
    """Hoy por defecto. La recepcionista solo puede pedir el total de hoy."""

    permission_classes = [AdministradorORecepcionista]

    def get(self, request):
        hoy = timezone.localdate()
        periodo = periodo_de(request.query_params, hoy)
        if request.user.rol == User.Rol.RECEPCIONISTA and not periodo.es_hoy(hoy):
            raise PermissionDenied("Solo puedes consultar el total vendido hoy.")
        return Response(services.ventas(periodo))


class ServiciosYPrendasView(APIView):
    permission_classes = [SoloAdministrador]

    def get(self, request):
        periodo = periodo_de(request.query_params)
        return Response(services.servicios_y_prendas(periodo, limite_de(request.query_params)))


class ClientesFrecuentesView(APIView):
    permission_classes = [SoloAdministrador]

    def get(self, request):
        periodo = periodo_de(request.query_params)
        return Response(services.clientes_frecuentes(periodo, limite_de(request.query_params)))


class OrdenesPorEstadoView(APIView):
    permission_classes = [SoloAdministrador]

    def get(self, request):
        return Response(services.ordenes_por_estado())


class FidelizacionView(APIView):
    permission_classes = [SoloAdministrador]

    def get(self, request):
        hoy = timezone.localdate()
        return Response(services.fidelizacion(periodo_de(request.query_params, hoy), hoy))
