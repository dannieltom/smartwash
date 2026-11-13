import hashlib
import logging

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Q
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.utils.decorators import method_decorator
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema  # <-- Importamos extend_schema

from turnos.services import turno_vigente

from .models import RegistroAuditoria, User
from .serializers import (
    MENSAJE_ULTIMO_ADMIN,
    AccionAuditoriaSerializer,
    HistorialAccionSerializer,
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserSerializer,
    UsuarioAdminSerializer,
    UsuarioInternoSerializer,
    es_ultimo_admin_activo,
)


MAX_INTENTOS_LOGIN = 5
BLOQUEO_LOGIN_SEGUNDOS = 15 * 60
MENSAJE_LOGIN_BLOQUEADO = (
    "Demasiados intentos fallidos. Intenta de nuevo en 15 minutos."
)


def _clave_intentos_login(username):
    # Se cuenta por el nombre escrito, exista o no la cuenta: asi el bloqueo no
    # delata cuales existen. El hash evita caracteres invalidos en la clave.
    huella = hashlib.sha256(username.strip().lower().encode()).hexdigest()
    return f"login-fallos:{huella}"


def _registrar_fallo_login(clave):
    cache.add(clave, 0, BLOQUEO_LOGIN_SEGUNDOS)
    try:
        fallos = cache.incr(clave)
    except ValueError:
        cache.set(clave, 1, BLOQUEO_LOGIN_SEGUNDOS)
        return
    if fallos == MAX_INTENTOS_LOGIN:
        # Los 15 minutos corren desde el quinto fallo, no desde el primero.
        cache.touch(clave, BLOQUEO_LOGIN_SEGUNDOS)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    #! Crea la sesion de Django. El navegador recibe la cookie de sesion.

    permission_classes = [AllowAny]

    @extend_schema(
        request=LoginSerializer,
        responses={200: UserSerializer, 401: dict, 429: dict},
        summary="Iniciar sesión",
    )
    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        clave = _clave_intentos_login(data.validated_data["username"])
        if cache.get(clave, 0) >= MAX_INTENTOS_LOGIN:
            # Bloquea incluso con la clave correcta: de lo contrario la
            # respuesta delataria si el intento acertaba.
            return Response(
                {"detail": MENSAJE_LOGIN_BLOQUEADO},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        user = authenticate(request, **data.validated_data)
        if user is None:
            _registrar_fallo_login(clave)
            return Response(
                {"detail": "Credenciales invalidas."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        cache.delete(clave)
        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    exento_de_turno = True

    @extend_schema(
        request=None,
        responses={204: None},
        summary="Cerrar sesión",
    )
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    """Usuario autenticado. Endpoint privado: responde 403 si no hay sesion.

    Ademas siembra la cookie csrftoken, que el frontend necesita antes del login.
    Al operario le dice si tiene turno vigente (`en_turno`).
    """

    exento_de_turno = True

    @extend_schema(
        responses={200: UserSerializer},
        summary="Obtener usuario actual",
    )
    def get(self, request):
        datos = UserSerializer(request.user).data
        if request.user.rol == User.Rol.OPERARIO:
            datos["en_turno"] = turno_vigente(request.user) is not None
        return Response(datos)


logger = logging.getLogger(__name__)

MENSAJE_RECUPERACION = (
    "Si la cuenta existe, recibiras un correo con los pasos a seguir."
)


class RecuperarPasswordPorCuentaThrottle(SimpleRateThrottle):
    """Limita por cuenta pedida y no por IP, que el cliente puede falsear con
    X-Forwarded-For. Asi nadie llena de correos la bandeja de otra persona."""

    scope = "recuperar-password-cuenta"

    def get_cache_key(self, request, view):
        identificador = str(request.data.get("identificador", "")).strip().lower()
        if not identificador:
            return None
        return self.cache_format % {"scope": self.scope, "ident": identificador}


@method_decorator(csrf_protect, name="dispatch")
class RecuperarPasswordView(APIView):
    """Envia el enlace de recuperacion al correo de la cuenta.

    Responde siempre lo mismo, exista o no la cuenta, e incluso si el envio
    falla: cualquier diferencia permitiria averiguar que cuentas existen.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle, RecuperarPasswordPorCuentaThrottle]
    throttle_scope = "recuperar-password"

    @extend_schema(
        request=PasswordResetRequestSerializer,
        responses={200: dict},
        summary="Solicitar recuperación de contraseña",
    )
    def post(self, request):
        data = PasswordResetRequestSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        identificador = data.validated_data["identificador"]

        usuarios = (
            get_user_model()
            .objects.filter(
                Q(username=identificador) | Q(email__iexact=identificador),
                is_active=True,
            )
            .exclude(email="")
        )
        for usuario in usuarios:
            try:
                enviar_correo_recuperacion(usuario)
            except Exception:
                logger.exception(
                    "No se pudo enviar el correo de recuperacion a %s", usuario.pk
                )

        return Response({"detail": MENSAJE_RECUPERACION})


def enviar_correo_recuperacion(usuario):
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    enlace = (
        f"{settings.FRONTEND_URL}/restablecer-password?uid={uid}&token={token}"
    )
    minutos = settings.PASSWORD_RESET_TIMEOUT // 60
    send_mail(
        subject="SmartWash - Recuperar contraseña",
        message=(
            f"Hola {usuario.get_short_name() or usuario.username},\n\n"
            f"Para crear una contraseña nueva entra a este enlace:\n{enlace}\n\n"
            f"El enlace vence en {minutos} minutos y solo se puede usar una vez.\n"
            "Si no lo solicitaste, ignora este correo."
        ),
        from_email=None,
        recipient_list=[usuario.email],
    )


@method_decorator(csrf_protect, name="dispatch")
class ConfirmarRecuperacionPasswordView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={200: dict, 400: dict},
        summary="Confirmar nueva contraseña",
    )
    def post(self, request):
        data = PasswordResetConfirmSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        data.save()
        return Response({"detail": "Contraseña actualizada. Ya puedes iniciar sesión."})


from .serializers import ActuarComoSerializer  # agrega este import junto a los otros de .serializers

# Cuentas fijas que puede tomar el selector de desarrollo. Nunca se acepta un
# username fuera de esta lista, aunque el request lo pida.
USUARIOS_DESARROLLO = ("admin", "recepcion", "operario1", "operario2")


@method_decorator(csrf_protect, name="dispatch")
class ActuarComoView(APIView):
    """Cambia la sesion a una cuenta sembrada, sin pedir contrasena.

    Solo existe con DEBUG=True: en produccion responde 404 en ambos metodos,
    asi que el selector del frontend se oculta solo. Se elimina en T8 (SCRUM-57).
    """

    permission_classes = [IsAuthenticated]
    exento_de_turno = True

    def get(self, request):
        if not settings.DEBUG:
            raise Http404
        usuarios = get_user_model().objects.filter(username__in=USUARIOS_DESARROLLO)
        return Response(UserSerializer(usuarios, many=True).data)

    def post(self, request):
        if not settings.DEBUG:
            raise Http404
        data = ActuarComoSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        username = data.validated_data["username"]
        if username not in USUARIOS_DESARROLLO:
            return Response(
                {"detail": "Cuenta no permitida."}, status=status.HTTP_400_BAD_REQUEST
            )
        usuario = get_object_or_404(get_user_model(), username=username)
        login(request, usuario)
        return Response(UserSerializer(usuario).data)


class UsuarioInternoListCreateView(generics.ListCreateAPIView):
    queryset = get_user_model().objects.all().order_by("username")

    def get_serializer_class(self):
        return UsuarioAdminSerializer if self.request.method == "GET" else UsuarioInternoSerializer


class UsuarioInternoDetailView(generics.RetrieveUpdateAPIView):
    """Sin destroy: la baja es "desactivar", no borrar (ver UsuarioDesactivarView)."""

    queryset = get_user_model().objects.all()
    serializer_class = UsuarioInternoSerializer


class UsuarioDesactivarView(APIView):
    def post(self, request, pk):
        usuario = get_object_or_404(get_user_model(), pk=pk)
        if es_ultimo_admin_activo(usuario):
            return Response({"detail": MENSAJE_ULTIMO_ADMIN}, status=status.HTTP_400_BAD_REQUEST)
        usuario.is_active = False
        usuario._realizado_por = request.user
        usuario.save(update_fields=["is_active"])
        return Response(UsuarioAdminSerializer(usuario).data)


class UsuarioActivarView(APIView):
    def post(self, request, pk):
        if request.user.rol != User.Rol.ADMINISTRADOR:
            return Response(
                {"detail": "Solo un administrador puede activar usuarios."},
                status=status.HTTP_403_FORBIDDEN,
            )
        usuario = get_object_or_404(get_user_model(), pk=pk)
        # Sin cambio no se guarda: la senal registraria una edicion vacia.
        if not usuario.is_active:
            usuario.is_active = True
            usuario._realizado_por = request.user
            usuario.save(update_fields=["is_active"])
        return Response(UsuarioAdminSerializer(usuario).data)


class HistorialUsuarioView(generics.ListAPIView):
    serializer_class = HistorialAccionSerializer

    def get_queryset(self):
        return RegistroAuditoria.objects.filter(usuario_id=self.kwargs["pk"])


class TrazabilidadView(generics.ListAPIView):
    serializer_class = AccionAuditoriaSerializer

    def get_queryset(self):
        queryset = RegistroAuditoria.objects.all()
        tipo_usuario = self.request.query_params.get("rol")
        if tipo_usuario:
            queryset = queryset.filter(tipo_usuario=tipo_usuario)
        return queryset
