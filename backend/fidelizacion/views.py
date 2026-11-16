from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from clientes.models import Cliente
from core.permissions import AdministradorORecepcionista, SoloAdministrador

from .models import Promocion, ReglaDescuento
from .serializers import PromocionSerializer, ReglaDescuentoSerializer


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
