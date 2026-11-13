from django.apps import AppConfig


class TurnosConfig(AppConfig):
    name = "turnos"

    def ready(self):
        from . import signals  # noqa: F401
