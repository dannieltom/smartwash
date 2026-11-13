from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # API SCHEMA y Documentacion
    path("api/", include("core.urls")),
    path("api/", include("accounts.urls")),
    path("api/", include("clientes.urls")),
    path("api/", include("ordenes.urls")),
    path("api/", include("pagos.urls")),
    path("api/", include("turnos.urls")),
    path("api/catalogo/", include("catalogo.urls")),
    path("api/fidelizacion/", include("fidelizacion.urls")),
    # Esquema OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    # Documentación interactiva Swagger UI
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # Documentación interactiva Redoc
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
]
