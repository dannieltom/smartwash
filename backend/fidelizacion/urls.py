from django.urls import path

from .views import (
    AsignarBeneficiosInactividadView,
    ClientesInactivosView,
    EnviarComunicacionesView,
    MisPuntosView,
    PromocionDetailView,
    PromocionesDisponiblesView,
    PromocionListCreateView,
    ReglaDescuentoDetailView,
    ReglaDescuentoListCreateView,
    ReglaInactividadDetailView,
    ReglaInactividadListCreateView,
)

urlpatterns = [
    path("reglas-descuento", ReglaDescuentoListCreateView.as_view(), name="reglas-descuento"),
    path(
        "reglas-descuento/<int:pk>",
        ReglaDescuentoDetailView.as_view(),
        name="regla-descuento-detalle",
    ),
    path("promociones", PromocionListCreateView.as_view(), name="promociones"),
    path(
        "promociones/disponibles",
        PromocionesDisponiblesView.as_view(),
        name="promociones-disponibles",
    ),
    path("promociones/<int:pk>", PromocionDetailView.as_view(), name="promocion-detalle"),
    path("mis-puntos", MisPuntosView.as_view(), name="mis-puntos"),
    path(
        "reglas-inactividad", ReglaInactividadListCreateView.as_view(), name="reglas-inactividad"
    ),
    path(
        "reglas-inactividad/<int:pk>",
        ReglaInactividadDetailView.as_view(),
        name="regla-inactividad-detalle",
    ),
    path("clientes-inactivos", ClientesInactivosView.as_view(), name="clientes-inactivos"),
    path(
        "clientes-inactivos/asignar-beneficios",
        AsignarBeneficiosInactividadView.as_view(),
        name="asignar-beneficios-inactividad",
    ),
    path(
        "comunicaciones/enviar", EnviarComunicacionesView.as_view(), name="enviar-comunicaciones"
    ),
]
