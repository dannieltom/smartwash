from django.urls import path

from .views import (
    ClientesFrecuentesView,
    FidelizacionView,
    OrdenesPorEstadoView,
    ServiciosYPrendasView,
    VentasView,
)

urlpatterns = [
    path("indicadores/ventas", VentasView.as_view(), name="indicadores-ventas"),
    path(
        "indicadores/servicios-y-prendas",
        ServiciosYPrendasView.as_view(),
        name="indicadores-servicios-y-prendas",
    ),
    path(
        "indicadores/clientes-frecuentes",
        ClientesFrecuentesView.as_view(),
        name="indicadores-clientes-frecuentes",
    ),
    path(
        "indicadores/ordenes-por-estado",
        OrdenesPorEstadoView.as_view(),
        name="indicadores-ordenes-por-estado",
    ),
    path("indicadores/fidelizacion", FidelizacionView.as_view(), name="indicadores-fidelizacion"),
]
