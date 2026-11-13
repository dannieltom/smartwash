from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import User
from ordenes.models import Comprobante, DanoPrenda, HistorialOrden, Novedad, Orden
from ordenes.tests import JPEG, CatalogoDePruebaMixin, crear_orden, data_url

from .models import EtapaDeTrabajo, Turno
from .services import turno_vigente

BOGOTA = ZoneInfo("America/Bogota")
Evento = HistorialOrden.TipoEvento
SIN_TURNO = {"detail": "Inicia tu turno para poder trabajar.", "codigo": "turno_no_iniciado"}


def operario(username, nombre="", turno=True):
    usuario = User.objects.create_user(username=username, password="x", rol=User.Rol.OPERARIO, first_name=nombre)
    if turno:
        Turno.objects.create(operario=usuario, inicio=timezone.now())
    return usuario


class TurnoApiTests(APITestCase):
    def setUp(self):
        self.operario = operario("op", turno=False)
        self.client.force_login(self.operario)

    def post(self, accion):
        return self.client.post(f"/api/turnos/{accion}")

    def test_iniciar_turno(self):
        response = self.post("iniciar")

        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual((response.json()["en_turno"], response.json()["ordenes_en_curso"]), (True, 0))
        self.assertRegex(response.json()["inicio"], r"-05:00$")
        self.assertIsNotNone(turno_vigente(self.operario))

    def test_no_se_inicia_un_turno_si_ya_hay_uno_vigente(self):
        self.post("iniciar")

        response = self.post("iniciar")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Turno.objects.count(), 1)

    def test_terminar_sin_turno_responde_400(self):
        self.assertEqual(self.post("terminar").status_code, 400)

    def test_se_puede_terminar_con_ordenes_en_proceso_y_siguen_asignadas(self):
        self.post("iniciar")
        orden = crear_orden()
        Orden.objects.filter(pk=orden.pk).update(estado=Orden.Estado.EN_PROCESO, operario=self.operario)

        response = self.post("terminar")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"en_turno": False, "inicio": None, "ordenes_en_curso": 1})
        turno = Turno.objects.get()
        self.assertEqual(turno.cierre, Turno.Cierre.MANUAL)
        orden.refresh_from_db()
        self.assertEqual(orden.operario, self.operario)

    def test_el_turno_abierto_de_ayer_se_cierra_solo_al_consultar(self):
        ayer = timezone.localtime() - timedelta(days=1)
        Turno.objects.create(operario=self.operario, inicio=ayer.replace(hour=8))

        actual = self.client.get("/api/turnos/actual").json()

        self.assertFalse(actual["en_turno"])
        turno = Turno.objects.get()
        fin = timezone.localtime(turno.fin)
        self.assertEqual((turno.cierre, fin.date(), fin.hour, fin.minute), (Turno.Cierre.AUTOMATICO, ayer.date(), 23, 59))
        self.assertEqual(self.post("iniciar").status_code, 201)

    def test_me_dice_si_el_operario_esta_en_turno(self):
        self.assertFalse(self.client.get("/api/auth/me").json()["en_turno"])
        self.post("iniciar")
        self.assertTrue(self.client.get("/api/auth/me").json()["en_turno"])

        self.client.force_login(User.objects.create_user(username="r", password="x", rol=User.Rol.RECEPCIONISTA))
        self.assertNotIn("en_turno", self.client.get("/api/auth/me").json())

    def test_solo_el_administrador_lista_los_turnos_del_rango(self):
        self.post("iniciar")
        self.assertEqual(self.client.get("/api/turnos").status_code, 403)

        self.client.force_login(User.objects.create_user(username="a", password="x", rol=User.Rol.ADMINISTRADOR))
        turnos = self.client.get("/api/turnos").json()

        self.assertEqual([t["operario"] for t in turnos], [self.operario.pk])
        self.assertIsNone(turnos[0]["fin"])


class TurnoModeloTests(TestCase):
    def setUp(self):
        self.operario = operario("op", turno=False)
        self.turno = Turno.objects.create(operario=self.operario, inicio=timezone.now())

    def test_solo_hay_un_turno_abierto_por_operario(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Turno.objects.create(operario=self.operario, inicio=timezone.now())

    def test_solo_se_escribe_el_cierre_una_vez(self):
        self.turno.inicio -= timedelta(hours=1)
        with self.assertRaises(PermissionDenied):
            self.turno.save()
        self.turno.refresh_from_db()
        self.turno.cerrar(timezone.now(), Turno.Cierre.MANUAL)
        with self.assertRaises(PermissionDenied):
            self.turno.cerrar(timezone.now(), Turno.Cierre.MANUAL)
        with self.assertRaises(PermissionDenied):
            self.turno.delete()
        with self.assertRaises(PermissionDenied):
            Turno.objects.update(fin=None)


class TurnoObligatorioTests(CatalogoDePruebaMixin, APITestCase):
    """Con sesion real: force_authenticate se salta las clases de autenticacion."""

    def setUp(self):
        self.crear_catalogo()
        self.operario = operario("op", turno=False)
        self.orden = crear_orden(codigo="SW-ABCD2345")
        Orden.objects.filter(pk=self.orden.pk).update(
            estado=Orden.Estado.EN_PROCESO, operario=self.operario, abono_alcanzado_en=timezone.localdate()
        )
        self.client.force_login(self.operario)

    def llamadas(self):
        url = f"/api/ordenes/{self.orden.pk}"
        return {
            "bandeja": self.client.get("/api/ordenes/bandeja"),
            "cambiar estado": self.client.post(f"{url}/estado", {"estado": "Control de calidad"}, format="json"),
            "novedades": self.client.get(f"{url}/novedades"),
            "detalle": self.client.get(url),
            "lista": self.client.get("/api/ordenes"),
        }

    def test_sin_turno_el_operario_recibe_403_con_codigo_en_toda_la_api(self):
        for nombre, response in self.llamadas().items():
            with self.subTest(nombre):
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json(), SIN_TURNO)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, Orden.Estado.EN_PROCESO)

    def test_con_turno_pasa(self):
        Turno.objects.create(operario=self.operario, inicio=timezone.now())

        for nombre, response in self.llamadas().items():
            with self.subTest(nombre):
                self.assertIn(response.status_code, (200, 201), response.content[:200])

    def test_las_rutas_de_sesion_y_de_turno_no_piden_turno(self):
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200)
        self.assertEqual(self.client.get("/api/turnos/actual").status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout").status_code, 204)

    def test_el_administrador_y_la_recepcionista_nunca_quedan_bloqueados(self):
        for rol in (User.Rol.ADMINISTRADOR, User.Rol.RECEPCIONISTA):
            with self.subTest(rol=rol):
                self.client.force_login(User.objects.create_user(username=f"u-{rol}", password="x", rol=rol))
                self.assertEqual(self.client.get("/api/ordenes").status_code, 200)
                self.assertEqual(self.client.get(f"/api/ordenes/{self.orden.pk}").status_code, 200)

    def test_el_rastreo_publico_funciona_sin_sesion_y_con_un_operario_sin_turno(self):
        self.assertEqual(self.client.get("/api/ordenes/consulta/SW-ABCD2345").status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get("/api/ordenes/consulta/SW-ABCD2345").status_code, 200)
        self.assertEqual(self.client.get("/api/ordenes/consulta/SW-NOEXISTE").status_code, 404)


class CargaDeOperariosTests(CatalogoDePruebaMixin, APITestCase):
    url = "/api/operarios"

    def setUp(self):
        self.crear_catalogo()
        self.client.force_authenticate(self.recepcionista)

    def orden_de(self, operario, *cantidades, estado=Orden.Estado.EN_PROCESO):
        self.client.force_authenticate(self.recepcionista)
        datos = self.registrar(*(self.prenda(self.planchado, cantidad=c) for c in cantidades)).json()
        Orden.objects.filter(pk=datos["id"]).update(estado=estado, operario=operario)
        return Orden.objects.get(pk=datos["id"])

    def carga(self):
        return {o["username"]: o for o in self.client.get(self.url).json()}

    def test_cuenta_ordenes_y_prendas_activas_sin_las_danadas_ni_las_cerradas(self):
        luis = operario("luis", "Luis")
        orden = self.orden_de(luis, 3, 2)
        self.orden_de(luis, 4, estado=Orden.Estado.ENTREGADA)
        self.orden_de(luis, 1, estado=Orden.Estado.CONTROL_CALIDAD)
        danada = orden.prendas.get(cantidad=2)
        DanoPrenda.objects.create(
            orden=orden, prenda=danada, tipo="perdida", cantidad_afectada=2, descripcion="No aparece",
            valor_unitario_declarado=Decimal("1000"), valor_declarado=Decimal("2000"), valor_servicio=Decimal("12000"),
        )

        carga = self.carga()["luis"]

        self.assertEqual(
            (carga["ordenes_activas"], carga["prendas_activas"], carga["en_turno"], carga["nombre"]), (2, 4, True, "Luis")
        )
        self.assertEqual(set(carga) >= {"id", "username", "nombre", "recomendado"}, True)

    def test_recomienda_al_de_menos_prendas_y_desempata_por_ordenes_y_nombre(self):
        ana, beto, caro = operario("ana", "Ana"), operario("beto", "Beto"), operario("caro", "Caro")
        self.orden_de(ana, 3)
        self.orden_de(beto, 1)
        self.orden_de(beto, 1)
        self.orden_de(caro, 2)

        self.assertEqual([u for u, o in self.carga().items() if o["recomendado"]], ["caro"])

        self.orden_de(ana, 1)
        self.orden_de(caro, 1)  # caro: 3 prendas en 2 ordenes; beto: 2 en 2
        self.assertEqual([u for u, o in self.carga().items() if o["recomendado"]], ["beto"])

        operario("dani", "Dani")
        self.assertEqual([u for u, o in self.carga().items() if o["recomendado"]], ["dani"])

    def test_desempate_final_por_nombre(self):
        operario("zoe", "Zoe")
        operario("abel", "Abel")

        self.assertEqual([u for u, o in self.carga().items() if o["recomendado"]], ["abel"])

    def test_sin_nadie_en_turno_no_hay_recomendado_y_se_listan_los_de_fuera_de_turno(self):
        operario("luis", "Luis", turno=False)

        carga = self.carga()["luis"]

        self.assertEqual((carga["en_turno"], carga["recomendado"]), (False, False))

    def test_las_consultas_no_crecen_con_el_numero_de_operarios(self):
        operario("uno")
        with self.assertNumQueries(1):
            self.client.get(self.url)

        for i in range(5):
            self.orden_de(operario(f"op{i}"), 2)
        self.client.force_authenticate(self.recepcionista)
        with self.assertNumQueries(1):
            self.client.get(self.url)


class AsignacionSoloEnTurnoTests(CatalogoDePruebaMixin, APITestCase):
    def setUp(self):
        self.crear_catalogo()
        self.client.force_authenticate(self.recepcionista)
        self.orden = Orden.objects.get(pk=self.registrar(self.prenda(self.planchado)).json()["id"])
        self.client.post(f"/api/ordenes/{self.orden.pk}/pagos", {"monto": "6000", "metodo": "efectivo"}, format="json")
        self.en_turno = operario("luis", "Luis")
        self.fuera = operario("marta", "Marta", turno=False)

    def asignar(self, operario_):
        return self.client.post(f"/api/ordenes/{self.orden.pk}/asignacion", {"operario": operario_.pk}, format="json")

    def test_rechaza_asignar_a_quien_no_esta_en_turno(self):
        response = self.asignar(self.fuera)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["operario"], "Marta no está en turno. Asígnala a un operario en turno.")
        self.orden.refresh_from_db()
        self.assertIsNone(self.orden.operario)

    def test_acepta_a_quien_esta_en_turno_y_rechaza_reasignar_fuera_de_turno(self):
        self.assertEqual(self.asignar(self.en_turno).status_code, 200)

        self.assertEqual(self.asignar(self.fuera).status_code, 400)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.operario, self.en_turno)

    def test_el_administrador_tampoco_reasigna_fuera_de_turno(self):
        self.asignar(self.en_turno)
        Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.EN_PROCESO)
        User.objects.filter(pk=self.en_turno.pk).update(is_active=False)
        self.client.force_authenticate(User.objects.create_user(username="jefe", password="x", rol=User.Rol.ADMINISTRADOR))

        self.assertEqual(self.asignar(self.fuera).status_code, 400)
        self.assertEqual(self.asignar(operario("nico", "Nico")).status_code, 200)


class FlujoMixin(CatalogoDePruebaMixin):
    """Orden de dos camisas asignada a Luis, en Clasificada; el administrador la mueve."""

    def setUp(self):
        self.crear_catalogo()
        self.admin = User.objects.create_user(username="jefe", password="x", rol=User.Rol.ADMINISTRADOR)
        self.luis = operario("luis", "Luis")
        self.client.force_authenticate(self.recepcionista)
        self.orden = Orden.objects.get(
            pk=self.registrar(self.prenda(self.planchado), self.prenda(self.planchado)).json()["id"]
        )
        self.url = f"/api/ordenes/{self.orden.pk}"
        self.client.post(f"{self.url}/pagos", {"monto": "12000", "metodo": "efectivo"}, format="json")
        self.client.post(f"{self.url}/asignacion", {"operario": self.luis.pk}, format="json")
        self.estado("Clasificada")

    def estado(self, estado):
        self.client.force_authenticate(self.admin)
        response = self.client.post(f"{self.url}/estado", {"estado": estado}, format="json")
        self.assertEqual(response.status_code, 200, response.json())

    def etapas(self):
        return [(e.estado, e.operario.username, e.fin is None) for e in EtapaDeTrabajo.objects.filter(orden=self.orden)]

    def novedad(self):
        self.client.force_authenticate(self.luis)
        prenda = self.orden.prendas.first()
        response = self.client.post(
            f"{self.url}/novedades", {"prenda": prenda.pk, "descripcion": "Mancha", "foto": data_url(JPEG)}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.json())

    def decidir(self, decision, **extra):
        self.client.force_authenticate(self.recepcionista)
        return self.client.post(
            f"{self.url}/decision", {"decision": decision, "observacion": "Hable con Ana", **extra}, format="json"
        )


class EtapasDeTrabajoTests(FlujoMixin, APITestCase):
    def test_el_flujo_normal_abre_y_cierra_una_etapa_por_estado(self):
        self.estado("En proceso")
        self.assertEqual(self.etapas(), [("En proceso", "luis", True)])

        self.estado("Control de calidad")
        self.estado("Lista para entrega")

        self.assertEqual(self.etapas(), [("En proceso", "luis", False), ("Control de calidad", "luis", False)])

    def test_cada_reproceso_abre_una_etapa_nueva(self):
        self.estado("En proceso")
        self.estado("Control de calidad")
        self.estado("En proceso")

        self.assertEqual(
            self.etapas(),
            [("En proceso", "luis", False), ("Control de calidad", "luis", False), ("En proceso", "luis", True)],
        )

    def test_la_novedad_pausa_y_la_decision_reanuda(self):
        self.estado("En proceso")
        self.novedad()
        self.assertEqual(self.etapas(), [("En proceso", "luis", False)])

        self.assertEqual(self.decidir("continuar").status_code, 200)

        self.assertEqual(self.etapas(), [("En proceso", "luis", False), ("En proceso", "luis", True)])

    def test_la_reasignacion_cierra_la_etapa_y_abre_otra_para_el_nuevo_operario(self):
        self.estado("En proceso")
        User.objects.filter(pk=self.luis.pk).update(is_active=False)
        nico = operario("nico", "Nico")
        self.client.force_authenticate(self.admin)

        self.client.post(f"{self.url}/asignacion", {"operario": nico.pk}, format="json")

        self.assertEqual(self.etapas(), [("En proceso", "luis", False), ("En proceso", "nico", True)])

    def test_la_cancelacion_de_una_orden_con_novedad_no_deja_etapas_abiertas(self):
        self.estado("En proceso")
        self.novedad()
        Novedad.objects.filter(orden=self.orden).update(decision=Novedad.Decision.NO_CONTINUAR)
        self.client.force_authenticate(self.recepcionista)

        response = self.client.post(f"{self.url}/cancelacion", {"motivo": "No sigue"}, format="json")

        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(self.etapas(), [("En proceso", "luis", False)])

    def test_la_entrega_con_comprobante_y_el_reproceso_desde_la_entrega(self):
        self.estado("En proceso")
        self.estado("Control de calidad")
        self.estado("Lista para entrega")
        self.client.force_authenticate(self.recepcionista)
        camisa_1, camisa_2 = self.orden.prendas.all()
        self.client.post(f"{self.url}/entrega", {"prendas": [
            {"prenda": camisa_1.pk, "resultado": "novedad", "observacion": "Boton suelto", "foto": data_url(JPEG)},
            {"prenda": camisa_2.pk, "resultado": "coincide"},
        ]}, format="json")
        nico = operario("nico", "Nico")

        self.assertEqual(self.decidir("reprocesar_con_descuento", operario=nico.pk).status_code, 200)
        self.assertEqual(self.etapas()[-1], ("En proceso", "nico", True))

        self.estado("Control de calidad")
        self.estado("Lista para entrega")
        self.client.force_authenticate(self.recepcionista)
        response = self.client.post(f"{self.url}/entrega", {"prendas": [
            {"prenda": camisa_1.pk, "resultado": "coincide"}, {"prenda": camisa_2.pk, "resultado": "coincide"},
        ]}, format="json")

        self.assertEqual(response.status_code, 200, response.json())
        self.assertTrue(Comprobante.objects.filter(orden=self.orden, tipo=Comprobante.Tipo.ENTREGA).exists())
        self.assertFalse(EtapaDeTrabajo.objects.filter(orden=self.orden, fin__isnull=True).exists())

    def test_el_reproceso_con_otro_operario_fuera_de_turno_se_rechaza_y_el_mismo_no_lo_exige(self):
        self.estado("En proceso")
        self.estado("Control de calidad")
        self.estado("Lista para entrega")
        self.client.force_authenticate(self.recepcionista)
        camisa_1, camisa_2 = self.orden.prendas.all()
        self.client.post(f"{self.url}/entrega", {"prendas": [
            {"prenda": camisa_1.pk, "resultado": "novedad", "observacion": "Boton", "foto": data_url(JPEG)},
            {"prenda": camisa_2.pk, "resultado": "coincide"},
        ]}, format="json")
        marta = operario("marta", "Marta", turno=False)
        Turno.objects.get(operario=self.luis).cerrar(timezone.now(), Turno.Cierre.MANUAL)

        self.assertEqual(self.decidir("reprocesar_con_descuento", operario=marta.pk).status_code, 400)
        self.assertEqual(self.decidir("reprocesar_con_descuento", operario=self.luis.pk).status_code, 200)

    def test_una_orden_en_proceso_sin_etapa_abierta_no_falla_al_avanzar(self):
        Orden.objects.filter(pk=self.orden.pk).update(estado=Orden.Estado.EN_PROCESO)

        self.estado("Control de calidad")

        self.assertEqual(self.etapas(), [("Control de calidad", "luis", True)])


class OrdenesDeOperarioTests(FlujoMixin, APITestCase):
    def test_lista_las_ordenes_activas_con_la_fecha_de_asignacion_y_las_prendas_agrupadas(self):
        self.client.force_authenticate(self.recepcionista)

        ordenes = self.client.get(f"/api/operarios/{self.luis.pk}/ordenes").json()

        asignada = HistorialOrden.objects.get(orden=self.orden, tipo_evento=Evento.ASIGNACION).fecha
        self.assertEqual(
            ordenes,
            [
                {
                    "id": self.orden.pk,
                    "codigo": self.orden.codigo,
                    "fecha_asignacion": timezone.localtime(asignada).isoformat(),
                    "cliente_nombre": "Ana Gomez",
                    "estado": "Clasificada",
                    "total_prendas": 2,
                    "prendas": [{"cantidad": 2, "tipo_prenda": "Camisa", "servicios": ["Planchado"]}],
                }
            ],
        )

    def test_404_si_no_es_operario_y_403_para_el_operario(self):
        self.client.force_authenticate(self.recepcionista)
        self.assertEqual(self.client.get(f"/api/operarios/{self.admin.pk}/ordenes").status_code, 404)
        self.client.force_authenticate(self.luis)
        self.assertEqual(self.client.get(f"/api/operarios/{self.luis.pk}/ordenes").status_code, 403)


def en_bogota(hora, minuto=0):
    hoy = timezone.localtime().date()
    return datetime(hoy.year, hoy.month, hoy.day, hora, minuto, tzinfo=BOGOTA)


class ActividadTests(APITestCase):
    url = "/api/operarios/actividad"

    def setUp(self):
        self.admin = User.objects.create_user(username="jefe", password="x", rol=User.Rol.ADMINISTRADOR)
        self.luis, self.ana = operario("luis", "Luis", turno=False), operario("ana", "Ana", turno=False)
        self.orden_1, self.orden_2, self.orden_3 = (crear_orden(codigo=f"SW-ORDEN00{i}") for i in (1, 2, 3))
        etapa = EtapaDeTrabajo.objects.create
        etapa(orden=self.orden_1, operario=self.luis, estado="En proceso", inicio=en_bogota(14), fin=en_bogota(16, 30))
        etapa(orden=self.orden_2, operario=self.luis, estado="En proceso", inicio=en_bogota(16, 30))
        etapa(orden=self.orden_3, operario=self.ana, estado="Control de calidad", inicio=en_bogota(9), fin=en_bogota(10))
        Turno.objects.create(operario=self.luis, inicio=en_bogota(8))
        self.client.force_authenticate(self.admin)

    def actividad(self, **params):
        return self.client.get(self.url, params)

    def test_que_trabajaba_cada_operario_entre_las_4_y_las_6_de_la_tarde(self):
        datos = self.actividad(desde=en_bogota(16).isoformat(), hasta=en_bogota(18).isoformat()).json()

        self.assertEqual(
            [(e["orden_codigo"], e["operario_nombre"], e["fin"]) for e in datos["etapas"]],
            [("SW-ORDEN001", "Luis", en_bogota(16, 30).isoformat()), ("SW-ORDEN002", "Luis", None)],
        )
        self.assertEqual(datos["etapas"][0]["cliente_nombre"], "Ana Gomez")
        self.assertTrue(datos["etapas"][0]["inicio"].endswith("-05:00"))
        self.assertEqual([t["operario_nombre"] for t in datos["turnos"]], ["Luis"])

    def test_filtra_por_operario_y_por_defecto_es_hoy_hasta_ahora(self):
        datos = self.actividad(operario=self.ana.pk).json()

        self.assertEqual([e["orden_codigo"] for e in datos["etapas"]], ["SW-ORDEN003"])
        self.assertEqual(datos["turnos"], [])

    def test_valida_el_rango(self):
        for params in (
            {"desde": en_bogota(18).isoformat(), "hasta": en_bogota(16).isoformat()},
            {"desde": (en_bogota(8) - timedelta(days=40)).isoformat(), "hasta": en_bogota(8).isoformat()},
            {"desde": "ayer"},
            {"operario": self.admin.pk},
        ):
            with self.subTest(params=params):
                self.assertEqual(self.actividad(**params).status_code, 400)

    def test_solo_el_administrador(self):
        for usuario in (
            User.objects.create_user(username="r", password="x", rol=User.Rol.RECEPCIONISTA),
            self.luis,
        ):
            with self.subTest(usuario=usuario.username):
                self.client.force_authenticate(usuario)
                self.assertEqual(self.actividad().status_code, 403)
