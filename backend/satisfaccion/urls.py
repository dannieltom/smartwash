from django.urls import path

from .views import CalificacionesView, CalificarOrdenView

urlpatterns = [
    path(
        "ordenes/consulta/<str:codigo>/calificacion",
        CalificarOrdenView.as_view(),
        name="orden-calificacion",
    ),
    path("calificaciones", CalificacionesView.as_view(), name="calificaciones"),
]
