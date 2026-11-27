from django.core.management.base import BaseCommand, CommandError

from fidelizacion.services import (
    ProcesoInactividadFallido,
    SinReglasDeInactividad,
    asignar_beneficios_por_inactividad,
)


class Command(BaseCommand):
    help = "Suma los puntos de las reglas de inactividad a los clientes que llevan ese tiempo sin comprar."

    def handle(self, *args, **options):
        try:
            resultado = asignar_beneficios_por_inactividad()
        except SinReglasDeInactividad:
            raise CommandError("No hay reglas de inactividad activas.")
        except ProcesoInactividadFallido:
            raise CommandError("El proceso fallo y no se aplico ningun cambio. Revisa el log.")
        self.stdout.write(
            f"{resultado['beneficios']} beneficios a {resultado['clientes']} clientes "
            f"({resultado['puntos']} puntos)."
        )
