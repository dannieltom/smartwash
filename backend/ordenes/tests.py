import base64
from datetime import date, datetime
from datetime import timezone as dt_timezone
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import ProtectedError
from django.test import TestCase, TransactionTestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APITestCase

from catalogo.models import Material, NivelDificultad, Servicio, Tarifa, TipoPrenda, redondear_a_100
from clientes.models import Cliente
from fidelizacion.models import ReglaDescuento

from .historial import OperacionNoCompletada, operacion_sobre_orden, registrar_evento
from .models import (
    FotoNovedad,
    HistorialOrden,
    Novedad,
    Orden,
    OrdenServicio,
    Prenda,
    duracion_estimada_dias,
    sumar_dias_habiles,
)

User = get_user_model()


class OrdenTests(TestCase):
    def setUp(self):
        self.recepcionista = User.objects.create_user(
            username="recepcion", password="x", rol=User.Rol.RECEPCIONISTA
        )
        self.cliente = Cliente.objects.create(
            documento="1090123456", nombre_completo="Ana Gomez", telefono="3001112233"
        )
        self.camisa = TipoPrenda.objects.create(nombre="Camisa")
        self.lavado = Servicio.objects.create(nombre="Lavado")
        self.planchado = Servicio.objects.create(nombre="Planchado")
        self.tarifa_lavado = self.crear_tarifa(self.lavado, "8000")
        self.tarifa_planchado = self.crear_tarifa(self.planchado, "4000")
        self.orden = Orden.objects.create(
            codigo="ORD-0001",
            cliente=self.cliente,
            recepcionista=self.recepcionista,
        )

    def crear_tarifa(self, servicio, valor):
        return Tarifa.objects.create(
            tipo_prenda=self.camisa,
            servicio=servicio,
            valor_base=Decimal(valor),
            precio_por_kilo=Decimal("0"),
            plazo_entrega_dias=2,
            vigente_desde=date(2026, 1, 1),
        )

    def crear_prenda(self):
        return Prenda.objects.create(orden=self.orden, tipo_prenda=self.camisa)

    def test_el_codigo_de_la_orden_es_unico(self):
        with self.assertRaises(IntegrityError):
            Orden.objects.create(
                codigo="ORD-0001",
                cliente=self.cliente,
                recepcionista=self.recepcionista,
            )

    def test_la_orden_nace_en_espera_sin_operario_y_sin_pagar(self):
        self.assertEqual(self.orden.estado, Orden.Estado.EN_ESPERA)
        self.assertEqual(self.orden.estado_pago, Orden.EstadoPago.PENDIENTE)
        self.assertIsNone(self.orden.operario)

    def test_una_prenda_admite_varios_servicios(self):
        prenda = self.crear_prenda()
        OrdenServicio.objects.create(
            prenda=prenda, tarifa=self.tarifa_lavado, valor_aplicado=Decimal("8000")
        )
        OrdenServicio.objects.create(
            prenda=prenda, tarifa=self.tarifa_planchado, valor_aplicado=Decimal("4000")
        )

        self.assertEqual(prenda.servicios.count(), 2)

    def test_no_repite_el_mismo_servicio_en_una_prenda(self):
        prenda = self.crear_prenda()
        OrdenServicio.objects.create(
            prenda=prenda, tarifa=self.tarifa_lavado, valor_aplicado=Decimal("8000")
        )
        with self.assertRaises(IntegrityError):
            OrdenServicio.objects.create(
                prenda=prenda, tarifa=self.tarifa_lavado, valor_aplicado=Decimal("8000")
            )

    def test_cambiar_la_tarifa_no_altera_lo_ya_cobrado(self):
        prenda = self.crear_prenda()
        servicio = OrdenServicio.objects.create(
            prenda=prenda, tarifa=self.tarifa_lavado, valor_aplicado=Decimal("8000")
        )

        self.tarifa_lavado.valor = Decimal("12000")
        self.tarifa_lavado.save()
        servicio.refresh_from_db()

        self.assertEqual(servicio.valor_aplicado, Decimal("8000"))

    def test_no_se_puede_borrar_un_cliente_con_ordenes(self):
        with self.assertRaises(ProtectedError):
            self.cliente.delete()

    def test_no_se_puede_borrar_una_tarifa_ya_cobrada(self):
        OrdenServicio.objects.create(
            prenda=self.crear_prenda(),
            tarifa=self.tarifa_lavado,
            valor_aplicado=Decimal("8000"),
        )
        with self.assertRaises(ProtectedError):
            self.tarifa_lavado.delete()

    def test_borrar_la_orden_borra_sus_prendas_y_sus_servicios(self):
        prenda = self.crear_prenda()
        OrdenServicio.objects.create(
            prenda=prenda, tarifa=self.tarifa_lavado, valor_aplicado=Decimal("8000")
        )

        self.orden.delete()

        self.assertEqual(Prenda.objects.count(), 0)
        self.assertEqual(OrdenServicio.objects.count(), 0)

    def test_rechaza_una_prenda_con_cantidad_cero(self):
        with self.assertRaises(IntegrityError):
            Prenda.objects.create(
                orden=self.orden, tipo_prenda=self.camisa, cantidad=0
            )

    def test_desactivar_al_operario_no_borra_la_orden(self):
        operario = User.objects.create_user(
            username="op", password="x", rol=User.Rol.OPERARIO
        )
        self.orden.abono_alcanzado_en = date(2026, 1, 1)
        self.orden.operario = operario
        self.orden.save()

        operario.delete()
        self.orden.refresh_from_db()

        self.assertIsNone(self.orden.operario)
        self.assertEqual(Orden.objects.count(), 1)


Evento = HistorialOrden.TipoEvento


def crear_orden(codigo="ORD-0100"):
    recepcionista, _ = User.objects.get_or_create(
        username="recepcion", defaults={"rol": User.Rol.RECEPCIONISTA}
    )
    cliente, _ = Cliente.objects.get_or_create(
        documento="1090123456",
        defaults={"nombre_completo": "Ana Gomez", "telefono": "3001112233"},
    )
    return Orden.objects.create(codigo=codigo, cliente=cliente, recepcionista=recepcionista)


class RegistrarEventoTests(TestCase):
    def test_rechaza_un_tipo_de_evento_desconocido(self):
        orden = crear_orden()
        with self.assertRaises(ValueError):
            registrar_evento(orden, "borrado", orden.recepcionista)

    def test_si_falla_el_registro_no_se_aplica_el_cambio_ni_el_historial(self):
        orden = crear_orden()
        with (
            mock.patch.object(
                HistorialOrden.objects, "create", side_effect=OperationalError("sin conexion")
            ),
            self.assertLogs("ordenes.historial", level="ERROR") as logs,
            self.assertRaises(OperacionNoCompletada) as error,
        ):
            with operacion_sobre_orden():
                orden.estado = Orden.Estado.CLASIFICADA
                orden.save()
                registrar_evento(orden, Evento.CAMBIO_ESTADO, orden.recepcionista)

        orden.refresh_from_db()
        self.assertEqual(orden.estado, Orden.Estado.EN_ESPERA)
        self.assertFalse(HistorialOrden.objects.exists())
        self.assertIn("sin conexion", "\n".join(logs.output))
        self.assertNotIn("sin conexion", str(error.exception.detail))


class RegistrarEventoFueraDeTransaccionTests(TransactionTestCase):
    def test_exige_estar_dentro_de_la_transaccion_del_cambio(self):
        orden = crear_orden()
        with self.assertRaises(RuntimeError):
            registrar_evento(orden, Evento.CREACION, orden.recepcionista)


class InmutabilidadHistorialTests(TestCase):
    def setUp(self):
        self.orden = crear_orden()
        self.evento = registrar_evento(
            self.orden, Evento.CREACION, self.orden.recepcionista, "original"
        )

    def test_no_se_puede_editar_un_registro(self):
        self.evento.detalle = "alterado"
        with self.assertRaises(PermissionDenied):
            self.evento.save()
        with self.assertRaises(PermissionDenied):
            HistorialOrden.objects.update(detalle="alterado")
        copia = HistorialOrden(pk=self.evento.pk, orden=self.orden, tipo_evento=Evento.PAGO)
        with self.assertRaises(IntegrityError), transaction.atomic():
            copia.save()

        self.assertEqual(HistorialOrden.objects.get().detalle, "original")

    def test_no_se_puede_borrar_un_registro(self):
        with self.assertRaises(PermissionDenied):
            self.evento.delete()
        with self.assertRaises(PermissionDenied):
            self.orden.historial.all().delete()

        self.assertTrue(HistorialOrden.objects.exists())


class HistorialOrdenApiTests(APITestCase):
    def setUp(self):
        self.orden = crear_orden()
        self.recepcionista = self.orden.recepcionista
        self.admin = User.objects.create_user(
            username="admin", password="x", rol=User.Rol.ADMINISTRADOR
        )
        registrar_evento(self.orden, Evento.CREACION, self.recepcionista, "creada")
        registrar_evento(self.orden, Evento.ASIGNACION, self.admin, "operario1")
        registrar_evento(crear_orden(codigo="ORD-0200"), Evento.CREACION, self.recepcionista)
        self.url = f"/api/ordenes/{self.orden.pk}/historial"

    def test_el_administrador_ve_el_historial_de_la_orden_en_orden_cronologico(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(e["tipo_evento"], e["usuario_nombre"], e["detalle"]) for e in response.json()],
            [(Evento.CREACION, "recepcion", "creada"), (Evento.ASIGNACION, "admin", "operario1")],
        )
        self.assertTrue(all(e["fecha"] for e in response.json()))

    def test_la_recepcionista_consulta_y_el_operario_no(self):
        self.client.force_login(self.recepcionista)
        self.assertEqual(self.client.get(self.url).status_code, 200)

        operario = User.objects.create_user(username="op", password="x", rol=User.Rol.OPERARIO)
        self.client.force_login(operario)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_una_orden_inexistente_responde_404(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/api/ordenes/9999/historial").status_code, 404)

    def test_la_api_no_permite_escribir_el_historial(self):
        self.client.force_login(self.admin)
        for metodo in ("post", "put", "patch", "delete"):
            response = getattr(self.client, metodo)(self.url, {"detalle": "x"}, format="json")
            self.assertEqual(response.status_code, 405, metodo)

        self.assertEqual(self.orden.historial.count(), 2)


# El manifiesto de WhiteNoise solo existe tras collectstatic; el admin lo necesita para renderizar.
@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class HistorialDesdeAdminTests(TestCase):
    def setUp(self):
        self.superusuario = User.objects.create_superuser(
            username="root", password="x", rol=User.Rol.ADMINISTRADOR
        )
        self.client.force_login(self.superusuario)
        self.orden = crear_orden()
        # Con el abono ya registrado, para poder asignarla (HU23).
        Orden.objects.filter(pk=self.orden.pk).update(
            estado=Orden.Estado.RECIBIDA, abono_alcanzado_en=date(2026, 10, 1)
        )

    def guardar(self, url, **cambios):
        response = self.client.get(url)
        formularios = [response.context["adminform"].form]
        for inline in response.context["inline_admin_formsets"]:
            formularios.append(inline.formset.management_form)
            formularios.extend(inline.formset.forms)
        datos = {
            campo.html_name: campo.value()
            for formulario in formularios
            for campo in formulario
            if campo.value() is not None
        }
        datos.update(cambios)
        self.assertEqual(self.client.post(url, datos).status_code, 302)

    def editar_orden(self, **cambios):
        self.guardar(f"/admin/ordenes/orden/{self.orden.pk}/change/", **cambios)

    def test_los_cambios_de_la_orden_quedan_en_el_historial(self):
        operario1 = User.objects.create_user(username="operario1", rol=User.Rol.OPERARIO)
        operario2 = User.objects.create_user(username="operario2", rol=User.Rol.OPERARIO)

        self.editar_orden(operario=operario1.pk)
        self.editar_orden(operario=operario2.pk)
        self.editar_orden(estado=Orden.Estado.ENTREGADA)

        self.assertEqual(
            list(self.orden.historial.values_list("tipo_evento", "detalle")),
            [
                (Evento.ASIGNACION, "sin operario → operario1"),
                (Evento.REASIGNACION, "operario1 → operario2"),
                (Evento.ENTREGA, "Recibida → Entregada"),
            ],
        )
        self.assertTrue(all(e.usuario == self.superusuario for e in self.orden.historial.all()))

    def test_agregar_prenda_y_servicio_quedan_en_el_historial(self):
        camisa = TipoPrenda.objects.create(nombre="Camisa")
        tarifa = Tarifa.objects.create(
            tipo_prenda=camisa,
            servicio=Servicio.objects.create(nombre="Lavado"),
            valor_base=Decimal("8000"),
            precio_por_kilo=Decimal("0"),
            plazo_entrega_dias=2,
            vigente_desde=date(2026, 1, 1),
        )
        self.editar_orden(
            **{"prendas-TOTAL_FORMS": "1", "prendas-0-tipo_prenda": camisa.pk, "prendas-0-cantidad": "2"}
        )
        prenda = self.orden.prendas.get()
        self.guardar(
            f"/admin/ordenes/prenda/{prenda.pk}/change/",
            **{"servicios-TOTAL_FORMS": "1", "servicios-0-tarifa": tarifa.pk, "servicios-0-valor_aplicado": "8000"},
        )

        self.assertEqual(
            list(self.orden.historial.values_list("tipo_evento", flat=True)),
            [Evento.PRENDA_AGREGADA, Evento.SERVICIO_AGREGADO],
        )

    def test_el_admin_no_permite_editar_ni_borrar_registros(self):
        evento = registrar_evento(self.orden, Evento.CREACION, self.superusuario, "original")
        base = f"/admin/ordenes/historialorden/{evento.pk}"

        self.assertEqual(self.client.post(f"{base}/change/", {"detalle": "x"}).status_code, 403)
        self.assertEqual(self.client.post(f"{base}/delete/", {"post": "yes"}).status_code, 403)
        evento.refresh_from_db()
        self.assertEqual(evento.detalle, "original")


class CatalogoDePruebaMixin:
    def crear_catalogo(self):
        self.recepcionista = User.objects.create_user(
            username="recepcion", password="x", rol=User.Rol.RECEPCIONISTA
        )
        self.cliente = Cliente.objects.create(
            documento="1090123456", nombre_completo="Ana Gomez", telefono="3001112233"
        )
        self.camisa = TipoPrenda.objects.create(nombre="Camisa")
        self.pantalon = TipoPrenda.objects.create(nombre="Pantalon")
        self.facil = NivelDificultad.objects.create(nombre="Facil", factor=Decimal("1.00"))
        self.dificil = NivelDificultad.objects.create(nombre="Dificil", factor=Decimal("1.60"))
        self.algodon = Material.objects.create(nombre="Algodon", nivel_dificultad=self.facil)
        self.jean = Material.objects.create(nombre="Jean", nivel_dificultad=self.facil)
        self.lavado = Servicio.objects.create(nombre="Lavado")
        self.planchado = Servicio.objects.create(nombre="Planchado")
        self.tarifa(self.camisa, self.lavado, "0", "4000")
        self.tarifa(self.camisa, self.planchado, "6000")

    def tarifa(self, tipo_prenda, servicio, base, por_kilo="0", **vigencia):
        vigencia.setdefault("vigente_desde", date(2020, 1, 1))
        return Tarifa.objects.create(
            tipo_prenda=tipo_prenda,
            servicio=servicio,
            valor_base=Decimal(base),
            precio_por_kilo=Decimal(por_kilo),
            plazo_entrega_dias=1,
            **vigencia,
        )

    def prenda(self, *servicios, tipo=None, **extra):
        datos = {
            "tipo_prenda": (tipo or self.camisa).pk,
            "material": self.algodon.pk,
            "cantidad": 1,
            "peso": "2.5",
            "servicios": [s.pk for s in servicios],
        }
        datos.update(extra)
        return datos

    def registrar(self, *prendas):
        return self.client.post(
            "/api/ordenes",
            {"cliente": self.cliente.pk, "prendas": list(prendas)},
            format="json",
        )


class RegistrarOrdenApiTests(CatalogoDePruebaMixin, APITestCase):
    def setUp(self):
        self.crear_catalogo()
        self.client.force_authenticate(self.recepcionista)

    def test_registra_la_orden_en_espera_con_valor_abono_duracion_e_historial(self):
        response = self.registrar(self.prenda(self.lavado, self.planchado, color="azul"))

        self.assertEqual(response.status_code, 201, response.json())
        datos = response.json()
        self.assertTrue(datos["codigo"].startswith("SW-"))
        self.assertEqual(datos["estado"], Orden.Estado.EN_ESPERA)
        self.assertEqual(datos["estado_pago"], Orden.EstadoPago.PENDIENTE)
        # Lavado: 4000 por kilo x 2,5 kg. Planchado: 6000 por prenda.
        self.assertEqual(Decimal(datos["valor_total"]), Decimal("16000"))
        self.assertEqual(Decimal(datos["abono_requerido"]), Decimal("4800"))
        self.assertEqual(datos["duracion_estimada_dias"], 2)
        self.assertIsNone(datos["fecha_estimada_entrega"])
        self.assertEqual(datos["detalle_prendas"][0]["color"], "azul")
        orden = Orden.objects.get()
        self.assertEqual(
            list(orden.historial.values_list("tipo_evento", flat=True)), [Evento.CREACION]
        )

    def test_el_abono_requerido_se_redondea_hacia_arriba(self):
        self.tarifa(self.pantalon, self.planchado, "3335")
        ReglaDescuento.objects.create(
            nombre="Cinco",
            tipo=ReglaDescuento.Tipo.PORCENTAJE,
            valor=Decimal("5"),
            vigente_desde=date(2020, 1, 1),
        )

        datos = self.registrar(self.prenda(self.planchado, tipo=self.pantalon)).json()

        # 3335 se redondea a 3300; con 5 % de descuento el total es 3135 y el
        # 30 % (940,5) sube a 941.
        self.assertEqual(Decimal(datos["subtotal"]), Decimal("3300"))
        self.assertEqual(Decimal(datos["valor_total"]), Decimal("3135"))
        self.assertEqual(Decimal(datos["abono_requerido"]), Decimal("941"))

    def test_rechaza_una_orden_sin_prendas(self):
        for cuerpo in ({"cliente": self.cliente.pk, "prendas": []}, {"cliente": self.cliente.pk}):
            response = self.client.post("/api/ordenes", cuerpo, format="json")

            self.assertEqual(response.status_code, 400)
            self.assertIn("al menos una prenda", str(response.json()["prendas"]))
        self.assertFalse(Orden.objects.exists())

    def test_rechaza_una_prenda_sin_servicios(self):
        response = self.registrar(self.prenda())

        self.assertEqual(response.status_code, 400)

    def test_rechaza_una_combinacion_sin_tarifa_vigente(self):
        self.tarifa(
            self.pantalon,
            self.lavado,
            "0",
            "5000",
            vigente_hasta=date(2021, 1, 1),
        )

        response = self.registrar(self.prenda(self.lavado, tipo=self.pantalon))

        self.assertEqual(response.status_code, 400)
        self.assertIn("No hay tarifa vigente", str(response.json()))
        self.assertFalse(Orden.objects.exists())

    def test_el_peso_es_obligatorio_y_mayor_que_cero_sin_importar_el_servicio(self):
        for peso in (None, "0", "-1"):
            for servicio in (self.lavado, self.planchado):
                with self.subTest(peso=peso, servicio=servicio.nombre):
                    response = self.registrar(self.prenda(servicio, peso=peso))

                    self.assertEqual(response.status_code, 400)
                    self.assertIn("peso", str(response.json()))
        sin_campo = self.prenda(self.planchado)
        del sin_campo["peso"]
        self.assertEqual(self.registrar(sin_campo).status_code, 400)
        self.assertFalse(Orden.objects.exists())

    def test_aplica_solo_la_regla_de_descuento_que_mas_descuenta(self):
        self.tarifa(self.pantalon, self.planchado, "27000")
        regla = {"activa": True, "vigente_desde": date(2020, 1, 1)}
        ReglaDescuento.objects.create(nombre="10%", tipo="porcentaje", valor=10, **regla)
        ReglaDescuento.objects.create(nombre="Fijo", tipo="monto_fijo", valor=1000, **regla)

        response = self.registrar(self.prenda(self.planchado, tipo=self.pantalon, cantidad=1))

        self.assertEqual(Decimal(response.json()["descuento"]), Decimal("2700"))
        self.assertEqual(Decimal(response.json()["valor_total"]), Decimal("24300"))

    def test_sin_regla_aplicable_el_descuento_es_cero(self):
        ReglaDescuento.objects.create(
            nombre="Inactiva", tipo="porcentaje", valor=50, activa=False,
            vigente_desde=date(2020, 1, 1),
        )
        ReglaDescuento.objects.create(
            nombre="Vencida", tipo="porcentaje", valor=50,
            vigente_desde=date(2020, 1, 1), vigente_hasta=date(2021, 1, 1),
        )
        ReglaDescuento.objects.create(
            nombre="Solo VIP", tipo="porcentaje", valor=50,
            clasificacion_cliente=Cliente.Clasificacion.VIP, vigente_desde=date(2020, 1, 1),
        )

        response = self.registrar(self.prenda(self.planchado))

        self.assertEqual(Decimal(response.json()["descuento"]), Decimal("0"))
        self.assertEqual(Decimal(response.json()["valor_total"]), Decimal("6000"))

    def test_el_operario_no_registra_ordenes(self):
        operario = User.objects.create_user(username="op", password="x", rol=User.Rol.OPERARIO)
        self.client.force_authenticate(operario)

        self.assertEqual(self.registrar(self.prenda(self.planchado)).status_code, 403)

    def test_si_una_prenda_es_invalida_no_se_guarda_nada(self):
        response = self.registrar(
            self.prenda(self.planchado), self.prenda(self.lavado, tipo=self.pantalon)
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Orden.objects.exists())
        self.assertFalse(Prenda.objects.exists())

    def test_cambiar_la_tarifa_despues_no_altera_la_orden(self):
        self.registrar(self.prenda(self.planchado))
        Tarifa.objects.filter(servicio=self.planchado).update(valor_base=Decimal("9999"))

        self.assertEqual(Orden.objects.get().valor_total, Decimal("6000"))


class AgregarLineasApiTests(CatalogoDePruebaMixin, APITestCase):
    def setUp(self):
        self.crear_catalogo()
        self.client.force_authenticate(self.recepcionista)
        self.registrar(self.prenda(self.planchado))
        self.orden = Orden.objects.get()

    def agregar_prenda(self, *servicios, **extra):
        return self.client.post(
            f"/api/ordenes/{self.orden.pk}/prendas", self.prenda(*servicios, **extra), format="json"
        )

    def agregar_servicio(self, servicio):
        prenda = self.orden.prendas.first()
        return self.client.post(
            f"/api/ordenes/{self.orden.pk}/prendas/{prenda.pk}/servicios",
            {"servicio": servicio.pk},
            format="json",
        )

    def test_agregar_una_prenda_recalcula_total_abono_y_duracion(self):
        response = self.agregar_prenda(self.lavado)

        self.assertEqual(response.status_code, 201, response.json())
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.valor_total, Decimal("16000"))
        self.assertEqual(self.orden.abono_requerido, Decimal("4800"))
        self.assertEqual(self.orden.duracion_estimada_dias, 2)
        self.assertEqual(self.orden.historial.last().tipo_evento, Evento.PRENDA_AGREGADA)

    def test_agregar_un_servicio_a_una_prenda_recalcula_y_queda_en_el_historial(self):
        response = self.agregar_servicio(self.lavado)

        self.assertEqual(response.status_code, 201, response.json())
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.valor_total, Decimal("16000"))
        self.assertEqual(self.orden.historial.last().tipo_evento, Evento.SERVICIO_AGREGADO)

    def test_no_repite_un_servicio_en_la_misma_prenda(self):
        self.assertEqual(self.agregar_servicio(self.planchado).status_code, 400)

    def test_con_el_abono_ya_alcanzado_no_se_pide_otro_y_se_recalcula_la_fecha(self):
        # Viernes; la orden queda "Recibida" ese dia.
        Orden.objects.filter(pk=self.orden.pk).update(
            estado=Orden.Estado.RECIBIDA,
            abono_alcanzado_en=date(2026, 10, 9),
            abono_requerido=Decimal("1800"),
        )

        self.agregar_servicio(self.lavado)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.valor_total, Decimal("16000"))
        self.assertEqual(self.orden.abono_requerido, Decimal("1800"))
        # Dos servicios = 2 dias habiles: sabado y, saltando el domingo, lunes.
        self.assertEqual(self.orden.fecha_estimada_entrega, date(2026, 10, 12))

    def test_desde_en_proceso_no_se_agregan_prendas_ni_servicios(self):
        Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.EN_PROCESO)

        self.assertEqual(self.agregar_prenda(self.planchado).status_code, 400)
        self.assertEqual(self.agregar_servicio(self.lavado).status_code, 400)
        self.assertEqual(self.orden.prendas.count(), 1)


class DuracionEstimadaTests(TestCase):
    def test_un_dia_base_mas_medio_dia_por_servicio_adicional_redondeado_hacia_arriba(self):
        self.assertEqual(
            [duracion_estimada_dias(n) for n in (1, 2, 3, 4)], [1, 2, 2, 3]
        )

    @override_settings(ORDEN_DURACION_POR_SERVICIO_ADICIONAL=Decimal("1"))
    def test_los_valores_son_configurables(self):
        self.assertEqual(duracion_estimada_dias(3), 3)

    def test_cuenta_de_lunes_a_sabado_sin_domingos(self):
        sabado = date(2026, 10, 10)
        self.assertEqual(sumar_dias_habiles(sabado, 1), date(2026, 10, 12))
        self.assertEqual(sumar_dias_habiles(date(2026, 10, 5), 5), sabado)


class AbonoAntesDeAsignarTests(CatalogoDePruebaMixin, APITestCase):
    def setUp(self):
        self.crear_catalogo()
        self.client.force_authenticate(self.recepcionista)
        # 16000 de valor total; abono minimo 4800.
        self.registrar(self.prenda(self.lavado, self.planchado))
        self.orden = Orden.objects.get()
        self.operario = User.objects.create_user(
            username="op", password="x", rol=User.Rol.OPERARIO
        )

    def pagar(self, monto):
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/pagos",
            {"monto": monto, "metodo": "efectivo"},
            format="json",
        )
        self.orden.refresh_from_db()

    def asignar(self):
        with operacion_sobre_orden():
            orden = Orden.objects.select_for_update().get(pk=self.orden.pk)
            orden.operario = self.operario
            orden.save()

    def test_con_el_abono_minimo_la_orden_se_puede_asignar(self):
        self.pagar("4800")

        self.asignar()

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.operario, self.operario)

    def test_sin_abono_no_se_asigna_e_indica_el_abono_requerido(self):
        self.pagar("1000")

        with self.assertRaises(ValidationError) as error:
            self.asignar()

        self.assertIn("$4800", str(error.exception.detail))
        self.assertIn("faltan $3800", str(error.exception.detail))
        self.orden.refresh_from_db()
        self.assertIsNone(self.orden.operario)

    def test_una_orden_nueva_queda_en_espera_y_no_se_puede_asignar(self):
        self.assertEqual(self.orden.estado, Orden.Estado.EN_ESPERA)
        self.assertFalse(self.orden.tiene_abono())
        with self.assertRaises(ValidationError):
            self.asignar()

    def test_al_registrar_el_abono_la_orden_pasa_a_recibida_y_se_puede_asignar(self):
        self.pagar("2000")
        self.pagar("2800")

        self.assertEqual(self.orden.estado, Orden.Estado.RECIBIDA)
        self.asignar()

    def test_un_abono_insuficiente_queda_parcial_y_la_orden_sigue_en_espera(self):
        self.pagar("4799")

        self.assertEqual(self.orden.estado_pago, Orden.EstadoPago.PARCIAL)
        self.assertEqual(self.orden.estado, Orden.Estado.EN_ESPERA)
        with self.assertRaises(ValidationError):
            self.asignar()

    def test_si_sube_el_total_despues_del_abono_no_se_vuelve_a_exigir(self):
        self.pagar("4800")
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/prendas", self.prenda(self.lavado), format="json"
        )
        self.orden.refresh_from_db()

        self.assertEqual(self.orden.valor_total, Decimal("26000"))
        self.assertEqual(self.orden.estado, Orden.Estado.RECIBIDA)
        self.assertTrue(self.orden.tiene_abono())
        self.asignar()

    def test_ningun_camino_guarda_una_orden_asignada_sin_abono(self):
        self.orden.operario = self.operario
        with self.assertRaises(DjangoValidationError):
            self.orden.save()
        with self.assertRaises(DjangoValidationError):
            self.orden.full_clean()

    @override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
        }
    )
    def test_el_admin_muestra_el_error_y_no_asigna(self):
        admin = User.objects.create_superuser(
            username="root", password="x", rol=User.Rol.ADMINISTRADOR
        )
        self.client.force_login(admin)
        url = f"/admin/ordenes/orden/{self.orden.pk}/change/"
        formulario = self.client.get(url).context["adminform"].form
        datos = {c.html_name: c.value() for c in formulario if c.value() is not None}
        datos.update(
            {
                "operario": self.operario.pk,
                "prendas-TOTAL_FORMS": "0",
                "prendas-INITIAL_FORMS": "0",
                "historial-TOTAL_FORMS": "0",
                "historial-INITIAL_FORMS": "0",
            }
        )

        response = self.client.post(url, datos)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "abono minimo de $4800")
        self.orden.refresh_from_db()
        self.assertIsNone(self.orden.operario)


class EntregaExigePagoCompletoTests(CatalogoDePruebaMixin, APITestCase):
    def setUp(self):
        self.crear_catalogo()
        self.client.force_authenticate(self.recepcionista)
        # 16000 de valor total.
        self.registrar(self.prenda(self.lavado, self.planchado))
        self.orden = Orden.objects.get()

    def pagar(self, monto):
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/pagos",
            {"monto": monto, "metodo": "efectivo"},
            format="json",
        )

    def entregar(self):
        with operacion_sobre_orden():
            orden = Orden.objects.select_for_update().get(pk=self.orden.pk)
            orden.estado = Orden.Estado.ENTREGADA
            orden.save()

    def preparar_para_entrega(self):
        Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.LISTA)

    def test_con_el_pago_completo_la_orden_se_entrega(self):
        self.pagar("16000")
        self.preparar_para_entrega()

        self.entregar()

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.ENTREGADA)

    def test_con_pago_incompleto_se_bloquea_e_indica_el_saldo(self):
        self.pagar("10000")
        self.preparar_para_entrega()

        with self.assertRaises(ValidationError) as error:
            self.entregar()

        self.assertIn("saldo pendiente $6000", str(error.exception.detail))
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.LISTA)

    def test_el_bloqueo_aplica_tambien_al_administrador_y_fuera_de_la_api(self):
        self.preparar_para_entrega()
        self.orden.refresh_from_db()
        self.orden.estado = Orden.Estado.ENTREGADA

        with self.assertRaises(DjangoValidationError):
            self.orden.full_clean()
        with self.assertRaises(DjangoValidationError):
            self.orden.save()

    def test_nadie_deja_el_estado_de_pago_en_pagada_sin_pago_completo(self):
        self.pagar("10000")
        self.orden.refresh_from_db()

        self.orden.estado_pago = Orden.EstadoPago.PAGADA
        self.orden.save()
        respuesta = self.client.patch(
            f"/api/ordenes/{self.orden.pk}", {"estado_pago": "Pagada"}, format="json"
        )

        self.assertEqual(respuesta.status_code, 405)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado_pago, Orden.EstadoPago.PARCIAL)

    def test_si_sube_el_total_tras_el_abono_hay_que_pagar_la_diferencia_para_entregar(self):
        self.pagar("16000")
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/prendas", self.prenda(self.planchado), format="json"
        )
        self.preparar_para_entrega()

        with self.assertRaises(ValidationError) as error:
            self.entregar()
        self.assertIn("saldo pendiente $6000", str(error.exception.detail))

        self.pagar("6000")
        self.entregar()

    def test_si_falla_la_base_no_se_aplica_ningun_cambio(self):
        self.pagar("16000")
        self.preparar_para_entrega()

        with (
            mock.patch.object(Orden, "save", side_effect=OperationalError("sin conexion")),
            self.assertLogs("ordenes.historial", level="ERROR"),
            self.assertRaises(OperacionNoCompletada),
        ):
            self.entregar()

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.LISTA)


class RegistrarEntregaApiTests(CatalogoDePruebaMixin, APITestCase):
    def setUp(self):
        self.crear_catalogo()
        self.client.force_authenticate(self.recepcionista)
        # Dos prendas: 6000 + 10000 = 16000.
        self.registrar(self.prenda(self.planchado), self.prenda(self.lavado, color="rojo"))
        self.orden = Orden.objects.get()
        self.camisa_1, self.camisa_2 = self.orden.prendas.all()
        self.url = f"/api/ordenes/{self.orden.pk}/entrega"

    def pagar(self, monto):
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/pagos",
            {"monto": monto, "metodo": "efectivo"},
            format="json",
        )

    def lista_y_pagada(self, monto="16000"):
        self.pagar(monto)
        Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.LISTA)

    def entregar(self, *verificaciones):
        if not verificaciones:
            verificaciones = (
                {"prenda": self.camisa_1.pk, "coincide": True},
                {"prenda": self.camisa_2.pk, "coincide": True},
            )
        return self.client.post(self.url, {"prendas": list(verificaciones)}, format="json")

    def test_verificadas_las_prendas_y_pagada_la_orden_queda_entregada(self):
        self.lista_y_pagada()

        response = self.entregar()

        self.assertEqual(response.status_code, 200, response.json())
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.ENTREGADA)
        self.assertIsNotNone(self.orden.fecha_entrega)
        evento = self.orden.historial.last()
        self.assertEqual(evento.tipo_evento, Evento.ENTREGA)
        self.assertEqual(evento.usuario, self.recepcionista)
        self.assertIn("2 prendas verificadas, todas coinciden", evento.detalle)

    def test_una_prenda_que_no_coincide_exige_observacion_y_deja_la_orden_con_novedad(self):
        self.lista_y_pagada()
        sin_observacion = self.entregar(
            {"prenda": self.camisa_1.pk, "coincide": True},
            {"prenda": self.camisa_2.pk, "coincide": False, "observacion": "  "},
        )

        self.assertEqual(sin_observacion.status_code, 400)
        self.assertIn("observacion", str(sin_observacion.json()))

        response = self.entregar(
            {"prenda": self.camisa_1.pk, "coincide": True},
            {"prenda": self.camisa_2.pk, "coincide": False, "observacion": "Mancha en el cuello"},
        )

        self.assertEqual(response.status_code, 200)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.CON_NOVEDAD)
        evento = self.orden.historial.last()
        self.assertEqual(evento.tipo_evento, Evento.NOVEDAD)
        self.assertIn("Mancha en el cuello (sin foto)", evento.detalle)

    def test_con_pago_incompleto_no_se_entrega_e_indica_el_saldo(self):
        self.lista_y_pagada(monto="10000")

        response = self.entregar()

        self.assertEqual(response.status_code, 400)
        self.assertIn("saldo pendiente $6000", str(response.json()))
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.LISTA)
        self.assertNotEqual(self.orden.historial.last().tipo_evento, Evento.ENTREGA)

    def test_solo_se_entrega_desde_lista_para_entrega(self):
        self.pagar("16000")

        response = self.entregar()

        self.assertEqual(response.status_code, 400)
        self.assertIn("Lista para entrega", str(response.json()))

    def test_hay_que_verificar_cada_prenda_una_sola_vez(self):
        self.lista_y_pagada()
        uno = {"prenda": self.camisa_1.pk, "coincide": True}

        for verificaciones in ((uno,), (uno, uno), (uno, {"prenda": 999, "coincide": True})):
            self.assertEqual(self.entregar(*verificaciones).status_code, 400)
        self.assertEqual(self.client.post(self.url, {"prendas": []}, format="json").status_code, 400)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.LISTA)

    def test_el_operario_no_registra_entregas(self):
        self.lista_y_pagada()
        operario = User.objects.create_user(username="op", password="x", rol=User.Rol.OPERARIO)
        self.client.force_authenticate(operario)

        self.assertEqual(self.entregar().status_code, 403)



class CambiarEstadoApiTests(CatalogoDePruebaMixin, APITestCase):
    SECUENCIA = ("Clasificada", "En proceso", "Control de calidad", "Lista para entrega")

    def setUp(self):
        self.crear_catalogo()
        self.client.force_authenticate(self.recepcionista)
        self.registrar(self.prenda(self.planchado), self.prenda(self.lavado, color="rojo"))
        self.orden = Orden.objects.get()
        self.operario = User.objects.create_user(username="op", password="x", rol=User.Rol.OPERARIO)
        self.otro_operario = User.objects.create_user(
            username="otro", password="x", rol=User.Rol.OPERARIO
        )
        self.administrador = User.objects.create_user(
            username="admin", password="x", rol=User.Rol.ADMINISTRADOR
        )
        self.url = f"/api/ordenes/{self.orden.pk}/estado"

    def con_abono(self, operario=None):
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/pagos",
            {"monto": "4800", "metodo": "efectivo"},
            format="json",
        )
        if operario is not None:
            Orden.objects.filter(pk=self.orden.pk).update(operario=operario)

    def poner_estado(self, estado):
        Orden.objects.filter(pk=self.orden.pk).update(estado=estado)

    def cambiar(self, usuario, estado):
        self.client.force_authenticate(usuario)
        return self.client.post(self.url, {"estado": estado}, format="json")

    def test_la_recepcionista_clasifica_y_el_operario_asignado_recorre_el_resto(self):
        self.con_abono(self.operario)
        self.assertEqual(self.cambiar(self.recepcionista, "Clasificada").status_code, 200)
        previo = self.orden.historial.count()

        anterior = "Clasificada"
        for estado in self.SECUENCIA[1:]:
            response = self.cambiar(self.operario, estado)
            self.assertEqual(response.status_code, 200, response.json())
            evento = self.orden.historial.last()
            self.assertEqual(evento.tipo_evento, Evento.CAMBIO_ESTADO)
            self.assertEqual(evento.usuario, self.operario)
            self.assertEqual(evento.detalle, f"{anterior} → {estado}")
            anterior = estado

        self.assertEqual(self.orden.historial.count(), previo + len(self.SECUENCIA) - 1)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.LISTA)

    def test_el_operario_asignado_no_clasifica_la_orden(self):
        self.con_abono(self.operario)
        previo = self.orden.historial.count()

        self.assertEqual(self.cambiar(self.operario, "Clasificada").status_code, 403)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.RECIBIDA)
        self.assertEqual(self.orden.historial.count(), previo)

    def test_el_operario_no_cambia_ordenes_de_otro_ni_sin_asignar(self):
        self.con_abono(self.otro_operario)
        self.poner_estado(Orden.Estado.CLASIFICADA)
        previo = self.orden.historial.count()
        self.assertEqual(self.cambiar(self.operario, "En proceso").status_code, 403)

        Orden.objects.filter(pk=self.orden.pk).update(operario=None)
        self.assertEqual(self.cambiar(self.operario, "En proceso").status_code, 403)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.CLASIFICADA)
        self.assertEqual(self.orden.historial.count(), previo)

    def test_el_administrador_cambia_cualquier_orden(self):
        self.con_abono(self.otro_operario)

        response = self.cambiar(self.administrador, "Clasificada")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.orden.historial.last().usuario, self.administrador)

    def test_la_recepcionista_no_cambia_estados_posteriores_a_clasificada(self):
        self.con_abono(self.operario)
        self.poner_estado(Orden.Estado.CLASIFICADA)

        self.assertEqual(self.cambiar(self.recepcionista, "En proceso").status_code, 403)

    def test_una_orden_sin_operario_no_pasa_a_en_proceso(self):
        self.con_abono()
        self.poner_estado(Orden.Estado.CLASIFICADA)

        response = self.cambiar(self.administrador, "En proceso")

        self.assertEqual(response.status_code, 400)
        self.assertIn("operario asignado", str(response.json()))
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.CLASIFICADA)

    def test_una_orden_en_espera_no_se_mueve(self):
        response = self.cambiar(self.administrador, "Clasificada")

        self.assertEqual(response.status_code, 400)
        self.assertIn("abono minimo", str(response.json()))
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.EN_ESPERA)

    def test_no_se_saltan_pasos_ni_se_retrocede(self):
        self.con_abono(self.operario)

        salto = self.cambiar(self.administrador, "Lista para entrega")
        self.assertEqual(salto.status_code, 400)
        self.assertIn('No se puede pasar de "Recibida" a "Lista para entrega"', str(salto.json()))

        self.poner_estado(Orden.Estado.EN_PROCESO)
        self.assertEqual(self.cambiar(self.operario, "Clasificada").status_code, 400)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.EN_PROCESO)

    def test_la_entrega_no_se_hace_por_este_endpoint(self):
        self.con_abono(self.operario)
        self.poner_estado(Orden.Estado.LISTA)

        self.assertEqual(self.cambiar(self.administrador, "Entregada").status_code, 400)

    def test_un_estado_desconocido_se_rechaza(self):
        self.con_abono(self.operario)

        self.assertEqual(self.cambiar(self.operario, "Volando").status_code, 400)

    def test_el_reproceso_vuelve_a_en_proceso_las_veces_que_haga_falta(self):
        self.con_abono(self.operario)
        self.poner_estado(Orden.Estado.CONTROL_CALIDAD)

        for _ in range(2):
            self.assertEqual(self.cambiar(self.operario, "En proceso").status_code, 200)
            self.assertEqual(self.cambiar(self.operario, "Control de calidad").status_code, 200)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.numero_reprocesos, 2)
        self.assertEqual(self.orden.valor_total, Decimal("16000"))

    def test_si_falla_la_base_no_se_aplica_ningun_cambio(self):
        self.con_abono(self.operario)

        previo = self.orden.historial.count()

        with (
            mock.patch.object(Orden, "save", side_effect=OperationalError("sin conexion")),
            self.assertLogs("ordenes.historial", level="ERROR"),
        ):
            response = self.cambiar(self.recepcionista, "Clasificada")

        self.assertEqual(response.status_code, 503)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.RECIBIDA)
        self.assertEqual(self.orden.historial.count(), previo)


class AsignarOperarioApiTests(CatalogoDePruebaMixin, APITestCase):
    def setUp(self):
        self.crear_catalogo()
        self.client.force_authenticate(self.recepcionista)
        # 16000 de valor total; abono minimo 4800.
        self.registrar(self.prenda(self.lavado, self.planchado))
        self.orden = Orden.objects.get()
        self.operario = User.objects.create_user(
            username="op1", password="x", rol=User.Rol.OPERARIO, first_name="Luis"
        )
        self.otro_operario = User.objects.create_user(
            username="op2", password="x", rol=User.Rol.OPERARIO, first_name="Marta"
        )
        self.admin = User.objects.create_user(
            username="jefe", password="x", rol=User.Rol.ADMINISTRADOR
        )

    def pagar(self, monto):
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/pagos",
            {"monto": monto, "metodo": "efectivo"},
            format="json",
        )

    def asignar(self, operario):
        pk = operario.pk if isinstance(operario, User) else operario
        return self.client.post(
            f"/api/ordenes/{self.orden.pk}/asignacion", {"operario": pk}, format="json"
        )

    def eventos(self, tipo):
        return HistorialOrden.objects.filter(orden=self.orden, tipo_evento=tipo)

    def fijar_estado(self, estado):
        Orden.objects.filter(pk=self.orden.pk).update(estado=estado)

    def desactivar(self, usuario):
        usuario.is_active = False
        usuario.save()

    def test_con_abono_la_recepcionista_asigna_y_queda_en_el_historial(self):
        self.pagar("4800")

        response = self.asignar(self.operario)

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["operario"], self.operario.pk)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.operario, self.operario)
        self.assertEqual(self.orden.actualizado_por, self.recepcionista)
        evento = self.eventos(Evento.ASIGNACION).get()
        self.assertEqual(evento.usuario, self.recepcionista)
        self.assertEqual(evento.detalle, "Asignada a Luis")
        self.assertIsNotNone(evento.fecha)

    def test_el_administrador_tambien_asigna(self):
        self.pagar("4800")
        self.client.force_authenticate(self.admin)

        self.assertEqual(self.asignar(self.operario).status_code, 200)
        self.assertEqual(self.eventos(Evento.ASIGNACION).get().usuario, self.admin)

    def test_sin_abono_rechaza_e_indica_que_se_requiere(self):
        self.pagar("1000")

        response = self.asignar(self.operario)

        self.assertEqual(response.status_code, 400)
        self.assertIn("abono minimo de $4800", str(response.json()))
        self.orden.refresh_from_db()
        self.assertIsNone(self.orden.operario)
        self.assertFalse(self.eventos(Evento.ASIGNACION).exists())

    def test_no_asigna_una_orden_en_espera(self):
        self.pagar("4800")
        self.fijar_estado(Orden.Estado.EN_ESPERA)

        response = self.asignar(self.operario)

        self.assertEqual(response.status_code, 400)
        self.assertIn("En espera", str(response.json()))

    def test_no_asigna_a_un_operario_inactivo(self):
        self.pagar("4800")
        self.desactivar(self.operario)

        response = self.asignar(self.operario)

        self.assertEqual(response.status_code, 400)
        self.assertIn("operario activo", str(response.json()))

    def test_no_asigna_a_quien_no_es_operario_ni_a_ids_invalidos(self):
        self.pagar("4800")

        for invalido in (self.recepcionista, self.admin, 999999, "abc", None):
            with self.subTest(invalido=invalido):
                self.assertEqual(self.asignar(invalido).status_code, 400)
        self.orden.refresh_from_db()
        self.assertIsNone(self.orden.operario)

    def test_reasigna_en_recibida_y_en_clasificada(self):
        self.pagar("4800")
        self.asignar(self.operario)

        self.assertEqual(self.asignar(self.otro_operario).status_code, 200)
        self.fijar_estado(Orden.Estado.CLASIFICADA)
        self.assertEqual(self.asignar(self.operario).status_code, 200)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.operario, self.operario)
        detalles = list(self.eventos(Evento.REASIGNACION).values_list("detalle", flat=True))
        self.assertEqual(detalles, ["Luis → Marta", "Marta → Luis"])

    def test_reasignar_al_mismo_operario_se_rechaza_sin_ensuciar_el_historial(self):
        self.pagar("4800")
        self.asignar(self.operario)

        self.assertEqual(self.asignar(self.operario).status_code, 400)
        self.assertFalse(self.eventos(Evento.REASIGNACION).exists())

    def test_en_proceso_la_orden_queda_fija(self):
        self.pagar("4800")
        self.asignar(self.operario)
        self.fijar_estado(Orden.Estado.EN_PROCESO)

        self.assertEqual(self.asignar(self.otro_operario).status_code, 400)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.asignar(self.otro_operario).status_code, 400)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.operario, self.operario)

    def test_el_admin_reasigna_en_proceso_si_el_operario_fue_desactivado(self):
        self.pagar("4800")
        self.asignar(self.operario)
        self.fijar_estado(Orden.Estado.EN_PROCESO)
        self.desactivar(self.operario)

        self.assertEqual(self.asignar(self.otro_operario).status_code, 400)
        self.client.force_authenticate(self.admin)
        response = self.asignar(self.otro_operario)

        self.assertEqual(response.status_code, 200, response.json())
        evento = self.eventos(Evento.REASIGNACION).get()
        self.assertEqual(evento.usuario, self.admin)
        self.assertIn("desactivado", evento.detalle)

    def test_no_reasigna_una_orden_lista_entregada_o_cancelada(self):
        self.pagar("4800")
        self.asignar(self.operario)
        self.desactivar(self.operario)
        self.client.force_authenticate(self.admin)

        for estado in (Orden.Estado.LISTA, Orden.Estado.ENTREGADA, Orden.Estado.CANCELADA):
            with self.subTest(estado=estado):
                self.fijar_estado(estado)
                self.assertEqual(self.asignar(self.otro_operario).status_code, 400)

    def test_el_operario_recibe_403_al_asignar_o_reasignar(self):
        self.pagar("4800")
        self.client.force_authenticate(self.operario)
        self.assertEqual(self.asignar(self.operario).status_code, 403)

        self.client.force_authenticate(self.recepcionista)
        self.asignar(self.operario)
        self.client.force_authenticate(self.operario)
        self.assertEqual(self.asignar(self.otro_operario).status_code, 403)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.operario, self.operario)

    def test_sin_sesion_no_asigna(self):
        self.client.force_authenticate(None)

        self.assertIn(self.asignar(self.operario).status_code, (401, 403))

    def test_una_peticion_rechazada_no_deja_cambios_ni_eventos(self):
        self.pagar("4800")
        antes = HistorialOrden.objects.count()

        self.assertEqual(self.asignar(None).status_code, 400)

        self.orden.refresh_from_db()
        self.assertIsNone(self.orden.operario)
        self.assertEqual(HistorialOrden.objects.count(), antes)

    def test_si_falla_el_historial_no_queda_la_asignacion(self):
        self.pagar("4800")

        with mock.patch("ordenes.views.registrar_evento", side_effect=OperationalError("caida")):
            response = self.asignar(self.operario)

        self.assertEqual(response.status_code, 503)
        self.orden.refresh_from_db()
        self.assertIsNone(self.orden.operario)

    def test_lista_solo_operarios_activos_para_recepcion_y_admin(self):
        User.objects.create_user(
            username="op3", password="x", rol=User.Rol.OPERARIO, is_active=False
        )

        response = self.client.get("/api/operarios")

        self.assertEqual(response.status_code, 200)
        ids = {o["id"] for o in response.json()}
        self.assertEqual(ids, {self.operario.pk, self.otro_operario.pk})
        self.client.force_authenticate(self.operario)
        self.assertEqual(self.client.get("/api/operarios").status_code, 403)



class BandejaOperarioApiTests(CatalogoDePruebaMixin, APITestCase):
    def setUp(self):
        self.crear_catalogo()
        self.operario = User.objects.create_user(
            username="op1", password="x", rol=User.Rol.OPERARIO
        )
        self.otro_operario = User.objects.create_user(
            username="op2", password="x", rol=User.Rol.OPERARIO
        )

    def orden_asignada(self, operario):
        self.client.force_authenticate(self.recepcionista)
        pk = self.registrar(self.prenda(self.lavado, self.planchado, color="azul")).json()["id"]
        self.client.post(
            f"/api/ordenes/{pk}/pagos", {"monto": "4800", "metodo": "efectivo"}, format="json"
        )
        self.client.post(f"/api/ordenes/{pk}/asignacion", {"operario": operario.pk}, format="json")
        return Orden.objects.get(pk=pk)

    def bandeja(self, usuario=None):
        self.client.force_authenticate(usuario or self.operario)
        return self.client.get("/api/ordenes/bandeja")

    def test_el_operario_ve_solo_sus_ordenes_pendientes_con_codigo_estado_prendas_y_fecha(self):
        mia = self.orden_asignada(self.operario)
        self.orden_asignada(self.otro_operario)

        response = self.bandeja()

        self.assertEqual(response.status_code, 200)
        datos = response.json()
        self.assertEqual([o["id"] for o in datos], [mia.pk])
        orden = datos[0]
        self.assertEqual(orden["codigo"], mia.codigo)
        self.assertEqual(orden["estado"], Orden.Estado.RECIBIDA)
        self.assertEqual(orden["fecha_estimada_entrega"], mia.fecha_estimada_entrega.isoformat())
        prenda = orden["prendas"][0]
        self.assertEqual(prenda["tipo_prenda_nombre"], "Camisa")
        self.assertEqual(prenda["cantidad"], 1)
        self.assertEqual(prenda["color"], "azul")
        self.assertEqual(prenda["servicios"], ["Lavado", "Planchado"])

    def test_la_bandeja_no_expone_cliente_ni_valores(self):
        self.orden_asignada(self.operario)

        orden = self.bandeja().json()[0]

        for campo in ("cliente", "cliente_nombre", "valor_total", "total_pagado", "saldo_pendiente"):
            self.assertNotIn(campo, orden)
        self.assertNotIn("valor_aplicado", str(orden))

    def test_sin_ordenes_asignadas_la_bandeja_esta_vacia(self):
        self.orden_asignada(self.otro_operario)

        response = self.bandeja()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_no_muestra_entregadas_ni_canceladas(self):
        pendiente = self.orden_asignada(self.operario)
        for estado in (Orden.Estado.ENTREGADA, Orden.Estado.CANCELADA):
            orden = self.orden_asignada(self.operario)
            Orden.objects.filter(pk=orden.pk).update(estado=estado)

        self.assertEqual([o["id"] for o in self.bandeja().json()], [pendiente.pk])

    def test_muestra_las_ordenes_en_cualquier_estado_pendiente(self):
        estados = (
            Orden.Estado.RECIBIDA,
            Orden.Estado.CLASIFICADA,
            Orden.Estado.EN_PROCESO,
            Orden.Estado.CONTROL_CALIDAD,
            Orden.Estado.LISTA,
        )
        for estado in estados:
            orden = self.orden_asignada(self.operario)
            Orden.objects.filter(pk=orden.pk).update(estado=estado)

        self.assertCountEqual([o["estado"] for o in self.bandeja().json()], estados)

    def test_las_ordenes_en_espera_no_aparecen(self):
        self.client.force_authenticate(self.recepcionista)
        self.registrar(self.prenda(self.lavado))

        self.assertEqual(self.bandeja().json(), [])

    def test_toda_orden_de_la_bandeja_tiene_fecha_estimada(self):
        self.orden_asignada(self.operario)
        self.orden_asignada(self.operario)

        self.assertTrue(all(o["fecha_estimada_entrega"] for o in self.bandeja().json()))

    def test_una_orden_reasignada_pasa_a_la_bandeja_del_nuevo_operario(self):
        orden = self.orden_asignada(self.operario)
        self.client.post(
            f"/api/ordenes/{orden.pk}/asignacion", {"operario": self.otro_operario.pk}, format="json"
        )

        self.assertEqual(self.bandeja().json(), [])
        self.assertEqual([o["id"] for o in self.bandeja(self.otro_operario).json()], [orden.pk])

    def test_el_operario_no_abre_por_la_api_una_orden_ajena(self):
        ajena = self.orden_asignada(self.otro_operario)
        sin_asignar = self.registrar(self.prenda(self.lavado)).json()["id"]
        self.client.force_authenticate(self.operario)

        self.assertEqual(self.client.get(f"/api/ordenes/{ajena.pk}").status_code, 403)
        self.assertEqual(self.client.get(f"/api/ordenes/{sin_asignar}").status_code, 403)

    def test_el_operario_si_abre_su_propia_orden(self):
        mia = self.orden_asignada(self.operario)
        self.client.force_authenticate(self.operario)

        self.assertEqual(self.client.get(f"/api/ordenes/{mia.pk}").status_code, 200)

    def test_el_listado_general_solo_le_muestra_al_operario_sus_ordenes(self):
        mia = self.orden_asignada(self.operario)
        self.orden_asignada(self.otro_operario)
        self.client.force_authenticate(self.operario)

        response = self.client.get("/api/ordenes")

        self.assertEqual([o["id"] for o in response.json()], [mia.pk])

    def test_recepcion_y_admin_siguen_viendo_todas_las_ordenes(self):
        self.orden_asignada(self.operario)
        self.orden_asignada(self.otro_operario)
        admin = User.objects.create_user(username="jefe", password="x", rol=User.Rol.ADMINISTRADOR)

        for usuario in (self.recepcionista, admin):
            with self.subTest(usuario=usuario.username):
                self.client.force_authenticate(usuario)
                ordenes = self.client.get("/api/ordenes").json()
                self.assertEqual(len(ordenes), 2)
                self.assertEqual(
                    self.client.get(f"/api/ordenes/{ordenes[0]['id']}").status_code, 200
                )

    def test_la_bandeja_es_solo_para_operarios(self):
        admin = User.objects.create_user(username="jefe", password="x", rol=User.Rol.ADMINISTRADOR)

        self.assertEqual(self.bandeja(self.recepcionista).status_code, 403)
        self.assertEqual(self.bandeja(admin).status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get("/api/ordenes/bandeja").status_code, (401, 403))

    def test_la_bandeja_no_admite_escritura(self):
        self.client.force_authenticate(self.operario)

        self.assertEqual(self.client.post("/api/ordenes/bandeja", {}).status_code, 405)

    def test_las_consultas_no_crecen_con_el_numero_de_ordenes(self):
        self.orden_asignada(self.operario)
        with self.assertNumQueries(7):
            self.bandeja()

        for _ in range(3):
            self.orden_asignada(self.operario)
        with self.assertNumQueries(7):
            self.assertEqual(len(self.bandeja().json()), 4)


class MaterialYServiciosPorPrendaTests(CatalogoDePruebaMixin, APITestCase):
    def setUp(self):
        self.crear_catalogo()
        self.tinte = Servicio.objects.create(nombre="Tintura")
        self.tarifa(self.camisa, self.tinte, "1500")
        self.client.force_authenticate(self.recepcionista)

    def test_la_orden_exige_material_en_cada_prenda(self):
        sin_material = self.prenda(self.planchado)
        del sin_material["material"]

        response = self.registrar(sin_material)

        self.assertEqual(response.status_code, 400)
        self.assertIn("material", str(response.json()))
        self.assertFalse(Orden.objects.exists())

    def test_agregar_prenda_tambien_exige_material(self):
        orden = self.registrar(self.prenda(self.planchado)).json()
        sin_material = self.prenda(self.planchado)
        del sin_material["material"]

        response = self.client.post(f"/api/ordenes/{orden['id']}/prendas", sin_material, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("material", response.json())

    def test_rechaza_un_material_inexistente(self):
        response = self.registrar(self.prenda(self.planchado, material=9999))

        self.assertEqual(response.status_code, 400)

    def test_el_material_se_guarda_y_se_muestra_en_orden_bandeja_y_entrega(self):
        datos = self.registrar(self.prenda(self.planchado, material=self.jean.pk)).json()

        prenda = datos["detalle_prendas"][0]
        self.assertEqual((prenda["material"], prenda["material_nombre"]), (self.jean.pk, "Jean"))
        self.assertEqual(Prenda.objects.get().material, self.jean)

        operario = User.objects.create_user(username="op", password="x", rol=User.Rol.OPERARIO)
        Orden.objects.filter(pk=datos["id"]).update(operario=operario, estado=Orden.Estado.RECIBIDA)
        self.client.force_authenticate(operario)
        bandeja = self.client.get("/api/ordenes/bandeja").json()
        self.assertEqual(bandeja[0]["prendas"][0]["material_nombre"], "Jean")

    def test_una_prenda_anterior_sin_material_se_serializa_sin_material(self):
        datos = self.registrar(self.prenda(self.planchado)).json()
        Prenda.objects.update(material=None)

        prenda = self.client.get(f"/api/ordenes/{datos['id']}").json()["detalle_prendas"][0]

        self.assertIsNone(prenda["material"])
        self.assertIsNone(prenda["material_nombre"])

    def ejemplo_de_tres_camisas_y_dos_pantalones(self):
        self.tarifa(self.pantalon, self.planchado, "2500")
        self.tarifa(self.pantalon, self.lavado, "0", "3000")
        self.tarifa(self.pantalon, self.tinte, "1000")
        return self.registrar(
            self.prenda(self.lavado, peso="2"),
            self.prenda(self.lavado, self.planchado, peso="1", material=self.jean.pk),
            self.prenda(self.tinte, peso="1"),
            self.prenda(self.planchado, tipo=self.pantalon, peso="1"),
            self.prenda(self.planchado, self.lavado, self.tinte, tipo=self.pantalon, peso="1.5"),
        )

    def test_servicios_distintos_por_prenda_suman_el_subtotal_y_congelan_cada_valor(self):
        response = self.ejemplo_de_tres_camisas_y_dos_pantalones()

        self.assertEqual(response.status_code, 201, response.json())
        # 8000 + (4000 + 6000) + 1500 + 2500 + (2500 + 4500 + 1000)
        self.assertEqual(Decimal(response.json()["subtotal"]), Decimal("30000"))
        lineas = [
            [(s["servicio_nombre"], Decimal(s["valor_aplicado"])) for s in p["servicios"]]
            for p in response.json()["detalle_prendas"]
        ]
        self.assertEqual(
            lineas,
            [
                [("Lavado", Decimal("8000"))],
                [("Lavado", Decimal("4000")), ("Planchado", Decimal("6000"))],
                [("Tintura", Decimal("1500"))],
                [("Planchado", Decimal("2500"))],
                [
                    ("Planchado", Decimal("2500")),
                    ("Lavado", Decimal("4500")),
                    ("Tintura", Decimal("1000")),
                ],
            ],
        )
        self.assertEqual(OrdenServicio.objects.count(), 8)

    def test_el_valor_cobrado_no_cambia_si_la_tarifa_sube_despues(self):
        datos = self.ejemplo_de_tres_camisas_y_dos_pantalones().json()
        Tarifa.objects.update(valor_base=Decimal("99999"), precio_por_kilo=Decimal("99999"))
        self.facil.factor = Decimal("5")
        self.facil.save()

        orden = self.client.get(f"/api/ordenes/{datos['id']}").json()

        self.assertEqual(Decimal(orden["detalle_prendas"][0]["servicios"][0]["valor_aplicado"]), Decimal("8000"))
        self.assertEqual(Decimal(orden["subtotal"]), Decimal("30000"))

    def test_el_descuento_se_aplica_sobre_el_total_de_las_prendas(self):
        ReglaDescuento.objects.create(
            nombre="Diez",
            tipo=ReglaDescuento.Tipo.PORCENTAJE,
            valor=Decimal("10"),
            vigente_desde=date(2020, 1, 1),
        )

        datos = self.ejemplo_de_tres_camisas_y_dos_pantalones().json()

        self.assertEqual(Decimal(datos["subtotal"]), Decimal("30000"))
        self.assertEqual(Decimal(datos["descuento"]), Decimal("3000"))
        self.assertEqual(Decimal(datos["valor_total"]), Decimal("27000"))


class PrecioPorServicioTests(CatalogoDePruebaMixin, APITestCase):
    """Valor base + peso x precio por kilo, por el factor del nivel del material."""

    def setUp(self):
        self.crear_catalogo()
        Tarifa.objects.all().delete()
        self.tarifa(None, self.planchado, "5000", "8000")
        self.lino = Material.objects.create(nombre="Lino", nivel_dificultad=self.dificil)
        self.client.force_authenticate(self.recepcionista)

    def cobrar(self, peso, material=None, tipo=None, servicio=None):
        response = self.registrar(
            self.prenda(servicio or self.planchado, peso=peso, material=(material or self.jean).pk, tipo=tipo)
        )
        self.assertEqual(response.status_code, 201, response.json())
        return Decimal(response.json()["valor_total"])

    def test_jean_de_07_kg_nivel_facil_cuesta_10600(self):
        self.assertEqual(self.cobrar("0.7"), Decimal("10600"))

    def test_lino_de_02_kg_nivel_dificil_se_redondea_de_10560_a_10600(self):
        self.assertEqual(self.cobrar("0.2", material=self.lino), Decimal("10600"))

    def test_redondea_a_la_centena_mas_cercana(self):
        self.assertEqual(redondear_a_100(Decimal("10540")), Decimal("10500"))
        self.assertEqual(redondear_a_100(Decimal("10560")), Decimal("10600"))
        self.assertEqual(redondear_a_100(Decimal("10550")), Decimal("10600"))
        self.assertEqual(redondear_a_100(Decimal("49")), Decimal("0"))

    def test_el_cobro_de_la_linea_es_el_precio_de_una_prenda_por_la_cantidad(self):
        response = self.registrar(self.prenda(self.planchado, peso="0.7", cantidad=3))

        self.assertEqual(Decimal(response.json()["valor_total"]), Decimal("31800"))

    def test_congela_el_desglose_para_auditar_el_calculo(self):
        datos = self.registrar(self.prenda(self.planchado, peso="0.2", material=self.lino.pk)).json()

        linea = OrdenServicio.objects.get()
        self.assertEqual(
            (linea.valor_base, linea.precio_por_kilo, linea.peso, linea.nivel_dificultad, linea.factor, linea.es_excepcion),
            (Decimal("5000"), Decimal("8000"), Decimal("0.20"), "Dificil", Decimal("1.60"), False),
        )
        self.assertEqual(linea.valor_aplicado, Decimal("10600"))
        servicio = datos["detalle_prendas"][0]["servicios"][0]
        self.assertEqual(servicio["nivel_dificultad"], "Dificil")
        self.assertEqual(servicio["es_excepcion"], False)

    def test_cambiar_el_factor_y_el_precio_por_kilo_solo_afecta_a_las_ordenes_nuevas(self):
        antes = self.registrar(self.prenda(self.planchado, peso="0.7")).json()["id"]
        admin = User.objects.create_user(username="admin", password="x", rol=User.Rol.ADMINISTRADOR)
        self.client.force_authenticate(admin)
        self.client.patch(f"/api/catalogo/niveles-dificultad/{self.facil.pk}", {"factor": "1.10"}, format="json")
        general = Tarifa.objects.get(tipo_prenda__isnull=True)
        self.client.patch(f"/api/catalogo/tarifas/{general.pk}", {"precio_por_kilo": "9000"}, format="json")
        self.client.force_authenticate(self.recepcionista)

        despues = self.registrar(self.prenda(self.planchado, peso="0.7")).json()

        # (5000 + 0,7 x 9000) x 1,1 = 12430 -> 12400; la anterior conserva 10600.
        self.assertEqual(Decimal(despues["valor_total"]), Decimal("12400"))
        self.assertEqual(Orden.objects.get(pk=antes).valor_total, Decimal("10600"))

    def test_la_excepcion_por_tipo_tiene_prioridad_sobre_la_general(self):
        self.tarifa(self.pantalon, self.planchado, "1000", "0")

        self.assertEqual(self.cobrar("5", tipo=self.pantalon), Decimal("1000"))
        self.assertEqual(self.cobrar("5", tipo=self.camisa), Decimal("45000"))
        linea = OrdenServicio.objects.filter(prenda__tipo_prenda=self.pantalon).get()
        self.assertTrue(linea.es_excepcion)

    def test_un_tipo_sin_excepcion_usa_la_general_aunque_sea_nuevo(self):
        cobija = TipoPrenda.objects.create(nombre="Cobija")

        self.assertEqual(self.cobrar("1", tipo=cobija), Decimal("13000"))

    def test_una_tarifa_vencida_no_se_usa(self):
        Tarifa.objects.all().delete()
        self.tarifa(None, self.planchado, "5000", "8000", vigente_hasta=date(2021, 1, 1))

        response = self.registrar(self.prenda(self.planchado, peso="1"))

        self.assertEqual(response.status_code, 400)
        self.assertIn("No hay tarifa vigente", str(response.json()))
        self.assertFalse(Orden.objects.exists())

    def test_una_tarifa_que_empieza_manana_no_se_usa_hoy(self):
        Tarifa.objects.all().delete()
        self.tarifa(None, self.planchado, "5000", "8000", vigente_desde=date(2999, 1, 1))

        self.assertEqual(self.registrar(self.prenda(self.planchado, peso="1")).status_code, 400)

    def test_el_descuento_y_el_abono_se_calculan_sobre_el_total_redondeado(self):
        ReglaDescuento.objects.create(
            nombre="Diez", tipo=ReglaDescuento.Tipo.PORCENTAJE, valor=Decimal("10"), vigente_desde=date(2020, 1, 1)
        )

        datos = self.registrar(self.prenda(self.planchado, peso="0.7", material=self.lino.pk)).json()

        # (5000 + 5600) x 1,6 = 16960 -> 17000; 10 % = 1700; total 15300; abono 4590.
        self.assertEqual(Decimal(datos["subtotal"]), Decimal("17000"))
        self.assertEqual(Decimal(datos["descuento"]), Decimal("1700"))
        self.assertEqual(Decimal(datos["valor_total"]), Decimal("15300"))
        self.assertEqual(Decimal(datos["abono_requerido"]), Decimal("4590"))

    def test_una_prenda_anterior_sin_material_usa_factor_uno(self):
        orden = self.registrar(self.prenda(self.planchado, peso="1")).json()
        Prenda.objects.update(material=None)

        response = self.client.post(
            f"/api/ordenes/{orden['id']}/prendas/{Prenda.objects.get().pk}/servicios",
            {"servicio": self.lavado.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 400)  # lavado no tiene tarifa
        self.tarifa(None, self.lavado, "0", "1000")
        response = self.client.post(
            f"/api/ordenes/{orden['id']}/prendas/{Prenda.objects.get().pk}/servicios",
            {"servicio": self.lavado.pk},
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.json())
        linea = OrdenServicio.objects.get(tarifa__servicio=self.lavado)
        self.assertEqual((linea.factor, linea.nivel_dificultad, linea.valor_aplicado), (Decimal("1"), "", Decimal("1000")))

    def test_agregar_un_servicio_a_una_prenda_sin_peso_se_rechaza(self):
        orden = self.registrar(self.prenda(self.planchado, peso="1")).json()
        Prenda.objects.update(peso=None)
        self.tarifa(None, self.lavado, "0", "1000")

        response = self.client.post(
            f"/api/ordenes/{orden['id']}/prendas/{Prenda.objects.get().pk}/servicios",
            {"servicio": self.lavado.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("peso", str(response.json()))

    def test_agregar_prenda_exige_peso_y_cotiza_con_el_material(self):
        orden = self.registrar(self.prenda(self.planchado, peso="1")).json()
        sin_peso = self.prenda(self.planchado)
        del sin_peso["peso"]

        rechazada = self.client.post(f"/api/ordenes/{orden['id']}/prendas", sin_peso, format="json")
        aceptada = self.client.post(
            f"/api/ordenes/{orden['id']}/prendas",
            self.prenda(self.planchado, peso="0.2", material=self.lino.pk),
            format="json",
        )

        self.assertEqual(rechazada.status_code, 400)
        self.assertEqual(aceptada.status_code, 201)
        # 13000 de la primera + 10600 de la segunda.
        self.assertEqual(Decimal(aceptada.json()["valor_total"]), Decimal("23600"))

    def test_operario_y_recepcion_no_editan_tarifas_ni_niveles(self):
        general = Tarifa.objects.get()
        for rol in (User.Rol.RECEPCIONISTA, User.Rol.OPERARIO):
            self.client.force_authenticate(User.objects.create_user(username=f"u-{rol}", password="x", rol=rol))
            for ruta, datos in (
                (f"tarifas/{general.pk}", {"precio_por_kilo": "1"}),
                (f"niveles-dificultad/{self.facil.pk}", {"factor": "9"}),
            ):
                with self.subTest(rol=rol, ruta=ruta):
                    self.assertEqual(self.client.patch(f"/api/catalogo/{ruta}", datos, format="json").status_code, 403)
        general.refresh_from_db()
        self.assertEqual(general.precio_por_kilo, Decimal("8000"))


class HistorialClienteApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="x", rol=User.Rol.ADMINISTRADOR
        )
        self.antigua = crear_orden(codigo="SW-ANTIGUA")
        self.cancelada = crear_orden(codigo="SW-CANCELA")
        self.reciente = crear_orden(codigo="SW-RECIENT")
        self.cliente = self.antigua.cliente
        for dia, orden, estado, total in (
            (1, self.antigua, Orden.Estado.EN_ESPERA, "20000"),
            (2, self.cancelada, Orden.Estado.CANCELADA, "50000"),
            (3, self.reciente, Orden.Estado.RECIBIDA, "35000"),
        ):
            Orden.objects.filter(pk=orden.pk).update(
                creado_en=datetime(2026, 5, dia, tzinfo=dt_timezone.utc), estado=estado, valor_total=Decimal(total)
            )
        otro = Cliente.objects.create(documento="555", nombre_completo="Otro", telefono="300")
        Orden.objects.create(cliente=otro, recepcionista=self.antigua.recepcionista)
        self.url = f"/api/clientes/{self.cliente.pk}/ordenes"

    def test_lista_todas_las_ordenes_del_cliente_de_la_mas_reciente_a_la_mas_antigua(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        datos = response.json()
        self.assertEqual(
            [(o["codigo"], o["estado"], o["valor_total"]) for o in datos["ordenes"]],
            [
                ("SW-RECIENT", "Recibida", "35000.00"),
                ("SW-CANCELA", "Cancelada", "50000.00"),
                ("SW-ANTIGUA", "En espera", "20000.00"),
            ],
        )
        self.assertTrue(all(o["creado_en"] and o["estado_pago"] for o in datos["ordenes"]))
        self.assertEqual(datos["cliente"], {"id": self.cliente.pk, "nombre_completo": "Ana Gomez"})

    def test_el_total_comprado_excluye_las_canceladas_y_el_conteo_las_incluye(self):
        self.client.force_login(self.admin)
        datos = self.client.get(self.url).json()

        self.assertEqual(datos["numero_ordenes"], 3)
        self.assertEqual(datos["total_comprado"], "55000.00")

    def test_un_cliente_sin_ordenes_recibe_lista_vacia_y_total_cero(self):
        nuevo = Cliente.objects.create(documento="777", nombre_completo="Nuevo", telefono="301")
        self.client.force_login(self.admin)
        datos = self.client.get(f"/api/clientes/{nuevo.pk}/ordenes").json()

        self.assertEqual(
            (datos["ordenes"], datos["numero_ordenes"], datos["total_comprado"]), ([], 0, "0.00")
        )

    def test_un_cliente_inexistente_responde_404(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get("/api/clientes/9999/ordenes").status_code, 404)

    def test_la_recepcionista_consulta_y_el_operario_recibe_403(self):
        self.client.force_login(self.antigua.recepcionista)
        self.assertEqual(self.client.get(self.url).status_code, 200)

        operario = User.objects.create_user(username="op", password="x", rol=User.Rol.OPERARIO)
        self.client.force_login(operario)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_la_consulta_no_permite_escribir(self):
        self.client.force_login(self.admin)
        for metodo in ("post", "put", "patch", "delete"):
            response = getattr(self.client, metodo)(self.url, {}, format="json")
            self.assertEqual(response.status_code, 405, metodo)


# 2026-05-10 03:00 UTC sigue siendo el 9 de mayo (22:00) en Bogota.
AHORA = datetime(2026, 5, 10, 3, 0, tzinfo=dt_timezone.utc)


@mock.patch("django.utils.timezone.now", return_value=AHORA)
class AlertasVencimientoApiTests(APITestCase):
    url = "/api/ordenes/alertas"

    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="x", rol=User.Rol.ADMINISTRADOR
        )
        self.operario = User.objects.create_user(
            username="op", password="x", rol=User.Rol.OPERARIO
        )

    def orden(self, codigo, estado, fecha, operario=None):
        orden = crear_orden(codigo=codigo)
        Orden.objects.filter(pk=orden.pk).update(
            estado=estado, fecha_estimada_entrega=fecha, operario=operario
        )
        return orden

    def alertas(self, usuario):
        self.client.force_login(usuario)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return [(a["codigo"], a["tipo"], a["dias"]) for a in response.json()]

    def test_prioriza_las_mas_retrasadas_y_luego_las_mas_proximas(self, _now):
        self.orden("SW-PROX2", Orden.Estado.CLASIFICADA, date(2026, 5, 11))
        self.orden("SW-RETR1", Orden.Estado.EN_PROCESO, date(2026, 5, 8))
        self.orden("SW-HOY", Orden.Estado.LISTA, date(2026, 5, 9))
        self.orden("SW-RETR3", Orden.Estado.RECIBIDA, date(2026, 5, 6))
        self.orden("SW-LEJOS", Orden.Estado.CONTROL_CALIDAD, date(2026, 5, 12))

        self.assertEqual(
            self.alertas(self.admin),
            [
                ("SW-RETR3", "retrasada", 3),
                ("SW-RETR1", "retrasada", 1),
                ("SW-HOY", "proxima", 0),
                ("SW-PROX2", "proxima", 2),
            ],
        )

    def test_hoy_es_la_fecha_de_bogota_y_no_la_de_utc(self, _now):
        self.orden("SW-HOY", Orden.Estado.EN_PROCESO, date(2026, 5, 9))

        self.assertEqual(self.alertas(self.admin), [("SW-HOY", "proxima", 0)])

    def test_excluye_en_espera_canceladas_y_entregadas(self, _now):
        vencida = date(2026, 5, 1)
        crear_orden(codigo="SW-ESPERA")
        self.orden("SW-CANCEL", Orden.Estado.CANCELADA, vencida)
        self.orden("SW-ENTREG", Orden.Estado.ENTREGADA, vencida)

        self.assertEqual(self.alertas(self.admin), [])

    def test_una_orden_con_novedad_sigue_alertando(self, _now):
        self.orden("SW-NOVEDAD", Orden.Estado.CON_NOVEDAD, date(2026, 5, 8))

        self.assertEqual(self.alertas(self.admin), [("SW-NOVEDAD", "retrasada", 1)])

    def test_la_recepcionista_ve_todas_y_el_operario_solo_las_suyas(self, _now):
        self.orden("SW-MIA", Orden.Estado.EN_PROCESO, date(2026, 5, 8), self.operario)
        self.orden("SW-OTRA", Orden.Estado.EN_PROCESO, date(2026, 5, 8))

        recepcionista = User.objects.get(username="recepcion")
        self.assertEqual(len(self.alertas(recepcionista)), 2)
        self.assertEqual(self.alertas(self.operario), [("SW-MIA", "retrasada", 1)])

    def test_si_la_base_falla_responde_500_registra_el_error_y_no_modifica_nada(self, _now):
        self.orden("SW-RETR", Orden.Estado.EN_PROCESO, date(2026, 5, 8))
        antes = list(Orden.objects.values_list("codigo", "estado", "fecha_estimada_entrega"))
        self.client.force_login(self.admin)
        self.client.raise_request_exception = False

        with mock.patch.object(
            Orden.objects, "filter", side_effect=OperationalError("sin conexion")
        ), self.assertLogs("django.request", level="ERROR") as logs:
            response = self.client.get(self.url)

        self.assertEqual(response.status_code, 500)
        self.assertIn("sin conexion", "\n".join(logs.output))
        self.assertEqual(
            list(Orden.objects.values_list("codigo", "estado", "fecha_estimada_entrega")), antes
        )


def data_url(datos, tipo="image/jpeg"):
    return f"data:{tipo};base64,{base64.b64encode(datos).decode()}"


JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


class OrdenEnProcesoMixin(CatalogoDePruebaMixin):
    def setUp(self):
        self.crear_catalogo()
        self.admin = User.objects.create_user(
            username="admin", password="x", rol=User.Rol.ADMINISTRADOR
        )
        self.operario = User.objects.create_user(
            username="op", password="x", rol=User.Rol.OPERARIO
        )
        self.otro_operario = User.objects.create_user(
            username="op2", password="x", rol=User.Rol.OPERARIO
        )
        self.client.force_authenticate(self.recepcionista)
        self.registrar(self.prenda(self.planchado), self.prenda(self.planchado))
        self.orden = Orden.objects.get()
        self.camisa_1, self.camisa_2 = self.orden.prendas.all()
        Orden.objects.filter(pk=self.orden.pk).update(
            estado=Orden.Estado.EN_PROCESO, operario=self.operario, abono_alcanzado_en=date(2026, 5, 1)
        )
        self.url = f"/api/ordenes/{self.orden.pk}/novedades"

    def registrar_novedad(self, usuario=None, **datos):
        self.client.force_authenticate(usuario or self.operario)
        cuerpo = {"prenda": self.camisa_1.pk, "descripcion": "Mancha de tinta", "foto": data_url(JPEG)}
        cuerpo.update(datos)
        return self.client.post(self.url, {k: v for k, v in cuerpo.items() if v is not ...}, format="json")



class NovedadApiTests(OrdenEnProcesoMixin, APITestCase):
    def assertSinCambios(self, estado=Orden.Estado.EN_PROCESO):
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, estado)
        self.assertFalse(Novedad.objects.exists())
        self.assertFalse(FotoNovedad.objects.exists())
        self.assertFalse(self.orden.historial.filter(tipo_evento=Evento.NOVEDAD).exists())

    def test_el_operario_registra_la_novedad_con_foto_y_la_orden_queda_con_novedad(self):
        response = self.registrar_novedad()

        self.assertEqual(response.status_code, 201, response.json())
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.CON_NOVEDAD)
        novedad = Novedad.objects.get()
        self.assertEqual(
            (novedad.prenda, novedad.descripcion, novedad.origen, novedad.estado_anterior),
            (self.camisa_1, "Mancha de tinta", Novedad.Origen.PROCESO, Orden.Estado.EN_PROCESO),
        )
        self.assertEqual((novedad.foto.tipo, novedad.foto.tamano), ("image/jpeg", len(JPEG)))
        self.assertEqual(response.json()["foto_url"], f"/api/novedades/{novedad.pk}/foto")
        evento = self.orden.historial.last()
        self.assertEqual((evento.tipo_evento, evento.usuario), (Evento.NOVEDAD, self.operario))
        self.assertIn(str(self.camisa_1), evento.detalle)
        self.assertIn("Mancha de tinta (con foto)", evento.detalle)

    def test_el_administrador_registra_desde_control_de_calidad_con_base64_sin_prefijo(self):
        Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.CONTROL_CALIDAD)

        response = self.registrar_novedad(self.admin, foto=base64.b64encode(PNG).decode())

        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(Novedad.objects.get().foto.tipo, "image/png")

    def test_sin_foto_durante_el_proceso_se_rechaza(self):
        for foto in (..., "", None):
            with self.subTest(foto=foto):
                response = self.registrar_novedad(foto=foto)
                self.assertEqual(response.status_code, 400)
                self.assertIn("La fotografia es obligatoria.", response.json()["foto"])
        self.assertSinCambios()

    def test_sin_descripcion_se_rechaza(self):
        response = self.registrar_novedad(descripcion="   ")

        self.assertEqual(response.status_code, 400)
        self.assertIn("La descripcion es obligatoria.", response.json()["descripcion"])
        self.assertSinCambios()

    def test_un_archivo_que_no_es_imagen_o_supera_500_kb_se_rechaza(self):
        casos = {
            data_url(b"%PDF-1.4 no soy imagen", "image/jpeg"): "no es una imagen",
            "esto no es base64!": "base64",
            data_url(b"\xff\xd8\xff" + b"0" * (500 * 1024)): "maximo es 500 KB",
        }
        for foto, motivo in casos.items():
            with self.subTest(motivo=motivo):
                response = self.registrar_novedad(foto=foto)
                self.assertEqual(response.status_code, 400)
                self.assertIn(motivo, response.json()["foto"][0])
        self.assertSinCambios()

    def test_una_foto_de_500_kb_exactos_se_acepta(self):
        foto = data_url(b"\xff\xd8\xff" + b"0" * (500 * 1024 - 3))

        self.assertEqual(self.registrar_novedad(foto=foto).status_code, 201)

    def test_el_operario_no_asignado_y_la_recepcionista_no_pueden_registrarla(self):
        for usuario in (self.otro_operario, self.recepcionista):
            with self.subTest(usuario=usuario.username):
                self.assertEqual(self.registrar_novedad(usuario).status_code, 403)
        self.assertSinCambios()

    def test_solo_se_registra_en_proceso_o_control_de_calidad(self):
        for estado in (Orden.Estado.CLASIFICADA, Orden.Estado.LISTA, Orden.Estado.CON_NOVEDAD):
            Orden.objects.filter(pk=self.orden.pk).update(estado=estado)
            with self.subTest(estado=estado):
                self.assertEqual(self.registrar_novedad().status_code, 400)
        self.assertFalse(Novedad.objects.exists())

    def test_una_prenda_de_otra_orden_se_rechaza(self):
        response = self.registrar_novedad(prenda=999)

        self.assertEqual(response.status_code, 400)
        self.assertSinCambios()

    def test_una_orden_con_novedad_no_avanza_de_estado(self):
        self.registrar_novedad()

        for usuario in (self.operario, self.admin):
            self.client.force_authenticate(usuario)
            response = self.client.post(
                f"/api/ordenes/{self.orden.pk}/estado",
                {"estado": Orden.Estado.CONTROL_CALIDAD},
                format="json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertIn("novedad pendiente", str(response.json()))
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.CON_NOVEDAD)

    def test_una_orden_con_novedad_no_se_entrega_ni_se_reasigna(self):
        self.registrar_novedad()
        self.client.force_authenticate(self.admin)

        entrega = self.client.post(
            f"/api/ordenes/{self.orden.pk}/entrega",
            {"prendas": [{"prenda": p.pk, "coincide": True} for p in (self.camisa_1, self.camisa_2)]},
            format="json",
        )
        asignacion = self.client.post(
            f"/api/ordenes/{self.orden.pk}/asignacion",
            {"operario": self.otro_operario.pk},
            format="json",
        )

        self.assertEqual((entrega.status_code, asignacion.status_code), (400, 400))
        self.orden.refresh_from_db()
        self.assertEqual(
            (self.orden.estado, self.orden.operario), (Orden.Estado.CON_NOVEDAD, self.operario)
        )

    def test_si_la_base_falla_no_queda_novedad_ni_foto_ni_cambio_de_estado(self):
        with mock.patch(
            "ordenes.serializers.registrar_evento", side_effect=OperationalError("sin conexion")
        ), self.assertLogs("ordenes.historial", level="ERROR") as logs:
            response = self.registrar_novedad()

        self.assertEqual(response.status_code, 503)
        self.assertIn("sin conexion", "\n".join(logs.output))
        self.assertSinCambios()

    def test_la_foto_la_ven_el_administrador_la_recepcionista_y_el_operario_asignado(self):
        self.registrar_novedad()
        url = f"/api/novedades/{Novedad.objects.get().pk}/foto"

        for usuario in (self.admin, self.recepcionista, self.operario):
            with self.subTest(usuario=usuario.username):
                self.client.force_authenticate(usuario)
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "image/jpeg")
                self.assertEqual(response.content, JPEG)

        self.client.force_authenticate(self.otro_operario)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_el_listado_de_novedades_no_incluye_el_contenido_de_la_foto(self):
        self.registrar_novedad()
        self.client.force_authenticate(self.recepcionista)

        novedades = self.client.get(self.url).json()

        self.assertEqual(len(novedades), 1)
        self.assertNotIn("contenido", novedades[0])
        self.assertEqual(novedades[0]["usuario_nombre"], "op")
        self.client.force_authenticate(self.otro_operario)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_en_la_entrega_cada_prenda_que_no_coincide_es_una_novedad_y_hay_un_solo_evento(self):
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/pagos",
            {"monto": "12000", "metodo": "efectivo"},
            format="json",
        )
        Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.LISTA)
        eventos_antes = self.orden.historial.count()
        self.client.force_authenticate(self.recepcionista)

        response = self.client.post(
            f"/api/ordenes/{self.orden.pk}/entrega",
            {
                "prendas": [
                    {"prenda": self.camisa_1.pk, "coincide": False, "observacion": "Falta un boton"},
                    {
                        "prenda": self.camisa_2.pk,
                        "coincide": False,
                        "observacion": "Otro color",
                        "foto": data_url(JPEG),
                    },
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.json())
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.CON_NOVEDAD)
        self.assertIsNone(self.orden.fecha_entrega)
        novedades = list(Novedad.objects.order_by("id"))
        self.assertEqual(
            [(n.prenda, n.origen, n.estado_anterior, hasattr(n, "foto")) for n in novedades],
            [
                (self.camisa_1, Novedad.Origen.ENTREGA, Orden.Estado.LISTA, False),
                (self.camisa_2, Novedad.Origen.ENTREGA, Orden.Estado.LISTA, True),
            ],
        )
        self.assertEqual(self.orden.historial.count(), eventos_antes + 1)
        evento = self.orden.historial.last()
        self.assertEqual((evento.tipo_evento, evento.usuario), (Evento.NOVEDAD, self.recepcionista))
        self.assertIn("detectada en la entrega", evento.detalle)
        self.assertIn("Falta un boton (sin foto)", evento.detalle)
        self.assertIn("Otro color (con foto)", evento.detalle)


class DecisionNovedadApiTests(OrdenEnProcesoMixin, APITestCase):
    url_lista = "/api/ordenes/novedades"

    def decidir(self, decision, observacion="Hable con Ana por telefono", usuario=None):
        self.client.force_authenticate(usuario or self.recepcionista)
        return self.client.post(
            f"/api/ordenes/{self.orden.pk}/decision",
            {"decision": decision, "observacion": observacion},
            format="json",
        )

    def novedad_en_la_entrega(self):
        self.client.force_authenticate(self.recepcionista)
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/pagos", {"monto": "12000", "metodo": "efectivo"}, format="json"
        )
        Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.LISTA)
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/entrega",
            {
                "prendas": [
                    {"prenda": self.camisa_1.pk, "coincide": False, "observacion": "Falta un boton"},
                    {"prenda": self.camisa_2.pk, "coincide": True},
                ]
            },
            format="json",
        )

    def ultimo_evento(self):
        return self.orden.historial.last()

    def test_la_lista_muestra_cada_orden_con_novedad_y_sus_novedades_pendientes(self):
        self.registrar_novedad()
        self.client.force_authenticate(self.admin)

        ordenes = self.client.get(self.url_lista).json()

        self.assertEqual([o["codigo"] for o in ordenes], [self.orden.codigo])
        novedad = ordenes[0]["novedades"][0]
        self.assertEqual(ordenes[0]["operario_nombre"], "op")
        self.assertEqual(
            (novedad["prenda"], novedad["descripcion"], novedad["usuario_nombre"], novedad["origen"]),
            (self.camisa_1.pk, "Mancha de tinta", "op", Novedad.Origen.PROCESO),
        )
        self.assertTrue(novedad["foto_url"] and novedad["creado_en"])

    def test_la_lista_muestra_la_novedad_de_la_entrega_sin_foto_y_omite_las_resueltas(self):
        self.novedad_en_la_entrega()
        self.client.force_authenticate(self.recepcionista)

        novedad = self.client.get(self.url_lista).json()[0]["novedades"][0]
        self.assertEqual((novedad["origen"], novedad["foto_url"]), (Novedad.Origen.ENTREGA, None))

        self.decidir(Novedad.Decision.CONTINUAR)
        self.assertEqual(self.client.get(self.url_lista).json(), [])

    def test_continuar_igual_devuelve_la_orden_al_estado_de_origen(self):
        Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.CONTROL_CALIDAD)
        self.registrar_novedad()

        response = self.decidir(Novedad.Decision.CONTINUAR)

        self.assertEqual(response.status_code, 200, response.json())
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.CONTROL_CALIDAD)
        novedad = Novedad.objects.get()
        self.assertEqual(
            (novedad.decision, novedad.decidida_por, novedad.decision_observacion),
            (Novedad.Decision.CONTINUAR, self.recepcionista, "Hable con Ana por telefono"),
        )
        self.assertIsNotNone(novedad.decidida_en)
        evento = self.ultimo_evento()
        self.assertEqual(
            (evento.tipo_evento, evento.usuario), (Evento.DECISION_NOVEDAD, self.recepcionista)
        )
        self.assertIn("Continuar igual: Hable con Ana por telefono", evento.detalle)
        self.assertIn("→ Control de calidad", evento.detalle)

    def test_continuar_tras_una_novedad_de_la_entrega_permite_entregar(self):
        self.novedad_en_la_entrega()

        self.decidir(Novedad.Decision.CONTINUAR)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.LISTA)

        entrega = self.client.post(
            f"/api/ordenes/{self.orden.pk}/entrega",
            {"prendas": [{"prenda": p.pk, "coincide": True} for p in (self.camisa_1, self.camisa_2)]},
            format="json",
        )
        self.assertEqual(entrega.status_code, 200, entrega.json())
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.ENTREGADA)

    def test_reprocesar_pasa_a_en_proceso_y_cuenta_el_reproceso_sin_costo(self):
        self.novedad_en_la_entrega()
        self.orden.refresh_from_db()
        total = self.orden.valor_total

        response = self.decidir(Novedad.Decision.REPROCESAR, usuario=self.admin)

        self.assertEqual(response.status_code, 200, response.json())
        self.orden.refresh_from_db()
        self.assertEqual(
            (self.orden.estado, self.orden.numero_reprocesos, self.orden.valor_total),
            (Orden.Estado.EN_PROCESO, 1, total),
        )
        self.assertIn("Reprocesar", self.ultimo_evento().detalle)

    def test_no_continuar_deja_la_orden_con_novedad_y_admite_otra_decision(self):
        self.registrar_novedad()

        response = self.decidir(Novedad.Decision.NO_CONTINUAR, "Ana no quiere seguir")

        self.assertEqual(response.status_code, 200)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.CON_NOVEDAD)
        self.assertIn("La orden sigue Con novedad", self.ultimo_evento().detalle)
        lista = self.client.get(self.url_lista).json()
        self.assertEqual(lista[0]["novedades"][0]["decision"], Novedad.Decision.NO_CONTINUAR)

        self.decidir(Novedad.Decision.CONTINUAR, "Ana cambio de opinion")

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.EN_PROCESO)
        self.assertEqual(
            self.orden.historial.filter(tipo_evento=Evento.DECISION_NOVEDAD).count(), 2
        )

    def test_sin_observacion_se_rechaza(self):
        self.registrar_novedad()

        response = self.decidir(Novedad.Decision.CONTINUAR, "  ")

        self.assertEqual(response.status_code, 400)
        self.assertIn("con quien se hablo", response.json()["observacion"][0])
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.CON_NOVEDAD)

    def test_el_operario_no_registra_la_decision_ni_ve_la_lista(self):
        self.registrar_novedad()

        self.assertEqual(self.decidir(Novedad.Decision.CONTINUAR, usuario=self.operario).status_code, 403)
        self.assertEqual(self.client.get(self.url_lista).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url_lista).status_code, 403)

    def test_sin_novedad_pendiente_se_rechaza(self):
        response = self.decidir(Novedad.Decision.CONTINUAR)

        self.assertEqual(response.status_code, 400)
        self.assertIn("no tiene una novedad pendiente", str(response.json()))
        self.assertFalse(self.orden.historial.filter(tipo_evento=Evento.DECISION_NOVEDAD).exists())

    def test_si_la_base_falla_no_cambia_nada(self):
        self.registrar_novedad()

        with mock.patch(
            "ordenes.serializers.registrar_evento", side_effect=OperationalError("sin conexion")
        ), self.assertLogs("ordenes.historial", level="ERROR") as logs:
            response = self.decidir(Novedad.Decision.REPROCESAR)

        self.assertEqual(response.status_code, 503)
        self.assertIn("sin conexion", "\n".join(logs.output))
        self.orden.refresh_from_db()
        self.assertEqual(
            (self.orden.estado, self.orden.numero_reprocesos), (Orden.Estado.CON_NOVEDAD, 0)
        )
        self.assertIsNone(Novedad.objects.get().decision)


class ClasificacionPorConsumoTests(CatalogoDePruebaMixin, APITestCase):
    def setUp(self):
        self.crear_catalogo()
        self.client.force_authenticate(self.recepcionista)
        # Una prenda de planchado: 6000.
        self.registrar(self.prenda(self.planchado))
        self.orden = Orden.objects.get()
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/pagos", {"monto": "6000", "metodo": "efectivo"}, format="json"
        )
        Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.LISTA)

    def ordenes_previas(self, estado, cantidad, valor="10000"):
        for _ in range(cantidad):
            orden = Orden.objects.create(cliente=self.cliente, recepcionista=self.recepcionista)
            Orden.objects.filter(pk=orden.pk).update(estado=estado, valor_total=Decimal(valor))

    def entregar(self, coincide=True, **extra):
        prenda = {"prenda": self.orden.prendas.get().pk, "coincide": coincide, **extra}
        return self.client.post(
            f"/api/ordenes/{self.orden.pk}/entrega", {"prendas": [prenda]}, format="json"
        )

    def clasificacion(self):
        self.cliente.refresh_from_db()
        return self.cliente.clasificacion

    def test_la_tercera_orden_cerrada_vuelve_frecuente_al_cliente_y_queda_en_el_historial(self):
        self.ordenes_previas(Orden.Estado.ENTREGADA, 2)

        response = self.entregar()

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(self.clasificacion(), Cliente.Clasificacion.FRECUENTE)
        self.assertIn("Cliente: Ocasional → Frecuente", self.orden.historial.last().detalle)

    def test_las_ordenes_canceladas_o_sin_cerrar_no_cuentan(self):
        self.ordenes_previas(Orden.Estado.CANCELADA, 5, "200000")
        self.ordenes_previas(Orden.Estado.EN_PROCESO, 5, "200000")

        self.entregar()

        self.assertEqual(self.clasificacion(), Cliente.Clasificacion.OCASIONAL)
        self.assertNotIn("Cliente:", self.orden.historial.last().detalle)

    def test_diez_ordenes_cerradas_hacen_vip(self):
        self.ordenes_previas(Orden.Estado.ENTREGADA, 9, "1000")

        self.entregar()

        self.assertEqual(self.clasificacion(), Cliente.Clasificacion.VIP)

    def test_500_mil_consumidos_hacen_vip_aunque_haya_pocas_ordenes(self):
        self.ordenes_previas(Orden.Estado.ENTREGADA, 1, "494000")

        self.entregar()

        self.assertEqual(self.clasificacion(), Cliente.Clasificacion.VIP)
        self.assertIn("Cliente: Ocasional → VIP", self.orden.historial.last().detalle)

    def test_cuenta_el_valor_cobrado_con_descuento_y_no_el_subtotal(self):
        self.ordenes_previas(Orden.Estado.ENTREGADA, 1, "493000")
        Orden.objects.filter(valor_total=Decimal("493000")).update(
            subtotal=Decimal("600000"), descuento=Decimal("107000")
        )

        self.entregar()

        # Cobrado: 493000 + 6000 = 499000, mil por debajo del umbral VIP.
        self.assertEqual(self.clasificacion(), Cliente.Clasificacion.OCASIONAL)

    def test_la_clasificacion_nunca_baja(self):
        Cliente.objects.filter(pk=self.cliente.pk).update(clasificacion=Cliente.Clasificacion.VIP)

        self.entregar()

        self.assertEqual(self.clasificacion(), Cliente.Clasificacion.VIP)

    @override_settings(CLIENTE_FRECUENTE_MIN_ORDENES=1)
    def test_los_umbrales_se_configuran_en_settings(self):
        self.entregar()

        self.assertEqual(self.clasificacion(), Cliente.Clasificacion.FRECUENTE)

    def test_una_entrega_con_novedad_no_reclasifica(self):
        self.ordenes_previas(Orden.Estado.ENTREGADA, 2)

        self.entregar(coincide=False, observacion="Otro color")

        self.assertEqual(self.clasificacion(), Cliente.Clasificacion.OCASIONAL)

    def test_si_la_base_falla_no_se_entrega_ni_se_reclasifica(self):
        self.ordenes_previas(Orden.Estado.ENTREGADA, 2)

        with mock.patch(
            "ordenes.views.registrar_evento", side_effect=OperationalError("sin conexion")
        ), self.assertLogs("ordenes.historial", level="ERROR") as logs:
            response = self.entregar()

        self.assertEqual(response.status_code, 503)
        self.assertIn("sin conexion", "\n".join(logs.output))
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.LISTA)
        self.assertEqual(self.clasificacion(), Cliente.Clasificacion.OCASIONAL)


class AvisoOrdenListaTests(OrdenEnProcesoMixin, APITestCase):
    def setUp(self):
        super().setUp()
        Cliente.objects.filter(pk=self.cliente.pk).update(correo="ana@example.com")
        Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.CONTROL_CALIDAD)

    def cambiar_estado(self, estado):
        self.client.force_authenticate(self.operario)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                f"/api/ordenes/{self.orden.pk}/estado", {"estado": estado}, format="json"
            )

    def pagar(self, monto):
        self.client.force_authenticate(self.recepcionista)
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/pagos", {"monto": monto, "metodo": "efectivo"}, format="json"
        )

    def ultimo_aviso(self):
        return self.orden.historial.filter(tipo_evento=Evento.NOTIFICACION).last()

    def test_al_quedar_lista_se_avisa_al_cliente_con_el_saldo_pendiente(self):
        self.pagar("2000")

        response = self.cambiar_estado(Orden.Estado.LISTA)

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(len(mail.outbox), 1)
        aviso = mail.outbox[0]
        self.assertEqual(aviso.to, ["ana@example.com"])
        self.assertIn(self.orden.codigo, aviso.subject)
        self.assertIn("esta lista para recoger", aviso.body)
        self.assertIn("Saldo pendiente por pagar al recogerla: $10.000.", aviso.body)
        evento = self.ultimo_aviso()
        self.assertIsNone(evento.usuario)
        self.assertEqual(evento.detalle, "Aviso de orden lista enviado a ana@example.com.")

    def test_si_esta_pagada_el_aviso_no_menciona_saldo(self):
        self.pagar("12000")

        self.cambiar_estado(Orden.Estado.LISTA)

        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("Saldo", mail.outbox[0].body)

    def test_si_la_base_falla_no_cambia_el_estado_ni_se_avisa(self):
        with mock.patch(
            "ordenes.views.registrar_evento", side_effect=OperationalError("sin conexion")
        ), self.assertLogs("ordenes.historial", level="ERROR"):
            response = self.cambiar_estado(Orden.Estado.LISTA)

        self.assertEqual(response.status_code, 503)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.CONTROL_CALIDAD)
        self.assertEqual(mail.outbox, [])
        self.assertIsNone(self.ultimo_aviso())

    def test_si_falla_el_correo_la_orden_sigue_lista_y_queda_constancia(self):
        with mock.patch(
            "ordenes.avisos.send_mail", side_effect=RuntimeError("Resend caido")
        ), self.assertLogs("ordenes.avisos", level="ERROR") as logs:
            response = self.cambiar_estado(Orden.Estado.LISTA)

        self.assertEqual(response.status_code, 200)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.LISTA)
        self.assertIn("Resend caido", "\n".join(logs.output))
        self.assertIn("No se pudo enviar el aviso", self.ultimo_aviso().detalle)

    def test_sin_correo_no_se_envia_y_queda_la_indicacion_de_llamar(self):
        Cliente.objects.filter(pk=self.cliente.pk).update(correo="")

        self.cambiar_estado(Orden.Estado.LISTA)

        self.assertEqual(mail.outbox, [])
        self.assertIn("no tiene correo registrado", self.ultimo_aviso().detalle)

    def test_otros_cambios_de_estado_no_avisan(self):
        self.cambiar_estado(Orden.Estado.EN_PROCESO)

        self.assertEqual(mail.outbox, [])
        self.assertIsNone(self.ultimo_aviso())

    def test_continuar_tras_una_novedad_de_la_entrega_no_vuelve_a_avisar(self):
        self.pagar("12000")
        Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.LISTA)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                f"/api/ordenes/{self.orden.pk}/entrega",
                {
                    "prendas": [
                        {"prenda": self.camisa_1.pk, "coincide": False, "observacion": "Otro color"},
                        {"prenda": self.camisa_2.pk, "coincide": True},
                    ]
                },
                format="json",
            )
            self.client.post(
                f"/api/ordenes/{self.orden.pk}/decision",
                {"decision": "continuar", "observacion": "Ana acepta"},
                format="json",
            )

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.LISTA)
        self.assertEqual(mail.outbox, [])
        self.assertIsNone(self.ultimo_aviso())

    def test_tras_un_reproceso_avisa_de_nuevo_al_quedar_lista(self):
        self.cambiar_estado(Orden.Estado.EN_PROCESO)
        self.cambiar_estado(Orden.Estado.CONTROL_CALIDAD)
        self.cambiar_estado(Orden.Estado.LISTA)

        self.assertEqual(len(mail.outbox), 1)


class CancelarOrdenApiTests(CatalogoDePruebaMixin, APITestCase):
    def setUp(self):
        self.crear_catalogo()
        self.client.force_authenticate(self.recepcionista)
        # 16000 de valor total; abono minimo 4800.
        self.registrar(self.prenda(self.lavado, self.planchado))
        self.orden = Orden.objects.get()
        self.operario = User.objects.create_user(
            username="op1", password="x", rol=User.Rol.OPERARIO, first_name="Luis"
        )
        self.admin = User.objects.create_user(
            username="jefe", password="x", rol=User.Rol.ADMINISTRADOR
        )
        self.url = f"/api/ordenes/{self.orden.pk}/cancelacion"

    def cancelar(self, motivo="El cliente se retracto", usuario=None):
        self.client.force_authenticate(usuario or self.recepcionista)
        datos = {} if motivo is None else {"motivo": motivo}
        return self.client.post(self.url, datos, format="json")

    def pagar(self, monto):
        return self.client.post(
            f"/api/ordenes/{self.orden.pk}/pagos",
            {"monto": monto, "metodo": "efectivo"},
            format="json",
        )

    def fijar_estado(self, estado):
        Orden.objects.filter(pk=self.orden.pk).update(estado=estado)

    def eventos(self, tipo):
        return HistorialOrden.objects.filter(orden=self.orden, tipo_evento=tipo)

    def test_la_recepcionista_o_el_administrador_cancelan_antes_de_iniciar_el_servicio(self):
        for usuario in (self.recepcionista, self.admin):
            for estado in Orden.ESTADOS_CANCELABLES:
                with self.subTest(usuario=usuario.username, estado=estado):
                    self.fijar_estado(estado)

                    response = self.cancelar("Orden registrada con error", usuario)

                    self.assertEqual(response.status_code, 200, response.json())
                    self.assertEqual(response.json()["estado"], "Cancelada")
                    self.assertEqual(response.json()["motivo_cancelacion"], "Orden registrada con error")
                    evento = self.eventos(Evento.CANCELACION).last()
                    self.assertEqual(evento.usuario, usuario)
                    self.assertEqual(
                        evento.detalle, f"{estado} → Cancelada. Motivo: Orden registrada con error"
                    )
                    self.assertIsNotNone(evento.fecha)

    def test_sin_pagos_no_registra_devolucion(self):
        self.cancelar()

        self.assertFalse(self.eventos(Evento.DEVOLUCION).exists())

    def test_con_abono_registra_la_devolucion_sin_tocar_los_pagos(self):
        self.pagar("3000")
        self.pagar("2000")
        pagos = list(self.orden.pagos.values_list("id", "monto"))

        response = self.cancelar("El cliente se retracto")

        self.assertEqual(response.status_code, 200, response.json())
        evento = self.eventos(Evento.DEVOLUCION).get()
        self.assertEqual(evento.usuario, self.recepcionista)
        self.assertRegex(
            evento.detalle, r"^\$5000(\.00)? devueltos al cliente\. Motivo: El cliente se retracto$"
        )
        self.assertEqual(list(self.orden.pagos.values_list("id", "monto")), pagos)

    def test_rechaza_la_cancelacion_sin_motivo(self):
        previo = self.orden.historial.count()

        for motivo in (None, "", "   "):
            with self.subTest(motivo=motivo):
                response = self.cancelar(motivo)

                self.assertEqual(response.status_code, 400)
                self.assertIn("motivo", response.json())

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.EN_ESPERA)
        self.assertEqual(self.orden.motivo_cancelacion, "")
        self.assertEqual(self.orden.historial.count(), previo)

    def test_rechaza_cancelar_cuando_el_servicio_ya_inicio(self):
        previo = self.orden.historial.count()

        for estado in (
            Orden.Estado.EN_PROCESO,
            Orden.Estado.CONTROL_CALIDAD,
            Orden.Estado.LISTA,
            Orden.Estado.ENTREGADA,
        ):
            with self.subTest(estado=estado):
                self.fijar_estado(estado)

                response = self.cancelar(usuario=self.admin)

                self.assertEqual(response.status_code, 400)
                self.assertIn("el servicio ya inicio", str(response.json()))
                self.orden.refresh_from_db()
                self.assertEqual(self.orden.estado, estado)

        self.assertEqual(self.orden.historial.count(), previo)

    def test_una_orden_cancelada_no_se_reactiva_asigna_avanza_amplia_ni_cobra(self):
        self.pagar("4800")
        self.cancelar()
        previo = self.orden.historial.count()
        self.client.force_authenticate(self.admin)
        base = f"/api/ordenes/{self.orden.pk}"
        prenda = self.orden.prendas.first()

        intentos = {
            "cancelar de nuevo": (self.url, {"motivo": "Otra vez"}),
            "reactivar": (f"{base}/estado", {"estado": "Recibida"}),
            "avanzar": (f"{base}/estado", {"estado": "Clasificada"}),
            "asignar": (f"{base}/asignacion", {"operario": self.operario.pk}),
            "agregar prenda": (f"{base}/prendas", self.prenda(self.lavado)),
            "agregar servicio": (
                f"{base}/prendas/{prenda.pk}/servicios",
                {"servicio": self.lavado.pk},
            ),
            "registrar pago": (f"{base}/pagos", {"monto": "1000", "metodo": "efectivo"}),
        }
        for accion, (url, datos) in intentos.items():
            with self.subTest(accion=accion):
                response = self.client.post(url, datos, format="json")

                self.assertEqual(response.status_code, 400, response.json())
                self.assertIn("cancelada", str(response.json()))

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.CANCELADA)
        self.assertIsNone(self.orden.operario)
        self.assertEqual(self.orden.total_pagado(), Decimal("4800"))
        self.assertEqual(self.orden.historial.count(), previo)

    def test_la_orden_asignada_sale_de_la_bandeja_del_operario(self):
        self.pagar("4800")
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/asignacion",
            {"operario": self.operario.pk},
            format="json",
        )

        self.cancelar()

        self.orden.refresh_from_db()
        self.assertIsNone(self.orden.operario)
        self.assertIn("Sale de la bandeja de Luis", self.eventos(Evento.CANCELACION).get().detalle)
        self.client.force_authenticate(self.operario)
        self.assertEqual(self.client.get("/api/ordenes/bandeja").json(), [])

    def test_el_operario_recibe_403_al_cancelar(self):
        response = self.cancelar(usuario=self.operario)

        self.assertEqual(response.status_code, 403)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.EN_ESPERA)

    def test_la_orden_cancelada_sigue_en_el_historial_del_cliente(self):
        self.cancelar()

        response = self.client.get("/api/ordenes")

        self.assertEqual([o["estado"] for o in response.json()], ["Cancelada"])
        self.assertEqual(self.orden.historial.first().tipo_evento, Evento.CREACION)


class CancelarOrdenConNovedadApiTests(OrdenEnProcesoMixin, APITestCase):
    def decidir(self, decision):
        self.client.force_authenticate(self.recepcionista)
        return self.client.post(
            f"/api/ordenes/{self.orden.pk}/decision",
            {"decision": decision, "observacion": "Hable con Ana por telefono"},
            format="json",
        )

    def cancelar(self, usuario=None):
        self.client.force_authenticate(usuario or self.recepcionista)
        return self.client.post(
            f"/api/ordenes/{self.orden.pk}/cancelacion",
            {"motivo": "El cliente no acepta la prenda manchada"},
            format="json",
        )

    def test_se_cancela_la_orden_con_novedad_que_el_cliente_decidio_no_continuar(self):
        self.client.force_authenticate(self.recepcionista)
        self.client.post(
            f"/api/ordenes/{self.orden.pk}/pagos", {"monto": "5000", "metodo": "efectivo"}, format="json"
        )
        self.registrar_novedad()
        self.decidir(Novedad.Decision.NO_CONTINUAR)

        for usuario in (self.recepcionista, self.admin):
            with self.subTest(usuario=usuario.username):
                Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.CON_NOVEDAD)

                response = self.cancelar(usuario)

                self.assertEqual(response.status_code, 200, response.json())
                self.assertEqual(response.json()["estado"], "Cancelada")
                cancelacion = self.orden.historial.filter(tipo_evento=Evento.CANCELACION).last()
                self.assertEqual(cancelacion.usuario, usuario)
                self.assertEqual(
                    cancelacion.detalle,
                    "Con novedad → Cancelada. Motivo: El cliente no acepta la prenda manchada"
                    ". Sale de la bandeja de op",
                )
                devolucion = self.orden.historial.filter(tipo_evento=Evento.DEVOLUCION).last()
                self.assertRegex(devolucion.detalle, r"^\$5000(\.00)? devueltos al cliente\.")
                Orden.objects.filter(pk=self.orden.pk).update(operario=self.operario)

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/ordenes/novedades").json(), [])

    def test_rechaza_cancelar_la_orden_con_novedad_sin_decision(self):
        self.registrar_novedad()

        response = self.cancelar()

        self.assertEqual(response.status_code, 400)
        self.assertIn("el servicio ya inicio", str(response.json()))
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.CON_NOVEDAD)
        self.assertFalse(self.orden.historial.filter(tipo_evento=Evento.CANCELACION).exists())

    def test_rechaza_cancelar_si_el_cliente_decidio_continuar_o_reprocesar(self):
        for decision in (Novedad.Decision.CONTINUAR, Novedad.Decision.REPROCESAR):
            with self.subTest(decision=decision):
                Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.EN_PROCESO)
                self.registrar_novedad()
                self.decidir(decision)

                response = self.cancelar()

                self.assertEqual(response.status_code, 400)
                self.assertIn("el servicio ya inicio", str(response.json()))

        self.assertFalse(self.orden.historial.filter(tipo_evento=Evento.CANCELACION).exists())


class ConsultaPublicaApiTests(APITestCase):
    def setUp(self):
        self.orden = crear_orden(codigo="SW-ABCD2345")

    def consultar(self, codigo="SW-ABCD2345"):
        return self.client.get(f"/api/ordenes/consulta/{codigo}")

    def fijar(self, estado, fecha=date(2026, 11, 3)):
        Orden.objects.filter(pk=self.orden.pk).update(estado=estado, fecha_estimada_entrega=fecha)

    def test_sin_sesion_ve_el_estado_y_la_fecha_estimada(self):
        self.fijar(Orden.Estado.RECIBIDA)

        response = self.consultar()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"codigo": "SW-ABCD2345", "estado": "Recibida", "fecha_estimada_entrega": "2026-11-03"},
        )

    def test_en_espera_se_muestra_sin_fecha_estimada(self):
        datos = self.consultar().json()

        self.assertEqual(datos["estado"], "En espera")
        self.assertIsNone(datos["fecha_estimada_entrega"])

    def test_la_orden_cancelada_se_muestra_como_cancelada(self):
        self.fijar(Orden.Estado.CANCELADA)

        self.assertEqual(self.consultar().json()["estado"], "Cancelada")

    def test_un_codigo_inexistente_responde_404_con_mensaje(self):
        response = self.consultar("SW-ZZZZ9999")

        self.assertEqual(response.status_code, 404)
        self.assertIn("No encontramos una orden con ese codigo", response.json()["detail"])

    def test_no_expone_datos_del_cliente_ni_montos(self):
        Orden.objects.filter(pk=self.orden.pk).update(valor_total=Decimal("16000"))

        datos = self.consultar().json()

        self.assertEqual(set(datos), {"codigo", "estado", "fecha_estimada_entrega"})
        self.assertNotIn("Ana Gomez", str(datos))
        self.assertNotIn("16000", str(datos))

    def test_cualquier_rol_puede_consultar(self):
        for rol in User.Rol.values:
            with self.subTest(rol=rol):
                self.client.force_authenticate(
                    User.objects.create_user(username=f"u-{rol}", password="x", rol=rol)
                )
                self.assertEqual(self.consultar().status_code, 200)
