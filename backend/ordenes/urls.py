from django.urls import path

from .views import (
    AlertasVencimientoView,
    AgregarPrendaView,
    AgregarServicioView,
    AsignarOperarioView,
    BandejaOperarioView,
    CambiarEstadoView,
    CambiosDescuentosNovedadView,
    CancelarOrdenView,
    DanosView,
    DecisionNovedadView,
    DescuentosNovedadView,
    FotoDanoView,
    FotoNovedadView,
    HistorialClienteView,
    HistorialOrdenView,
    NovedadesOrdenView,
    OperariosActivosView,
    OrdenDetailView,
    OrdenListCreateView,
    OrdenesConNovedadView,
    PagoDanoView,
    RegistrarEntregaView,
)

urlpatterns = [
    path("ordenes", OrdenListCreateView.as_view(), name="ordenes"),
    path("ordenes/alertas", AlertasVencimientoView.as_view(), name="ordenes-alertas"),
    path("ordenes/novedades", OrdenesConNovedadView.as_view(), name="ordenes-con-novedad"),
    path("ordenes/<int:pk>/decision", DecisionNovedadView.as_view(), name="orden-decision"),
    path("ordenes/bandeja", BandejaOperarioView.as_view(), name="ordenes-bandeja"),
    path("ordenes/<int:pk>", OrdenDetailView.as_view(), name="orden-detalle"),
    path("ordenes/<int:pk>/prendas", AgregarPrendaView.as_view(), name="orden-prendas"),
    path(
        "ordenes/<int:pk>/prendas/<int:prenda_pk>/servicios",
        AgregarServicioView.as_view(),
        name="orden-prenda-servicios",
    ),
    path(
        "ordenes/<int:pk>/asignacion", AsignarOperarioView.as_view(), name="orden-asignacion"
    ),
    path("ordenes/<int:pk>/entrega", RegistrarEntregaView.as_view(), name="orden-entrega"),
    path("ordenes/<int:pk>/estado", CambiarEstadoView.as_view(), name="orden-estado"),
    path(
        "ordenes/<int:pk>/cancelacion", CancelarOrdenView.as_view(), name="orden-cancelacion"
    ),
    path("ordenes/<int:pk>/historial", HistorialOrdenView.as_view(), name="orden-historial"),
    path("clientes/<int:pk>/ordenes", HistorialClienteView.as_view(), name="cliente-ordenes"),
    path("ordenes/<int:pk>/novedades", NovedadesOrdenView.as_view(), name="orden-novedades"),
    path("novedades/<int:pk>/foto", FotoNovedadView.as_view(), name="novedad-foto"),
    path("operarios", OperariosActivosView.as_view(), name="operarios-activos"),
    path(
        "ordenes/descuentos-novedad", DescuentosNovedadView.as_view(), name="descuentos-novedad"
    ),
    path(
        "ordenes/descuentos-novedad/cambios",
        CambiosDescuentosNovedadView.as_view(),
        name="descuentos-novedad-cambios",
    ),
    path("danos", DanosView.as_view(), name="danos"),
    path("danos/<int:pk>/pago", PagoDanoView.as_view(), name="dano-pago"),
    path("danos/<int:pk>/foto", FotoDanoView.as_view(), name="dano-foto"),
]
