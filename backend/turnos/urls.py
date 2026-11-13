from django.urls import path

from .views import ActividadOperariosView, IniciarTurnoView, TerminarTurnoView, TurnoActualView, TurnosView

urlpatterns = [
    path("turnos", TurnosView.as_view(), name="turnos"),
    path("turnos/iniciar", IniciarTurnoView.as_view(), name="turno-iniciar"),
    path("turnos/terminar", TerminarTurnoView.as_view(), name="turno-terminar"),
    path("turnos/actual", TurnoActualView.as_view(), name="turno-actual"),
    path("operarios/actividad", ActividadOperariosView.as_view(), name="operarios-actividad"),
]
