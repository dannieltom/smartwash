from django.urls import path

from .views import (
    PromocionDetailView,
    PromocionesDisponiblesView,
    PromocionListCreateView,
    ReglaDescuentoDetailView,
    ReglaDescuentoListCreateView,
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
]
