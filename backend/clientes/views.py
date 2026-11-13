from rest_framework import generics

from core.listas import PAGINACION, ListaPaginadaMixin, buscar_por_palabras, opcion

from .models import Cliente
from .serializers import ClienteSerializer


class ClienteListCreateView(ListaPaginadaMixin, generics.ListCreateAPIView):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    parametros_de_lista = (*PAGINACION, "clasificacion")

    def filtrar_lista(self, clientes, params):
        clasificacion = opcion(params, "clasificacion", Cliente.Clasificacion.values, "Esa clasificacion no existe.")
        clientes = buscar_por_palabras(
            clientes, params.get("buscar", ""), ("nombre_completo", "documento", "telefono", "correo")
        )
        if clasificacion:
            clientes = clientes.filter(clasificacion=clasificacion)
        return clientes.order_by("-creado_en", "-id")


class ClienteDetailView(generics.RetrieveUpdateAPIView):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
