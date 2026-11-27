from datetime import timedelta
from unittest import mock

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core import mail
from django.db import DatabaseError
from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from clientes.models import Cliente
from fidelizacion.models import ComunicacionPromocional, Promocion
from ordenes.models import HistorialOrden, Orden
from ordenes.tests import OrdenEnProcesoMixin

from .models import Comunicacion

User = get_user_model()
Evento = HistorialOrden.TipoEvento
FALLA_AL_REGISTRAR = "notificaciones.models.Comunicacion.save"


class AvisoOrdenListaRegistradoTests(OrdenEnProcesoMixin, APITestCase):
    def setUp(self):
        super().setUp()
        Cliente.objects.filter(pk=self.cliente.pk).update(correo="ana@example.com")
        Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.CONTROL_CALIDAD)

    def marcar_lista(self):
        self.client.force_authenticate(self.operario)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                f"/api/ordenes/{self.orden.pk}/estado",
                {"estado": Orden.Estado.LISTA},
                format="json",
            )

    def test_al_quedar_lista_la_orden_el_aviso_enviado_queda_registrado(self):
        response = self.marcar_lista()

        self.assertEqual(response.status_code, 200)
        comunicacion = Comunicacion.objects.get()
        self.assertEqual(comunicacion.tipo, Comunicacion.Tipo.ORDEN_LISTA)
        self.assertEqual(comunicacion.cliente, self.cliente)
        self.assertEqual(comunicacion.orden, self.orden)
        self.assertIsNone(comunicacion.promocion)
        self.assertEqual(comunicacion.correo, "ana@example.com")
        self.assertEqual(comunicacion.asunto, mail.outbox[0].subject)
        self.assertEqual(comunicacion.cuerpo, mail.outbox[0].body)
        self.assertIsNotNone(comunicacion.enviada_en)

    def test_un_aviso_que_no_salio_no_se_registra(self):
        with mock.patch("ordenes.avisos.send_mail", side_effect=ConnectionError):
            self.marcar_lista()

        self.assertFalse(Comunicacion.objects.exists())

    def test_sin_correo_no_hay_comunicacion_que_registrar(self):
        Cliente.objects.filter(pk=self.cliente.pk).update(correo="")

        self.marcar_lista()

        self.assertFalse(Comunicacion.objects.exists())

    def test_si_falla_la_base_se_registra_el_error_y_no_queda_constancia_parcial(self):
        with mock.patch(FALLA_AL_REGISTRAR, side_effect=DatabaseError("sin conexion")):
            with self.assertLogs("ordenes.avisos", "ERROR"):
                response = self.marcar_lista()

        self.assertEqual(response.status_code, 200)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.LISTA)
        self.assertFalse(Comunicacion.objects.exists())
        self.assertFalse(self.orden.historial.filter(tipo_evento=Evento.NOTIFICACION).exists())


class ComunicacionesProgramadasRegistradasTests(APITestCase):
    RUTA = "/api/fidelizacion/comunicaciones/enviar"

    def setUp(self):
        self.hoy = timezone.localdate()
        User.objects.create_user(username="admin", password="x", rol=User.Rol.ADMINISTRADOR)
        self.recepcion = User.objects.create_user(
            username="recep", password="x", rol=User.Rol.RECEPCIONISTA
        )
        self.client.login(username="admin", password="x")
        self.cliente = Cliente.objects.create(
            documento="1",
            nombre_completo="Ana Gomez",
            telefono="300",
            correo="ana@example.com",
            clasificacion="VIP",
        )

    def orden_lista_hace(self, dias):
        orden = Orden.objects.create(
            codigo="LISTA-1", cliente=self.cliente, recepcionista=self.recepcion, estado=Orden.Estado.LISTA
        )
        # El historial es inmutable: la fecha pasada se fija al crearlo.
        with mock.patch("django.utils.timezone.now", return_value=timezone.now() - timedelta(days=dias)):
            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento=Evento.CAMBIO_ESTADO,
                detalle="Control de calidad → Lista para entrega",
            )
        return orden

    def promocion(self):
        promocion = Promocion.objects.create(
            nombre="Semana VIP",
            tipo="porcentaje",
            valor=10,
            vigente_desde=self.hoy,
            vigente_hasta=self.hoy + timedelta(days=5),
        )
        promocion.segmentos.create(clasificacion="VIP")
        return promocion

    def test_el_recordatorio_enviado_queda_registrado_con_su_orden(self):
        orden = self.orden_lista_hace(dias=4)

        self.client.post(self.RUTA)

        comunicacion = Comunicacion.objects.get()
        self.assertEqual(comunicacion.tipo, Comunicacion.Tipo.RECORDATORIO)
        self.assertEqual(comunicacion.orden, orden)
        self.assertEqual(comunicacion.cliente, self.cliente)
        self.assertEqual(comunicacion.asunto, mail.outbox[0].subject)

    def test_la_promocion_enviada_queda_registrada_con_su_campana(self):
        promocion = self.promocion()

        self.client.post(self.RUTA)

        comunicacion = Comunicacion.objects.get()
        self.assertEqual(comunicacion.tipo, Comunicacion.Tipo.PROMOCION)
        self.assertEqual(comunicacion.promocion, promocion)
        self.assertIsNone(comunicacion.orden)
        self.assertEqual(comunicacion.correo, "ana@example.com")
        self.assertEqual(comunicacion.cuerpo, mail.outbox[0].body)

    def test_cada_envio_queda_registrado_por_separado(self):
        self.orden_lista_hace(dias=4)
        self.promocion()

        self.client.post(self.RUTA)

        self.assertEqual(
            sorted(Comunicacion.objects.values_list("tipo", flat=True)),
            [Comunicacion.Tipo.PROMOCION, Comunicacion.Tipo.RECORDATORIO],
        )

    def test_un_envio_fallido_no_se_registra(self):
        self.orden_lista_hace(dias=4)
        self.promocion()

        with mock.patch("ordenes.recordatorios.send_mail", side_effect=ConnectionError), \
                mock.patch("fidelizacion.comunicaciones.send_mail", side_effect=ConnectionError):
            self.client.post(self.RUTA)

        self.assertFalse(Comunicacion.objects.exists())

    def test_si_falla_la_base_al_registrar_un_recordatorio_no_queda_constancia_parcial(self):
        orden = self.orden_lista_hace(dias=4)

        with mock.patch(FALLA_AL_REGISTRAR, side_effect=DatabaseError("sin conexion")):
            with self.assertLogs("ordenes.recordatorios", "ERROR"):
                self.client.post(self.RUTA)

        self.assertFalse(Comunicacion.objects.exists())
        self.assertFalse(orden.historial.filter(tipo_evento=Evento.NOTIFICACION).exists())

    def test_si_falla_la_base_al_registrar_una_promocion_no_queda_constancia_parcial(self):
        self.promocion()

        with mock.patch(FALLA_AL_REGISTRAR, side_effect=DatabaseError("sin conexion")):
            with self.assertLogs("fidelizacion.comunicaciones", "ERROR"):
                self.client.post(self.RUTA)

        self.assertFalse(Comunicacion.objects.exists())
        self.assertFalse(ComunicacionPromocional.objects.exists())


class ComunicacionAdminTests(TestCase):
    def test_el_registro_se_consulta_pero_no_se_crea_edita_ni_borra_desde_el_admin(self):
        peticion = RequestFactory().get("/admin/")
        peticion.user = User.objects.create_superuser(username="root", password="x")
        modelo_admin = admin.site._registry[Comunicacion]

        self.assertTrue(modelo_admin.has_view_permission(peticion))
        self.assertFalse(modelo_admin.has_add_permission(peticion))
        self.assertFalse(modelo_admin.has_change_permission(peticion))
        self.assertFalse(modelo_admin.has_delete_permission(peticion))
