import re
import time
from datetime import datetime, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient, APITestCase
from django.test import override_settings
from django.utils import timezone

from core.pruebas import PruebasDeListaMixin

from .models import RegistroAuditoria

User = get_user_model()


class AuthTests(APITestCase):
    """Cubre el contrato de autenticacion por sesion que consume el frontend."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="recepcion", password="smartwash123", rol=User.Rol.RECEPCIONISTA
        )

    def test_me_requires_authentication(self):
        self.assertEqual(self.client.get("/api/auth/me").status_code, 403)

    def test_me_sets_the_csrf_cookie_even_when_anonymous(self):
        # El frontend necesita el token antes de poder hacer login.
        response = self.client.get("/api/auth/me")
        self.assertIn("csrftoken", response.cookies)

    def test_login_with_valid_credentials_creates_a_session(self):
        response = self.client.post(
            "/api/auth/login",
            {"username": "recepcion", "password": "smartwash123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["rol"], "recepcionista")
        self.assertIn("sessionid", response.cookies)

        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["username"], "recepcion")

    def test_login_with_invalid_credentials_is_rejected(self):
        response = self.client.post(
            "/api/auth/login", {"username": "recepcion", "password": "incorrecta"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 403)

    def test_login_without_csrf_token_is_rejected(self):
        client = APIClient(enforce_csrf_checks=True)
        client.get("/api/auth/me")  # siembra la cookie csrftoken
        response = client.post(
            "/api/auth/login",
            {"username": "recepcion", "password": "smartwash123"},
        )
        self.assertEqual(response.status_code, 403)

    def test_logout_ends_the_session(self):
        self.client.login(username="recepcion", password="smartwash123")
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 204)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 403)

class LimiteIntentosLoginTests(APITestCase):
    LOGIN = "/api/auth/login"

    def setUp(self):
        cache.clear()
        User.objects.create_user(username="ana", password="smartwash123")

    def intentar(self, username="ana", password="incorrecta"):
        return self.client.post(
            self.LOGIN, {"username": username, "password": password}, format="json"
        )

    def fallar(self, veces, username="ana"):
        for _ in range(veces):
            self.intentar(username)

    def test_el_quinto_fallo_consecutivo_bloquea_los_intentos_siguientes(self):
        self.fallar(4)
        self.assertEqual(self.intentar().status_code, 401)

        response = self.intentar()
        self.assertEqual(response.status_code, 429)
        self.assertIn("15 minutos", response.json()["detail"])

    def test_con_la_cuenta_bloqueada_ni_la_clave_correcta_entra(self):
        self.fallar(5)
        response = self.intentar(password="smartwash123")

        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.client.get("/api/auth/me").status_code, 403)

    def test_el_bloqueo_termina_a_los_15_minutos(self):
        self.fallar(5)
        with mock.patch("time.time", return_value=time.time() + 15 * 60 + 1):
            response = self.intentar(password="smartwash123")
        self.assertEqual(response.status_code, 200)

    def test_el_bloqueo_sigue_vigente_antes_de_los_15_minutos(self):
        self.fallar(5)
        with mock.patch("time.time", return_value=time.time() + 14 * 60):
            response = self.intentar(password="smartwash123")
        self.assertEqual(response.status_code, 429)

    def test_un_acierto_reinicia_el_contador(self):
        self.fallar(4)
        self.assertEqual(self.intentar(password="smartwash123").status_code, 200)
        self.client.post("/api/auth/logout")

        self.fallar(4)
        self.assertEqual(self.intentar(password="smartwash123").status_code, 200)

    def test_una_cuenta_inexistente_se_bloquea_igual_que_una_existente(self):
        self.fallar(5, username="nadie")
        inexistente = self.intentar(username="nadie")

        self.fallar(5, username="ana")
        existente = self.intentar(username="ana")

        self.assertEqual(inexistente.status_code, 429)
        self.assertEqual(inexistente.status_code, existente.status_code)
        self.assertEqual(inexistente.json(), existente.json())

    def test_el_bloqueo_de_una_cuenta_no_afecta_a_las_demas(self):
        User.objects.create_user(username="luis", password="smartwash123")
        self.fallar(5, username="ana")

        self.assertEqual(self.intentar(username="luis", password="smartwash123").status_code, 200)

    def test_el_bloqueo_no_distingue_mayusculas_ni_espacios(self):
        self.fallar(3, username="ana")
        self.fallar(2, username=" ANA ")

        self.assertEqual(self.intentar(username="ana").status_code, 429)

    def test_una_peticion_invalida_no_cuenta_como_fallo(self):
        for _ in range(6):
            self.client.post(self.LOGIN, {"username": "ana"}, format="json")

        self.assertEqual(self.intentar(password="smartwash123").status_code, 200)


class ActuarComoTests(APITestCase):
    def setUp(self):
        User.objects.create_user(
            username="recepcion", password="smartwash123", rol=User.Rol.RECEPCIONISTA
        )
        User.objects.create_user(
            username="operario1", password="smartwash123", rol=User.Rol.OPERARIO
        )
        self.client.login(username="recepcion", password="smartwash123")

    @override_settings(DEBUG=True)
    def test_switches_the_session_to_another_seeded_account(self):
        response = self.client.post(
            "/api/auth/actuar-como", {"username": "operario1"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me").json()["username"], "operario1")

    @override_settings(DEBUG=True)
    def test_rejects_a_username_outside_the_seeded_list(self):
        User.objects.create_user(username="intruso", password="x")
        response = self.client.post("/api/auth/actuar-como", {"username": "intruso"})
        self.assertEqual(response.status_code, 400)

    @override_settings(DEBUG=False)
    def test_is_not_available_outside_debug(self):
        self.assertEqual(
            self.client.post("/api/auth/actuar-como", {"username": "operario1"}).status_code,
            404,
        )


class UsuarioInternoTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="smartwash123", rol=User.Rol.ADMINISTRADOR
        )
        self.client.login(username="admin", password="smartwash123")

    def test_requiere_sesion_activa(self):
        self.client.logout()
        response = self.client.get("/api/usuarios")
        self.assertEqual(response.status_code, 403)

    def test_crea_un_usuario_interno_con_un_rol(self):
        response = self.client.post(
            "/api/usuarios",
            {
                "username": "recepcion1",
                "email": "recepcion1@smartwash.test",
                "first_name": "Ana",
                "last_name": "Gomez",
                "rol": "recepcionista",
                "password": "Lavanderia#2026",
            },
        )
        self.assertEqual(response.status_code, 201)
        usuario = User.objects.get(username="recepcion1")
        self.assertEqual(usuario.rol, User.Rol.RECEPCIONISTA)
        self.assertTrue(usuario.check_password("Lavanderia#2026"))
        self.assertTrue(usuario.is_active)

    def test_crear_sin_password_se_rechaza_y_no_crea_nada(self):
        response = self.client.post(
            "/api/usuarios",
            {"username": "sinclave", "email": "x@smartwash.test", "rol": "operario"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(username="sinclave").exists())

    def test_la_lista_incluye_el_estado_activo_de_cada_usuario(self):
        response = self.client.get("/api/usuarios")
        self.assertEqual(response.status_code, 200)
        admin_listado = next(u for u in response.json() if u["username"] == "admin")
        self.assertIn("is_active", admin_listado)
        self.assertTrue(admin_listado["is_active"])

    def test_edita_el_rol_de_un_usuario_existente(self):
        usuario = User.objects.create_user(
            username="operario1", password="x", rol=User.Rol.OPERARIO
        )
        response = self.client.patch(
            f"/api/usuarios/{usuario.id}", {"rol": "recepcionista"}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        usuario.refresh_from_db()
        self.assertEqual(usuario.rol, User.Rol.RECEPCIONISTA)

    def test_un_usuario_solo_tiene_un_rol_a_la_vez(self):
        # El campo rol es un CharField unico (no una relacion multiple), asi
        # que asignar uno nuevo reemplaza al anterior: nunca conviven dos.
        usuario = User.objects.create_user(
            username="operario1", password="x", rol=User.Rol.OPERARIO
        )
        usuario.rol = User.Rol.RECEPCIONISTA
        usuario.save()
        usuario.refresh_from_db()
        self.assertEqual(usuario.rol, User.Rol.RECEPCIONISTA)

    def test_desactivar_marca_is_active_en_false_sin_borrar_el_usuario(self):
        usuario = User.objects.create_user(
            username="operario1", password="x", rol=User.Rol.OPERARIO
        )
        response = self.client.post(f"/api/usuarios/{usuario.id}/desactivar")
        self.assertEqual(response.status_code, 200)
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)
        self.assertTrue(User.objects.filter(pk=usuario.id).exists())

    def test_activar_devuelve_la_cuenta_a_un_usuario_desactivado_y_puede_iniciar_sesion(self):
        usuario = User.objects.create_user(
            username="operario1", password="x", rol=User.Rol.OPERARIO, is_active=False
        )
        self.assertFalse(APIClient().login(username="operario1", password="x"))

        response = self.client.post(f"/api/usuarios/{usuario.id}/activar")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_active"])
        usuario.refresh_from_db()
        self.assertTrue(usuario.is_active)
        self.assertTrue(APIClient().login(username="operario1", password="x"))

    def test_activar_a_un_usuario_ya_activo_no_cambia_nada_ni_registra_accion(self):
        usuario = User.objects.create_user(username="operario1", password="x", rol=User.Rol.OPERARIO)
        antes = RegistroAuditoria.objects.filter(usuario=usuario).count()

        response = self.client.post(f"/api/usuarios/{usuario.id}/activar")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(RegistroAuditoria.objects.filter(usuario=usuario).count(), antes)

    def test_solo_un_administrador_puede_activar_usuarios(self):
        User.objects.create_user(username="recepcion1", password="x", rol=User.Rol.RECEPCIONISTA)
        usuario = User.objects.create_user(
            username="operario1", password="x", rol=User.Rol.OPERARIO, is_active=False
        )
        self.client.login(username="recepcion1", password="x")

        response = self.client.post(f"/api/usuarios/{usuario.id}/activar")

        self.assertEqual(response.status_code, 403)
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)

    def test_activar_exige_sesion(self):
        usuario = User.objects.create_user(
            username="operario1", password="x", rol=User.Rol.OPERARIO, is_active=False
        )
        self.client.logout()
        response = self.client.post(f"/api/usuarios/{usuario.id}/activar")
        self.assertEqual(response.status_code, 403)
        usuario.refresh_from_db()
        self.assertFalse(usuario.is_active)

    def test_crear_con_una_contrasena_debil_se_rechaza_con_el_motivo(self):
        response = self.client.post(
            "/api/usuarios",
            {"username": "recepcion1", "rol": "recepcionista", "password": "12345678"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())
        self.assertFalse(User.objects.filter(username="recepcion1").exists())

    def test_no_se_puede_desactivar_al_ultimo_administrador_activo(self):
        response = self.client.post(f"/api/usuarios/{self.admin.id}/desactivar")
        self.assertEqual(response.status_code, 400)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_no_se_puede_quitar_el_rol_al_ultimo_administrador_activo(self):
        response = self.client.patch(
            f"/api/usuarios/{self.admin.id}", {"rol": "operario"}, format="json"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("rol", response.json())

    def test_con_otro_administrador_activo_si_se_puede_desactivar(self):
        otro = User.objects.create_user(username="admin2", password="x", rol=User.Rol.ADMINISTRADOR)
        response = self.client.post(f"/api/usuarios/{otro.id}/desactivar")
        self.assertEqual(response.status_code, 200)


class AuditoriaTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="smartwash123", rol=User.Rol.ADMINISTRADOR
        )
        self.client.login(username="admin", password="smartwash123")

    def test_crear_un_usuario_registra_una_accion_de_tipo_creado(self):
        usuario = User.objects.create_user(username="operario1", password="x", rol=User.Rol.OPERARIO)
        registro = RegistroAuditoria.objects.get(usuario=usuario)
        self.assertEqual(registro.accion, RegistroAuditoria.Accion.CREADO)
        self.assertEqual(registro.tipo_usuario, User.Rol.OPERARIO)

    def test_desactivar_un_usuario_registra_una_accion_de_tipo_desactivado(self):
        usuario = User.objects.create_user(username="operario1", password="x", rol=User.Rol.OPERARIO)
        usuario.is_active = False
        usuario.save()
        ultimo = RegistroAuditoria.objects.filter(usuario=usuario).latest("fecha")
        self.assertEqual(ultimo.accion, RegistroAuditoria.Accion.DESACTIVADO)

    def test_reactivar_un_usuario_registra_una_accion_de_tipo_activado(self):
        usuario = User.objects.create_user(
            username="operario1", password="x", rol=User.Rol.OPERARIO, is_active=False
        )
        usuario.is_active = True
        usuario.save()
        ultimo = RegistroAuditoria.objects.filter(usuario=usuario).latest("fecha")
        self.assertEqual(ultimo.accion, RegistroAuditoria.Accion.ACTIVADO)

    def test_editar_un_campo_sin_tocar_is_active_registra_una_accion_de_tipo_editado(self):
        usuario = User.objects.create_user(username="operario1", password="x", rol=User.Rol.OPERARIO)
        usuario.rol = User.Rol.RECEPCIONISTA
        usuario.save()
        ultimo = RegistroAuditoria.objects.filter(usuario=usuario).latest("fecha")
        self.assertEqual(ultimo.accion, RegistroAuditoria.Accion.EDITADO)

    def test_iniciar_sesion_registra_un_inicio_de_sesion_y_no_una_edicion(self):
        usuario = User.objects.create_user(username="operario1", password="x", rol=User.Rol.OPERARIO)
        self.client.post("/api/auth/login", {"username": "operario1", "password": "x"}, format="json")
        acciones = list(RegistroAuditoria.objects.filter(usuario=usuario).values_list("accion", flat=True))
        self.assertEqual(acciones, ["inicio_sesion", "creado"])

    def test_editar_desde_el_api_registra_que_cambio_y_quien_lo_hizo(self):
        usuario = User.objects.create_user(username="operario1", password="x", rol=User.Rol.OPERARIO)
        self.client.patch(
            f"/api/usuarios/{usuario.id}",
            {"rol": "recepcionista", "first_name": "Ana"},
            format="json",
        )
        ultimo = RegistroAuditoria.objects.filter(usuario=usuario).latest("fecha")
        self.assertEqual(ultimo.accion, RegistroAuditoria.Accion.EDITADO)
        self.assertEqual(ultimo.detalle, "nombre · rol: operario → recepcionista · por admin")

    def test_desactivar_desde_el_api_registra_quien_lo_hizo(self):
        usuario = User.objects.create_user(username="operario1", password="x", rol=User.Rol.OPERARIO)
        self.client.post(f"/api/usuarios/{usuario.id}/desactivar")
        ultimo = RegistroAuditoria.objects.filter(usuario=usuario).latest("fecha")
        self.assertEqual(ultimo.accion, RegistroAuditoria.Accion.DESACTIVADO)
        self.assertEqual(ultimo.detalle, "por admin")

    def test_activar_desde_el_api_registra_la_accion_activado_y_quien_lo_hizo(self):
        usuario = User.objects.create_user(
            username="operario1", password="x", rol=User.Rol.OPERARIO, is_active=False
        )
        self.client.post(f"/api/usuarios/{usuario.id}/activar")
        ultimo = RegistroAuditoria.objects.filter(usuario=usuario).latest("fecha")
        self.assertEqual(ultimo.accion, RegistroAuditoria.Accion.ACTIVADO)
        self.assertEqual(ultimo.detalle, "por admin")

    def test_el_historial_de_un_usuario_devuelve_solo_sus_propias_acciones(self):
        usuario = User.objects.create_user(username="operario1", password="x", rol=User.Rol.OPERARIO)
        response = self.client.get(f"/api/usuarios/{usuario.id}/historial")
        self.assertEqual(response.status_code, 200)
        datos = response.json()
        self.assertEqual(len(datos), 1)
        self.assertEqual(datos[0]["accion"], "creado")

    def test_el_historial_de_un_usuario_sin_acciones_informa_una_lista_vacia(self):
        response = self.client.get("/api/usuarios/999999/historial")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_la_trazabilidad_incluye_acciones_de_todos_los_usuarios(self):
        User.objects.create_user(username="operario1", password="x", rol=User.Rol.OPERARIO)
        User.objects.create_user(username="recepcion1", password="x", rol=User.Rol.RECEPCIONISTA)
        response = self.client.get("/api/usuarios/trazabilidad")
        self.assertEqual(response.status_code, 200)
        # admin (setUp) + operario1 + recepcion1: al menos 3 altas registradas.
        self.assertGreaterEqual(len(response.json()), 3)

    def test_la_trazabilidad_se_filtra_por_tipo_de_usuario(self):
        User.objects.create_user(username="recepcion1", password="x", rol=User.Rol.RECEPCIONISTA)
        response = self.client.get("/api/usuarios/trazabilidad?rol=recepcionista")
        self.assertEqual(response.status_code, 200)
        datos = response.json()
        self.assertTrue(datos)
        self.assertTrue(all(item["tipo_usuario"] == "recepcionista" for item in datos))

    def test_la_trazabilidad_sin_coincidencias_informa_una_lista_vacia(self):
        response = self.client.get("/api/usuarios/trazabilidad?rol=cliente")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_los_registros_de_auditoria_no_se_pueden_editar_ni_eliminar_desde_el_admin(self):
        from django.contrib import admin as django_admin

        from .admin import RegistroAuditoriaAdmin

        admin_site = RegistroAuditoriaAdmin(RegistroAuditoria, django_admin.site)
        self.assertFalse(admin_site.has_add_permission(None))
        self.assertFalse(admin_site.has_change_permission(None))
        self.assertFalse(admin_site.has_delete_permission(None))


@override_settings(FRONTEND_URL="http://front.test")
class RecuperarPasswordTests(APITestCase):
    SOLICITAR = "/api/auth/recuperar-password"
    CONFIRMAR = "/api/auth/confirmar-recuperacion"

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="ana", email="ana@smartwash.co", password="ClaveVieja#2026"
        )
        self.uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        self.token = default_token_generator.make_token(self.user)

    def confirmar(self, **cambios):
        datos = {"uid": self.uid, "token": self.token, "password": "ClaveNueva#2026", **cambios}
        return self.client.post(self.CONFIRMAR, datos, format="json")

    def assertPasswordSinCambios(self):
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ClaveVieja#2026"))

    def test_solicitar_con_el_correo_envia_un_enlace_al_frontend(self):
        response = self.client.post(self.SOLICITAR, {"identificador": "ana@smartwash.co"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["ana@smartwash.co"])
        enlace = re.search(
            r"http://front\.test/restablecer-password\?uid=([^&]+)&token=(\S+)",
            mail.outbox[0].body,
        )
        self.assertIsNotNone(enlace)
        self.assertEqual(enlace.group(1), self.uid)

    def test_solicitar_con_el_nombre_de_usuario_tambien_envia_el_correo(self):
        self.client.post(self.SOLICITAR, {"identificador": "ana"}, format="json")
        self.assertEqual(len(mail.outbox), 1)

    def test_el_correo_se_reconoce_sin_importar_mayusculas(self):
        self.client.post(self.SOLICITAR, {"identificador": "ANA@SmartWash.co"}, format="json")
        self.assertEqual(len(mail.outbox), 1)

    def test_una_cuenta_inexistente_recibe_la_misma_respuesta_y_no_se_envia_correo(self):
        existente = self.client.post(self.SOLICITAR, {"identificador": "ana"}, format="json")
        inexistente = self.client.post(self.SOLICITAR, {"identificador": "nadie@x.co"}, format="json")

        self.assertEqual(inexistente.status_code, existente.status_code)
        self.assertEqual(inexistente.json(), existente.json())
        self.assertEqual(len(mail.outbox), 1)

    def test_una_cuenta_desactivada_no_recibe_correo(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post(self.SOLICITAR, {"identificador": "ana"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_una_cuenta_sin_correo_no_recibe_correo(self):
        User.objects.create_user(username="sincorreo", password="x")
        self.client.post(self.SOLICITAR, {"identificador": "sincorreo"}, format="json")
        self.assertEqual(len(mail.outbox), 0)

    def test_si_el_envio_falla_la_respuesta_no_lo_revela_pero_queda_en_el_log(self):
        with (
            mock.patch("accounts.views.send_mail", side_effect=OSError("smtp caido")),
            self.assertLogs("accounts.views", level="ERROR"),
        ):
            response = self.client.post(self.SOLICITAR, {"identificador": "ana"}, format="json")
        self.assertEqual(response.status_code, 200)

    def test_solicitar_sin_identificador_se_rechaza(self):
        response = self.client.post(self.SOLICITAR, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("identificador", response.json())

    def test_limita_las_solicitudes_repetidas_desde_la_misma_ip(self):
        for numero in range(5):
            self.client.post(self.SOLICITAR, {"identificador": f"nadie{numero}"}, format="json")
        response = self.client.post(self.SOLICITAR, {"identificador": "ana"}, format="json")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(mail.outbox), 0)

    def test_limita_las_solicitudes_por_cuenta_aunque_cambie_la_ip(self):
        for numero in range(3):
            self.client.post(
                self.SOLICITAR, {"identificador": "ana"}, format="json",
                HTTP_X_FORWARDED_FOR=f"10.0.0.{numero}",
            )
        response = self.client.post(
            self.SOLICITAR, {"identificador": "ANA"}, format="json", HTTP_X_FORWARDED_FOR="10.0.0.9"
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(len(mail.outbox), 3)

    def test_solicitar_sin_token_csrf_se_rechaza(self):
        client = APIClient(enforce_csrf_checks=True)
        response = client.post(self.SOLICITAR, {"identificador": "ana"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_confirmar_con_un_enlace_valido_cambia_la_contrasena(self):
        response = self.confirmar()

        self.assertEqual(response.status_code, 200)
        login = self.client.post(
            "/api/auth/login", {"username": "ana", "password": "ClaveNueva#2026"}, format="json"
        )
        self.assertEqual(login.status_code, 200)

    def test_el_enlace_solo_se_puede_usar_una_vez(self):
        self.assertEqual(self.confirmar().status_code, 200)
        self.assertEqual(self.confirmar(password="OtraClave#2026").status_code, 400)

    def test_un_token_alterado_se_rechaza(self):
        response = self.confirmar(token="token-falso")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["non_field_errors"], ["El enlace de recuperación no es válido o expiró."])
        self.assertPasswordSinCambios()

    def test_un_uid_invalido_se_rechaza(self):
        self.assertEqual(self.confirmar(uid="no-es-base64!").status_code, 400)
        self.assertPasswordSinCambios()

    def test_el_token_de_otro_usuario_no_sirve(self):
        otro = User.objects.create_user(username="beto", email="beto@x.co", password="x")
        response = self.confirmar(uid=urlsafe_base64_encode(force_bytes(otro.pk)))
        self.assertEqual(response.status_code, 400)

    def test_un_enlace_de_hace_mas_de_una_hora_expira(self):
        hace_dos_horas = datetime.now() - timedelta(hours=2)
        with mock.patch.object(default_token_generator, "_now", return_value=hace_dos_horas):
            token_viejo = default_token_generator.make_token(self.user)

        self.assertEqual(self.confirmar(token=token_viejo).status_code, 400)
        self.assertPasswordSinCambios()

    def test_una_cuenta_desactivada_no_puede_confirmar(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.confirmar().status_code, 400)

    def test_una_contrasena_debil_se_rechaza_con_el_motivo(self):
        response = self.confirmar(password="123")

        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())
        self.assertPasswordSinCambios()

    def test_confirmar_sin_campos_se_rechaza(self):
        response = self.client.post(self.CONFIRMAR, {}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(set(response.json()), {"uid", "token", "password"})


class ListaUsuariosPaginadaApiTests(PruebasDeListaMixin, APITestCase):
    url = "/api/usuarios"
    invalidos = ({"rol": "cliente"}, {"activo": "si"})

    def setUp(self):
        self.client.force_authenticate(
            User.objects.create_user(username="jefe", password="x", rol=User.Rol.ADMINISTRADOR)
        )
        self.numero = 0

    def crear(self, cuando, **campos):
        self.numero += 1
        usuario = User.objects.create_user(
            username=campos.pop("username", f"usuario{self.numero}"), password="x", rol=campos.pop("rol", User.Rol.OPERARIO), **campos
        )
        User.objects.filter(pk=usuario.pk).update(date_joined=cuando)
        return usuario

    def test_busca_por_usuario_nombre_apellido_y_correo(self):
        ana = self.crear(timezone.now(), username="arojas", first_name="Ana", last_name="Rojas", email="ana@sw.co")
        luis = self.crear(timezone.now(), username="lperez", first_name="Luis", last_name="Perez", email="luis@sw.co")

        for texto, esperado in (("AROJAS", ana), ("luis", luis), ("perez", luis), ("ana@sw", ana), ("ana rojas", ana)):
            with self.subTest(texto=texto):
                self.assertEqual(self.claves(self.listar(buscar=texto)), [esperado.pk])
        self.assertEqual(self.claves(self.listar(buscar="ana perez")), [])

    def test_filtra_por_rol_y_por_estado(self):
        recepcion = self.crear(timezone.now(), rol=User.Rol.RECEPCIONISTA)
        inactivo = self.crear(timezone.now(), is_active=False)

        self.assertEqual(self.claves(self.listar(rol="recepcionista")), [recepcion.pk])
        self.assertEqual(self.claves(self.listar(activo="false")), [inactivo.pk])
        self.assertNotIn(inactivo.pk, self.claves(self.listar(activo="true")))
