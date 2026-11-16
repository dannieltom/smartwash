from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection
from django.db.models import ProtectedError
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APITestCase

from .models import Material, NivelDificultad, Servicio, Tarifa, TipoPrenda
from .serializers import TarifaSerializer

User = get_user_model()


class TarifaTests(TestCase):
    def setUp(self):
        self.camisa = TipoPrenda.objects.create(nombre="Camisa")
        self.lavado = Servicio.objects.create(nombre="Lavado")

    def crear_tarifa(self, valor="8000", desde=date(2026, 1, 1), hasta=None, **extra):
        return Tarifa.objects.create(
            tipo_prenda=extra.get("tipo_prenda", self.camisa),
            servicio=extra.get("servicio", self.lavado),
            valor_base=Decimal(valor),
            precio_por_kilo=Decimal("0"),
            plazo_entrega_dias=2,
            vigente_desde=desde,
            vigente_hasta=hasta,
        )

    def test_solo_admite_una_tarifa_vigente_por_tipo_de_prenda_y_servicio(self):
        self.crear_tarifa()
        with self.assertRaises(IntegrityError):
            self.crear_tarifa(valor="9000")

    def test_al_cerrar_la_vigencia_se_puede_registrar_la_nueva_tarifa(self):
        anterior = self.crear_tarifa(valor="8000")
        anterior.vigente_hasta = date(2026, 6, 1)
        anterior.save()

        self.crear_tarifa(valor="9000", desde=date(2026, 6, 1))

        self.assertEqual(Tarifa.objects.count(), 2)
        self.assertEqual(Tarifa.objects.filter(vigente_hasta__isnull=True).count(), 1)

    def test_rechaza_una_tarifa_negativa(self):
        with self.assertRaises(IntegrityError):
            self.crear_tarifa(valor="-1000")

    def test_rechaza_una_vigencia_que_termina_antes_de_empezar(self):
        with self.assertRaises(IntegrityError):
            self.crear_tarifa(desde=date(2026, 6, 1), hasta=date(2026, 1, 1))

    def test_el_valor_se_guarda_como_decimal_exacto(self):
        tarifa = self.crear_tarifa(valor="8500.55")
        tarifa.refresh_from_db()
        self.assertEqual(tarifa.valor_base, Decimal("8500.55"))


class CatalogoApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="smartwash123", rol=User.Rol.ADMINISTRADOR
        )
        self.client.login(username="admin", password="smartwash123")
        self.camisa = TipoPrenda.objects.create(nombre="Camisa")
        self.lavado = Servicio.objects.create(nombre="Lavado")
        self.nivel = NivelDificultad.objects.create(nombre="Facil", factor=Decimal("1.00"))

    def datos_tarifa(self, **extra):
        datos = {
            "tipo_prenda": self.camisa.pk,
            "servicio": self.lavado.pk,
            "valor_base": "8000.00",
            "precio_por_kilo": "0",
            "plazo_entrega_dias": 2,
            "vigente_desde": "2026-01-01",
        }
        datos.update(extra)
        return datos

    def test_crea_un_servicio_y_registra_quien_lo_creo(self):
        response = self.client.post(
            "/api/catalogo/servicios", {"nombre": "Planchado", "descripcion": "A vapor"}
        )
        self.assertEqual(response.status_code, 201)
        servicio = Servicio.objects.get(nombre="Planchado")
        self.assertEqual(servicio.creado_por, self.admin)

    def test_edita_un_servicio_existente(self):
        response = self.client.patch(
            f"/api/catalogo/servicios/{self.lavado.pk}",
            {"descripcion": "Lavado en agua"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.lavado.refresh_from_db()
        self.assertEqual(self.lavado.descripcion, "Lavado en agua")
        self.assertEqual(self.lavado.actualizado_por, self.admin)

    def test_rechaza_un_servicio_duplicado_sin_importar_mayusculas(self):
        response = self.client.post("/api/catalogo/servicios", {"nombre": " lavado "})
        self.assertEqual(response.status_code, 400)
        self.assertIn("nombre", response.json())
        self.assertEqual(Servicio.objects.count(), 1)

    def test_crea_un_tipo_de_prenda(self):
        response = self.client.post(
            "/api/catalogo/tipos-prenda", {"nombre": "Cobija"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"id": TipoPrenda.objects.get(nombre="Cobija").pk, "nombre": "Cobija", "peso_estandar": None})

    def test_crea_y_edita_un_material_con_autoria(self):
        creado = self.client.post(
            "/api/catalogo/materiales", {"nombre": "Lana", "nivel_dificultad": self.nivel.pk}
        )
        self.assertEqual(creado.status_code, 201)
        material = Material.objects.get()
        self.assertEqual(material.creado_por, self.admin)

        editado = self.client.patch(
            f"/api/catalogo/materiales/{material.pk}", {"nombre": "Seda"}, content_type="application/json"
        )
        self.assertEqual(editado.status_code, 200)
        material.refresh_from_db()
        self.assertEqual(material.nombre, "Seda")

    def test_rechaza_un_material_repetido_sin_importar_mayusculas(self):
        Material.objects.create(nombre="Algodon", nivel_dificultad=self.nivel)
        response = self.client.post("/api/catalogo/materiales", {"nombre": " algodon "})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Material.objects.count(), 1)

    def test_cualquier_sesion_lista_materiales_y_solo_el_administrador_escribe(self):
        Material.objects.create(nombre="Jean", nivel_dificultad=self.nivel)
        for rol in (User.Rol.RECEPCIONISTA, User.Rol.OPERARIO):
            usuario = User.objects.create_user(username=f"u-{rol}", password="x", rol=rol)
            self.client.force_authenticate(usuario)
            self.assertEqual(self.client.get("/api/catalogo/materiales").status_code, 200)
            self.assertEqual(self.client.post("/api/catalogo/materiales", {"nombre": "Lino", "nivel_dificultad": self.nivel.pk}).status_code, 403)
            self.assertEqual(
                self.client.post("/api/catalogo/tipos-prenda", {"nombre": "Saco"}).status_code, 403
            )
        self.assertEqual(Material.objects.count(), 1)

    def test_crea_una_tarifa_para_un_par_prenda_servicio(self):
        response = self.client.post("/api/catalogo/tarifas", self.datos_tarifa())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["servicio_nombre"], "Lavado")
        tarifa = Tarifa.objects.get()
        self.assertEqual(tarifa.valor_base, Decimal("8000.00"))
        self.assertEqual(tarifa.creado_por, self.admin)

    def test_rechaza_una_tarifa_negativa(self):
        response = self.client.post("/api/catalogo/tarifas", self.datos_tarifa(valor_base="-1"))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Tarifa.objects.exists())

    def test_rechaza_una_tarifa_vacia(self):
        response = self.client.post("/api/catalogo/tarifas", self.datos_tarifa(valor_base=""))
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Tarifa.objects.exists())

    def test_una_tarifa_nueva_cierra_la_vigente_y_conserva_el_historico(self):
        self.client.post("/api/catalogo/tarifas", self.datos_tarifa())
        response = self.client.post(
            "/api/catalogo/tarifas",
            self.datos_tarifa(valor_base="9000.00", vigente_desde="2026-06-01"),
        )
        self.assertEqual(response.status_code, 201)
        anterior = Tarifa.objects.get(valor_base=Decimal("8000.00"))
        self.assertEqual(anterior.vigente_hasta, date(2026, 6, 1))
        vigentes = self.client.get("/api/catalogo/tarifas?vigentes=1").json()
        self.assertEqual([t["valor_base"] for t in vigentes], ["9000.00"])

    def test_una_tarifa_nueva_no_puede_empezar_antes_que_la_vigente(self):
        self.client.post("/api/catalogo/tarifas", self.datos_tarifa(vigente_desde="2026-06-01"))
        response = self.client.post(
            "/api/catalogo/tarifas", self.datos_tarifa(vigente_desde="2026-01-01")
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Tarifa.objects.count(), 1)
        self.assertIsNone(Tarifa.objects.get().vigente_hasta)

    def test_rechaza_una_tarifa_cerrada_que_se_cruza_con_la_vigente(self):
        self.client.post("/api/catalogo/tarifas", self.datos_tarifa(vigente_desde="2026-06-01"))
        response = self.client.post(
            "/api/catalogo/tarifas",
            self.datos_tarifa(vigente_desde="2026-07-01", vigente_hasta="2026-08-01"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("vigente_desde", response.json())
        self.assertEqual(Tarifa.objects.count(), 1)
        self.assertIsNone(Tarifa.objects.get().vigente_hasta)

    def test_rechaza_una_tarifa_cerrada_que_se_cruza_con_una_historica(self):
        self.client.post(
            "/api/catalogo/tarifas",
            self.datos_tarifa(vigente_desde="2026-01-01", vigente_hasta="2026-03-01"),
        )
        response = self.client.post(
            "/api/catalogo/tarifas",
            self.datos_tarifa(vigente_desde="2026-02-01", vigente_hasta="2026-04-01"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Tarifa.objects.count(), 1)

    def test_rechaza_una_tarifa_cerrada_que_envuelve_a_otra(self):
        self.client.post(
            "/api/catalogo/tarifas",
            self.datos_tarifa(vigente_desde="2026-02-01", vigente_hasta="2026-03-01"),
        )
        response = self.client.post(
            "/api/catalogo/tarifas",
            self.datos_tarifa(vigente_desde="2026-01-01", vigente_hasta="2026-06-01"),
        )
        self.assertEqual(response.status_code, 400)

    def test_acepta_tarifas_cerradas_contiguas(self):
        self.client.post(
            "/api/catalogo/tarifas",
            self.datos_tarifa(vigente_desde="2026-01-01", vigente_hasta="2026-03-01"),
        )
        response = self.client.post(
            "/api/catalogo/tarifas",
            self.datos_tarifa(vigente_desde="2026-03-01", vigente_hasta="2026-04-01"),
        )
        self.assertEqual(response.status_code, 201)

    def test_acepta_una_tarifa_cerrada_anterior_a_la_vigente(self):
        self.client.post("/api/catalogo/tarifas", self.datos_tarifa(vigente_desde="2026-06-01"))
        response = self.client.post(
            "/api/catalogo/tarifas",
            self.datos_tarifa(vigente_desde="2026-01-01", vigente_hasta="2026-06-01"),
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Tarifa.objects.filter(vigente_hasta__isnull=True).count(), 1)

    def test_el_solape_solo_se_evalua_dentro_del_mismo_par_prenda_servicio(self):
        pantalon = TipoPrenda.objects.create(nombre="Pantalon")
        self.client.post("/api/catalogo/tarifas", self.datos_tarifa(vigente_desde="2026-06-01"))
        response = self.client.post(
            "/api/catalogo/tarifas",
            self.datos_tarifa(
                tipo_prenda=pantalon.pk, vigente_desde="2026-07-01", vigente_hasta="2026-08-01"
            ),
        )
        self.assertEqual(response.status_code, 201)

    def test_una_tarifa_nueva_abierta_no_puede_cruzarse_con_una_cerrada_posterior(self):
        Tarifa.objects.create(
            tipo_prenda=self.camisa,
            servicio=self.lavado,
            valor_base=Decimal("7000"),
            precio_por_kilo=Decimal("0"),
            plazo_entrega_dias=2,
            vigente_desde=date(2026, 7, 1),
            vigente_hasta=date(2026, 8, 1),
        )
        Tarifa.objects.create(
            tipo_prenda=self.camisa,
            servicio=self.lavado,
            valor_base=Decimal("8000"),
            precio_por_kilo=Decimal("0"),
            plazo_entrega_dias=2,
            vigente_desde=date(2026, 6, 1),
        )
        response = self.client.post(
            "/api/catalogo/tarifas", self.datos_tarifa(vigente_desde="2026-06-15")
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Tarifa.objects.count(), 2)

    def test_editar_una_tarifa_no_choca_consigo_misma(self):
        tarifa_id = self.client.post(
            "/api/catalogo/tarifas",
            self.datos_tarifa(vigente_desde="2026-01-01", vigente_hasta="2026-03-01"),
        ).json()["id"]
        response = self.client.patch(
            f"/api/catalogo/tarifas/{tarifa_id}",
            {"valor_base": "8500.00", "vigente_hasta": "2026-04-01"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Tarifa.objects.get(pk=tarifa_id).vigente_hasta, date(2026, 4, 1))

    def test_no_permite_extender_una_tarifa_hasta_cruzarse_con_otra(self):
        primera = self.client.post(
            "/api/catalogo/tarifas",
            self.datos_tarifa(vigente_desde="2026-01-01", vigente_hasta="2026-03-01"),
        ).json()["id"]
        self.client.post("/api/catalogo/tarifas", self.datos_tarifa(vigente_desde="2026-03-01"))
        response = self.client.patch(
            f"/api/catalogo/tarifas/{primera}",
            {"vigente_hasta": "2026-05-01"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Tarifa.objects.get(pk=primera).vigente_hasta, date(2026, 3, 1))

    def test_no_permite_mover_una_tarifa_a_otro_servicio(self):
        tarifa_id = self.client.post("/api/catalogo/tarifas", self.datos_tarifa()).json()["id"]
        planchado = Servicio.objects.create(nombre="Planchado")
        response = self.client.patch(
            f"/api/catalogo/tarifas/{tarifa_id}",
            {"servicio": planchado.pk},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_no_permite_reabrir_una_tarifa_si_ya_hay_otra_vigente(self):
        primera = self.client.post("/api/catalogo/tarifas", self.datos_tarifa()).json()["id"]
        self.client.post(
            "/api/catalogo/tarifas", self.datos_tarifa(vigente_desde="2026-06-01")
        )
        response = self.client.patch(
            f"/api/catalogo/tarifas/{primera}",
            {"vigente_hasta": None},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_una_edicion_rechazada_no_cambia_nada(self):
        tarifa_id = self.client.post("/api/catalogo/tarifas", self.datos_tarifa()).json()["id"]
        response = self.client.patch(
            f"/api/catalogo/tarifas/{tarifa_id}",
            {"valor_base": "9500.00", "plazo_entrega_dias": 0},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        tarifa = Tarifa.objects.get(pk=tarifa_id)
        self.assertEqual(tarifa.valor_base, Decimal("8000.00"))
        self.assertEqual(tarifa.plazo_entrega_dias, 2)

    def test_requiere_sesion_activa(self):
        self.client.logout()
        response = self.client.post("/api/catalogo/servicios", {"nombre": "Planchado"})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Servicio.objects.filter(nombre="Planchado").exists())

    def test_una_tarifa_general_no_lleva_tipo_de_prenda(self):
        datos = self.datos_tarifa(precio_por_kilo="8000", valor_base="5000")
        del datos["tipo_prenda"]
        response = self.client.post("/api/catalogo/tarifas", datos)
        self.assertEqual(response.status_code, 201, response.json())
        self.assertIsNone(response.json()["tipo_prenda"])
        self.assertIsNone(response.json()["tipo_prenda_nombre"])

    def test_solo_hay_una_tarifa_general_vigente_por_servicio_y_la_nueva_cierra_la_anterior(self):
        datos = self.datos_tarifa()
        del datos["tipo_prenda"]
        self.client.post("/api/catalogo/tarifas", datos)
        datos.update(valor_base="9000", vigente_desde="2026-06-01")
        self.assertEqual(self.client.post("/api/catalogo/tarifas", datos).status_code, 201)
        generales = Tarifa.objects.filter(tipo_prenda__isnull=True, vigente_hasta__isnull=True)
        self.assertEqual([t.valor_base for t in generales], [Decimal("9000.00")])

    def test_la_base_de_datos_rechaza_dos_generales_vigentes_del_mismo_servicio(self):
        Tarifa.objects.create(
            servicio=self.lavado, valor_base=1, precio_por_kilo=1, plazo_entrega_dias=1, vigente_desde=date(2026, 1, 1)
        )
        with self.assertRaises(IntegrityError):
            Tarifa.objects.create(
                servicio=self.lavado, valor_base=2, precio_por_kilo=2, plazo_entrega_dias=1, vigente_desde=date(2026, 2, 1)
            )

    def test_rechaza_un_precio_por_kilo_negativo(self):
        response = self.client.post("/api/catalogo/tarifas", self.datos_tarifa(precio_por_kilo="-1"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("precio_por_kilo", response.json())

    def test_edita_el_precio_por_kilo_de_la_tarifa_vigente(self):
        tarifa_id = self.client.post(
            "/api/catalogo/tarifas", self.datos_tarifa(precio_por_kilo="8000")
        ).json()["id"]
        response = self.client.patch(
            f"/api/catalogo/tarifas/{tarifa_id}", {"precio_por_kilo": "9000"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Tarifa.objects.get(pk=tarifa_id).precio_por_kilo, Decimal("9000.00"))


class NivelDificultadYMaterialTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="x", rol=User.Rol.ADMINISTRADOR)
        self.client.force_authenticate(self.admin)
        self.facil = NivelDificultad.objects.create(nombre="Facil", factor=Decimal("1.00"))

    def test_crea_edita_y_renombra_un_nivel(self):
        creado = self.client.post("/api/catalogo/niveles-dificultad", {"nombre": "Experto", "factor": "1.30"})
        self.assertEqual(creado.status_code, 201, creado.json())
        nivel_id = creado.json()["id"]
        editado = self.client.patch(
            f"/api/catalogo/niveles-dificultad/{nivel_id}",
            {"nombre": "Intermedio", "factor": "1.40"},
            format="json",
        )
        self.assertEqual(editado.status_code, 200)
        nivel = NivelDificultad.objects.get(pk=nivel_id)
        self.assertEqual((nivel.nombre, nivel.factor, nivel.creado_por), ("Intermedio", Decimal("1.40"), self.admin))

    def test_el_factor_debe_ser_mayor_que_cero(self):
        antes = NivelDificultad.objects.count()
        for factor in ("0", "-1", "0.00", ""):
            with self.subTest(factor=factor):
                response = self.client.post(
                    "/api/catalogo/niveles-dificultad", {"nombre": f"N{factor}", "factor": factor}
                )
                self.assertEqual(response.status_code, 400)
        self.assertEqual(NivelDificultad.objects.count(), antes)

    def test_rechaza_un_nivel_repetido_sin_importar_mayusculas(self):
        response = self.client.post("/api/catalogo/niveles-dificultad", {"nombre": "FACIL", "factor": "2"})
        self.assertEqual(response.status_code, 400)

    def test_el_material_exige_nivel_y_muestra_su_factor(self):
        sin_nivel = self.client.post("/api/catalogo/materiales", {"nombre": "Lino"})
        self.assertEqual(sin_nivel.status_code, 400)
        self.assertIn("nivel_dificultad", sin_nivel.json())

        response = self.client.post(
            "/api/catalogo/materiales", {"nombre": "Lino", "nivel_dificultad": self.facil.pk}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["nivel_dificultad_nombre"], "Facil")
        self.assertEqual(response.json()["factor"], "1.00")

    def test_cambiar_el_factor_del_nivel_cambia_el_factor_de_sus_materiales(self):
        Material.objects.create(nombre="Jean", nivel_dificultad=self.facil)
        self.client.patch(
            f"/api/catalogo/niveles-dificultad/{self.facil.pk}", {"factor": "1.10"}, format="json"
        )
        self.assertEqual(self.client.get("/api/catalogo/materiales").json()[0]["factor"], "1.10")

    def test_un_nivel_con_materiales_no_se_puede_eliminar(self):
        Material.objects.create(nombre="Jean", nivel_dificultad=self.facil)
        response = self.client.delete(f"/api/catalogo/niveles-dificultad/{self.facil.pk}")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(NivelDificultad.objects.filter(pk=self.facil.pk).exists())
        with self.assertRaises(ProtectedError):
            self.facil.delete()

    def test_un_nivel_sin_materiales_se_elimina(self):
        self.assertEqual(self.client.delete(f"/api/catalogo/niveles-dificultad/{self.facil.pk}").status_code, 204)

    def test_el_tipo_de_prenda_guarda_su_peso_estandar_y_lo_exige_positivo(self):
        creado = self.client.post("/api/catalogo/tipos-prenda", {"nombre": "Cobija", "peso_estandar": "2.5"})
        self.assertEqual(creado.status_code, 201)
        self.assertEqual(creado.json()["peso_estandar"], "2.50")
        malo = self.client.post("/api/catalogo/tipos-prenda", {"nombre": "Saco", "peso_estandar": "0"})
        self.assertEqual(malo.status_code, 400)
        sin_peso = self.client.post("/api/catalogo/tipos-prenda", {"nombre": "Falda"})
        self.assertEqual(sin_peso.status_code, 201)
        self.assertIsNone(sin_peso.json()["peso_estandar"])

    def test_recepcion_y_operario_no_escriben_niveles_pero_si_los_consultan(self):
        for rol in (User.Rol.RECEPCIONISTA, User.Rol.OPERARIO):
            self.client.force_authenticate(User.objects.create_user(username=f"u-{rol}", password="x", rol=rol))
            self.assertEqual(self.client.get("/api/catalogo/niveles-dificultad").status_code, 200)
            self.assertEqual(
                self.client.post("/api/catalogo/niveles-dificultad", {"nombre": "X", "factor": "2"}).status_code, 403
            )
            self.assertEqual(
                self.client.patch(
                    f"/api/catalogo/niveles-dificultad/{self.facil.pk}", {"factor": "9"}, format="json"
                ).status_code,
                403,
            )
            self.assertEqual(self.client.delete(f"/api/catalogo/niveles-dificultad/{self.facil.pk}").status_code, 403)
        self.facil.refresh_from_db()
        self.assertEqual(self.facil.factor, Decimal("1.00"))


class CatalogoPermisosTests(APITestCase):
    def setUp(self):
        User.objects.create_user(
            username="admin", password="smartwash123", rol=User.Rol.ADMINISTRADOR
        )
        User.objects.create_user(
            username="recepcion", password="smartwash123", rol=User.Rol.RECEPCIONISTA
        )
        self.camisa = TipoPrenda.objects.create(nombre="Camisa")
        self.lavado = Servicio.objects.create(nombre="Lavado")
        self.tarifa = Tarifa.objects.create(
            tipo_prenda=self.camisa,
            servicio=self.lavado,
            valor_base="8000.00",
            precio_por_kilo="0",
            plazo_entrega_dias=2,
            vigente_desde="2026-01-01",
        )
        self.client.login(username="recepcion", password="smartwash123")

    def test_el_recepcionista_consulta_el_catalogo(self):
        for ruta in ("tipos-prenda", "servicios", "tarifas"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(f"/api/catalogo/{ruta}").status_code, 200)
        self.assertEqual(self.client.get(f"/api/catalogo/tarifas/{self.tarifa.pk}").status_code, 200)

    def test_el_recepcionista_no_crea_nada_en_el_catalogo(self):
        creaciones = {
            "tipos-prenda": {"nombre": "Cobija"},
            "servicios": {"nombre": "Planchado"},
            "tarifas": {
                "tipo_prenda": self.camisa.pk,
                "servicio": self.lavado.pk,
                "valor_base": "9000.00",
                "precio_por_kilo": "0",
                "plazo_entrega_dias": 2,
                "vigente_desde": "2026-06-01",
            },
        }
        for ruta, datos in creaciones.items():
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.post(f"/api/catalogo/{ruta}", datos).status_code, 403)
        self.assertEqual(TipoPrenda.objects.count(), 1)
        self.assertEqual(Servicio.objects.count(), 1)
        self.assertEqual(Tarifa.objects.count(), 1)

    def test_el_recepcionista_no_edita_el_catalogo(self):
        ediciones = {
            f"tipos-prenda/{self.camisa.pk}": {"nombre": "Otra"},
            f"servicios/{self.lavado.pk}": {"nombre": "Otro"},
            f"tarifas/{self.tarifa.pk}": {"valor_base": "1.00"},
        }
        for ruta, datos in ediciones.items():
            with self.subTest(ruta=ruta):
                self.assertEqual(
                    self.client.patch(f"/api/catalogo/{ruta}", datos, format="json").status_code, 403
                )
        self.tarifa.refresh_from_db()
        self.assertEqual(self.tarifa.valor_base, Decimal("8000.00"))

    def test_el_administrador_si_escribe_en_el_catalogo(self):
        self.client.login(username="admin", password="smartwash123")
        response = self.client.post("/api/catalogo/servicios", {"nombre": "Planchado"})
        self.assertEqual(response.status_code, 201)


class BloqueoDeTarifaVigenteTests(APITestCase):
    """PostgreSQL no admite FOR UPDATE sobre el lado nulable de un LEFT JOIN, y el
    orden por defecto de Tarifa (tipo_prenda__nombre) lo genera si tipo_prenda es nulo.
    SQLite ignora el bloqueo: estas pruebas solo detectan el 500 corriendo contra PostgreSQL
    (DATABASE_URL=postgres://...), pero la comprobacion del SQL vale en cualquier base."""

    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="x", rol=User.Rol.ADMINISTRADOR)
        self.client.force_authenticate(self.admin)
        self.lavado = Servicio.objects.create(nombre="Lavado")
        self.camisa = TipoPrenda.objects.create(nombre="Camisa")

    def datos(self, tipo=None, **extra):
        datos = {
            "servicio": self.lavado.pk,
            "valor_base": "5000",
            "precio_por_kilo": "8000",
            "plazo_entrega_dias": 2,
            "vigente_desde": "2026-01-01",
        }
        if tipo is not None:
            datos["tipo_prenda"] = tipo.pk
        datos.update(extra)
        return datos

    def test_la_consulta_de_bloqueo_no_lleva_joins_ni_orden(self):
        for tipo in (None, self.camisa):
            with self.subTest(tipo=tipo):
                consulta = TarifaSerializer.tarifa_vigente_a_bloquear(tipo, self.lavado)
                self.assertNotIn("JOIN", str(consulta.query).upper())
                self.assertNotIn("ORDER BY", str(consulta.query).upper())

    def test_el_bloqueo_que_se_ejecuta_no_lleva_joins(self):
        with CaptureQueriesContext(connection) as consultas:
            self.client.post("/api/catalogo/tarifas", self.datos())
            self.client.post("/api/catalogo/tarifas", self.datos(valor_base="6000", vigente_desde="2026-06-01"))
        bloqueos = [q["sql"] for q in consultas if "FOR UPDATE" in q["sql"].upper()]
        if connection.features.has_select_for_update:
            self.assertTrue(bloqueos)
        for sql in bloqueos:
            self.assertNotIn("JOIN", sql.upper())

    def test_crea_una_tarifa_general_y_otra_que_cierra_la_anterior(self):
        primera = self.client.post("/api/catalogo/tarifas", self.datos())
        self.assertEqual(primera.status_code, 201, primera.content)
        segunda = self.client.post(
            "/api/catalogo/tarifas", self.datos(valor_base="6000", vigente_desde="2026-06-01")
        )
        self.assertEqual(segunda.status_code, 201, segunda.content)
        anterior = Tarifa.objects.get(pk=primera.json()["id"])
        self.assertEqual(anterior.vigente_hasta, date(2026, 6, 1))
        generales = Tarifa.objects.filter(tipo_prenda__isnull=True, vigente_hasta__isnull=True)
        self.assertEqual([t.valor_base for t in generales], [Decimal("6000.00")])

    def test_crea_una_excepcion_por_tipo_y_otra_que_cierra_la_anterior(self):
        self.assertEqual(self.client.post("/api/catalogo/tarifas", self.datos(self.camisa)).status_code, 201)
        segunda = self.client.post(
            "/api/catalogo/tarifas", self.datos(self.camisa, valor_base="6000", vigente_desde="2026-06-01")
        )
        self.assertEqual(segunda.status_code, 201, segunda.content)
        self.assertEqual(Tarifa.objects.filter(tipo_prenda=self.camisa, vigente_hasta__isnull=True).count(), 1)


class ListaTarifasPaginadaApiTests(APITestCase):
    url = "/api/catalogo/tarifas"

    def setUp(self):
        self.client.force_authenticate(
            get_user_model().objects.create_user(username="jefe", password="x", rol="administrador")
        )
        self.lavado = Servicio.objects.create(nombre="Lavado")
        self.planchado = Servicio.objects.create(nombre="Planchado")
        self.camisa = TipoPrenda.objects.create(nombre="Camisa")

    def tarifa(self, servicio, tipo=None, vigente_hasta=None):
        return Tarifa.objects.create(
            servicio=servicio,
            tipo_prenda=tipo,
            valor_base=Decimal("5000"),
            precio_por_kilo=Decimal("0"),
            plazo_entrega_dias=1,
            vigente_desde=date(2020, 1, 1),
            vigente_hasta=vigente_hasta,
        )

    def ids(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return [t["id"] for t in response.json()["resultados"]]

    def test_sin_parametros_responde_la_lista_completa_como_antes(self):
        self.tarifa(self.lavado)

        self.assertIsInstance(self.client.get(self.url).json(), list)

    def test_pagina_conservando_el_orden_por_servicio_y_tipo(self):
        planchado = self.tarifa(self.planchado)
        lavado_camisa = self.tarifa(self.lavado, self.camisa)
        lavado = self.tarifa(self.lavado)

        datos = self.client.get(self.url, {"tamano": 2}).json()

        self.assertEqual((datos["total"], datos["paginas"]), (3, 2))
        self.assertEqual(self.ids(tamano=2), [lavado.pk, lavado_camisa.pk])
        self.assertEqual(self.ids(tamano=2, pagina=2), [planchado.pk])
        self.assertEqual(self.ids(pagina=5), [])
        self.assertEqual(self.client.get(self.url, {"tamano": 500}).json()["tamano"], 100)
        self.assertEqual(self.client.get(self.url, {"pagina": "0"}).status_code, 400)

    def test_busca_por_servicio_y_tipo_de_prenda_y_conserva_vigentes(self):
        lavado_camisa = self.tarifa(self.lavado, self.camisa)
        self.tarifa(self.lavado, self.camisa, vigente_hasta=date(2021, 1, 1))
        planchado = self.tarifa(self.planchado)

        self.assertEqual(self.ids(buscar="lavado camisa", vigentes=1), [lavado_camisa.pk])
        self.assertEqual(self.ids(buscar="PLANCH"), [planchado.pk])
        self.assertEqual(len(self.ids(buscar="camisa")), 2)
