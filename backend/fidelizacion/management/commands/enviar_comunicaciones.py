from django.core.management.base import BaseCommand, CommandError

from fidelizacion.comunicaciones import ProcesoComunicacionesFallido, enviar_comunicaciones


class Command(BaseCommand):
    help = "Envia los recordatorios de ordenes no reclamadas y las promociones vigentes."

    def handle(self, *args, **options):
        try:
            resultado = enviar_comunicaciones()
        except ProcesoComunicacionesFallido:
            raise CommandError("El proceso fallo y no se aplico ningun cambio. Revisa el log.")
        for nombre, datos in resultado.items():
            self.stdout.write(
                f"{nombre}: {datos['enviados']} enviados, {datos['sin_correo']} sin correo, "
                f"{datos['fallidos']} fallidos."
            )
