from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny

from accounts.models import User

from .services import turno_vigente

MENSAJE_SIN_TURNO = "Inicia tu turno para poder trabajar."


def exenta_de_turno(request):
    vista = (request.parser_context or {}).get("view")
    if vista is None:
        return False
    if getattr(vista, "exento_de_turno", False):
        return True
    # Las rutas publicas (rastreo, recuperar contrasena) no dependen de quien tenga sesion.
    permisos = getattr(vista, "permission_classes", ())
    return bool(permisos) and all(permiso is AllowAny for permiso in permisos)


class SesionConTurno(SessionAuthentication):
    """Sesion de Django que ademas exige turno vigente al operario.

    Es el unico punto de control: cubre toda la API, incluidos los endpoints que se agreguen
    despues. Una vista se exime con el atributo `exento_de_turno = True`.
    """

    def authenticate(self, request):
        resultado = super().authenticate(request)
        if resultado is None:
            return None
        usuario = resultado[0]
        if usuario.rol == User.Rol.OPERARIO and not exenta_de_turno(request) and turno_vigente(usuario) is None:
            raise PermissionDenied({"detail": MENSAJE_SIN_TURNO, "codigo": "turno_no_iniciado"})
        return resultado
