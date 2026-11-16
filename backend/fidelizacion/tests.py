from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from clientes.models import Cliente

from .models import Promocion, ReglaDescuento, puntos_por_consumo

User = get_user_model()


class ReglaDescuentoModelTests(TestCase):
    def crear_regla(self, tipo="porcentaje", valor="10", **extra):
        datos = {
            "nombre": "Descuento clientes VIP",
            "tipo": tipo,
            "valor": valor,
            "vigente_desde": date(2026, 1, 1),
        }
        datos.update(extra)
        return ReglaDescuento.objects.create(**datos)

    def test_un_descuento_porcentual_no_puede_superar_cien(self):
        with self.assertRaises(IntegrityError):
            self.crear_regla(tipo="porcentaje", valor="150")

    def test_un_monto_fijo_puede_superar_cien(self):
        regla = self.crear_regla(tipo="monto_fijo", valor="15000")
        regla.refresh_from_db()
        self.assertEqual(regla.valor, Decimal("15000"))

    def test_rechaza_un_valor_negativo(self):
        with self.assertRaises(IntegrityError):
            self.crear_regla(valor="-10")

    def test_rechaza_una_vigencia_que_termina_antes_de_empezar(self):
        with self.assertRaises(IntegrityError):
            self.crear_regla(
                vigente_desde=date(2026, 6, 1), vigente_hasta=date(2026, 1, 1)
            )


class ReglaDescuentoApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin", password="smartwash123", rol=User.Rol.ADMINISTRADOR
        )
        self.client.login(username="admin", password="smartwash123")

    def datos_validos(self, **extra):
        datos = {
            "nombre": "Descuento clientes frecuentes",
            "tipo": "porcentaje",
            "valor": "10.00",
            "clasificacion_cliente": "Frecuente",
            "activa": True,
            "vigente_desde": "2026-01-01",
        }
        datos.update(extra)
        return datos

    def test_crea_una_regla_de_descuento(self):
        response = self.client.post("/api/fidelizacion/reglas-descuento", self.datos_validos())
        self.assertEqual(response.status_code, 201)
        regla = ReglaDescuento.objects.get(nombre="Descuento clientes frecuentes")
        self.assertEqual(regla.creado_por, self.admin)
        self.assertTrue(regla.activa)

    def test_rechaza_un_porcentaje_mayor_a_cien(self):
        response = self.client.post(
            "/api/fidelizacion/reglas-descuento", self.datos_validos(valor="150")
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(ReglaDescuento.objects.exists())

    def test_un_monto_fijo_mayor_a_cien_si_se_acepta(self):
        response = self.client.post(
            "/api/fidelizacion/reglas-descuento",
            self.datos_validos(tipo="monto_fijo", valor="20000"),
        )
        self.assertEqual(response.status_code, 201)

    def test_lista_las_reglas_creadas(self):
        self.client.post("/api/fidelizacion/reglas-descuento", self.datos_validos())
        response = self.client.get("/api/fidelizacion/reglas-descuento")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)

    def test_edita_una_regla_existente(self):
        creacion = self.client.post("/api/fidelizacion/reglas-descuento", self.datos_validos())
        regla_id = creacion.json()["id"]
        response = self.client.patch(
            f"/api/fidelizacion/reglas-descuento/{regla_id}",
            {"activa": False},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        regla = ReglaDescuento.objects.get(pk=regla_id)
        self.assertFalse(regla.activa)
        self.assertEqual(regla.actualizado_por, self.admin)

    def test_editar_a_un_porcentaje_mayor_a_cien_se_rechaza(self):
        creacion = self.client.post("/api/fidelizacion/reglas-descuento", self.datos_validos())
        regla_id = creacion.json()["id"]
        response = self.client.patch(
            f"/api/fidelizacion/reglas-descuento/{regla_id}",
            {"valor": "120"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_rechaza_un_valor_negativo_con_mensaje_y_no_con_error_500(self):
        response = self.client.post(
            "/api/fidelizacion/reglas-descuento", self.datos_validos(valor="-5")
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("valor", response.json())
        self.assertFalse(ReglaDescuento.objects.exists())

    def test_rechaza_una_vigencia_que_termina_antes_de_empezar(self):
        response = self.client.post(
            "/api/fidelizacion/reglas-descuento",
            self.datos_validos(vigente_desde="2026-06-01", vigente_hasta="2026-01-01"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("vigente_hasta", response.json())

    def test_editar_solo_el_fin_de_vigencia_a_una_fecha_anterior_se_rechaza(self):
        creacion = self.client.post("/api/fidelizacion/reglas-descuento", self.datos_validos())
        response = self.client.patch(
            f"/api/fidelizacion/reglas-descuento/{creacion.json()['id']}",
            {"vigente_hasta": "2025-12-31"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_requiere_sesion_activa(self):
        self.client.logout()
        response = self.client.post("/api/fidelizacion/reglas-descuento", self.datos_validos())
        self.assertEqual(response.status_code, 403)


PROMOCIONES = "/api/fidelizacion/promociones"


class PromocionApiTests(APITestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        User.objects.create_user(username="admin", password="x", rol=User.Rol.ADMINISTRADOR)
        self.client.login(username="admin", password="x")

    def datos(self, **extra):
        datos = {
            "nombre": "Semana VIP",
            "descripcion": "Campana de fin de mes",
            "tipo": "porcentaje",
            "valor": "15.00",
            "segmentos": ["VIP", "Frecuente"],
            "vigente_desde": str(self.hoy - timedelta(days=1)),
            "vigente_hasta": str(self.hoy + timedelta(days=10)),
        }
        datos.update(extra)
        return datos

    def crear(self, **extra):
        return self.client.post(PROMOCIONES, self.datos(**extra), format="json")

    def cliente(self, clasificacion, documento="100"):
        return Cliente.objects.create(
            documento=documento, nombre_completo="Cliente", telefono="300", clasificacion=clasificacion
        )

    def test_crea_la_promocion_con_vigencia_y_segmentos_y_queda_disponible(self):
        response = self.crear()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["segmentos"], ["Frecuente", "VIP"])
        self.assertTrue(response.json()["disponible"])
        promocion = Promocion.objects.get()
        self.assertTrue(promocion.activa)
        self.assertEqual(promocion.creado_por.username, "admin")

    def test_la_vigencia_exige_fecha_de_inicio_y_de_fin(self):
        for campo in ("vigente_desde", "vigente_hasta"):
            with self.subTest(campo=campo):
                datos = self.datos()
                del datos[campo]
                response = self.client.post(PROMOCIONES, datos, format="json")

                self.assertEqual(response.status_code, 400)
                self.assertIn(campo, response.json())
        self.assertFalse(Promocion.objects.exists())

    def test_rechaza_una_vigencia_que_termina_antes_de_empezar(self):
        response = self.crear(
            vigente_desde=str(self.hoy), vigente_hasta=str(self.hoy - timedelta(days=1))
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("vigente_hasta", response.json())

    def test_una_promocion_de_un_solo_dia_es_valida(self):
        response = self.crear(vigente_desde=str(self.hoy), vigente_hasta=str(self.hoy))

        self.assertEqual(response.status_code, 201)

    def test_exige_al_menos_un_segmento_y_que_exista(self):
        for segmentos in ([], ["Platino"]):
            with self.subTest(segmentos=segmentos):
                response = self.crear(segmentos=segmentos)

                self.assertEqual(response.status_code, 400)
                self.assertIn("segmentos", response.json())
        self.assertFalse(Promocion.objects.exists())

    def test_un_segmento_repetido_se_guarda_una_sola_vez(self):
        response = self.crear(segmentos=["VIP", "VIP"])

        self.assertEqual(response.json()["segmentos"], ["VIP"])

    def test_rechaza_un_porcentaje_mayor_a_cien_y_un_valor_negativo(self):
        for valor in ("101", "-1"):
            with self.subTest(valor=valor):
                response = self.crear(valor=valor)

                self.assertEqual(response.status_code, 400)
                self.assertIn("valor", response.json())

    def test_un_monto_fijo_puede_superar_cien(self):
        self.assertEqual(self.crear(tipo="monto_fijo", valor="20000").status_code, 201)

    def test_una_peticion_invalida_no_deja_cambios(self):
        creada = self.crear().json()

        self.client.patch(
            f"{PROMOCIONES}/{creada['id']}",
            {"nombre": "Otro", "segmentos": ["Platino"]},
            format="json",
        )

        promocion = Promocion.objects.get()
        self.assertEqual(promocion.nombre, "Semana VIP")
        self.assertEqual(promocion.clasificaciones, ["Frecuente", "VIP"])

    def test_edita_los_datos_y_reemplaza_los_segmentos(self):
        creada = self.crear().json()

        response = self.client.patch(
            f"{PROMOCIONES}/{creada['id']}",
            {"valor": "20", "segmentos": ["Ocasional", "VIP"]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["segmentos"], ["Ocasional", "VIP"])
        promocion = Promocion.objects.get()
        self.assertEqual(promocion.valor, Decimal("20"))
        self.assertEqual(promocion.actualizado_por.username, "admin")

    def test_editar_el_fin_a_una_fecha_anterior_al_inicio_guardado_se_rechaza(self):
        creada = self.crear().json()

        response = self.client.patch(
            f"{PROMOCIONES}/{creada['id']}",
            {"vigente_hasta": str(self.hoy - timedelta(days=5))},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_desactivar_la_promocion_la_saca_de_las_disponibles(self):
        creada = self.crear().json()
        cliente = self.cliente("VIP")

        self.client.patch(f"{PROMOCIONES}/{creada['id']}", {"activa": False}, format="json")

        disponibles = self.client.get(f"{PROMOCIONES}/disponibles?cliente={cliente.id}")
        self.assertEqual(disponibles.json(), [])
        self.assertFalse(self.client.get(f"{PROMOCIONES}/{creada['id']}").json()["disponible"])

    def test_lista_las_promociones_creadas(self):
        self.crear()
        self.crear(nombre="Otra")

        response = self.client.get(PROMOCIONES)

        self.assertEqual(len(response.json()), 2)

    def test_no_se_puede_borrar_una_promocion(self):
        creada = self.crear().json()

        response = self.client.delete(f"{PROMOCIONES}/{creada['id']}")

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Promocion.objects.exists())

    def test_disponibles_solo_incluye_las_del_segmento_del_cliente(self):
        self.crear(nombre="Para VIP", segmentos=["VIP"])
        self.crear(nombre="Para ocasionales", segmentos=["Ocasional"])
        vip = self.cliente("VIP")

        response = self.client.get(f"{PROMOCIONES}/disponibles?cliente={vip.id}")

        self.assertEqual([p["nombre"] for p in response.json()], ["Para VIP"])

    def test_disponibles_excluye_las_vencidas_y_las_que_aun_no_empiezan(self):
        self.crear(
            nombre="Vencida",
            vigente_desde=str(self.hoy - timedelta(days=9)),
            vigente_hasta=str(self.hoy - timedelta(days=1)),
        )
        self.crear(
            nombre="Futura",
            vigente_desde=str(self.hoy + timedelta(days=1)),
            vigente_hasta=str(self.hoy + timedelta(days=9)),
        )
        self.crear(nombre="Vigente hasta hoy", vigente_hasta=str(self.hoy))
        vip = self.cliente("VIP")

        response = self.client.get(f"{PROMOCIONES}/disponibles?cliente={vip.id}")

        self.assertEqual([p["nombre"] for p in response.json()], ["Vigente hasta hoy"])

    def test_disponibles_exige_un_cliente_que_exista(self):
        self.assertEqual(self.client.get(f"{PROMOCIONES}/disponibles").status_code, 400)
        self.assertEqual(self.client.get(f"{PROMOCIONES}/disponibles?cliente=999999").status_code, 404)

    def test_solo_el_administrador_gestiona_promociones(self):
        creada = self.crear().json()
        cliente = self.cliente("VIP")
        for rol in (User.Rol.RECEPCIONISTA, User.Rol.OPERARIO):
            with self.subTest(rol=rol):
                User.objects.create_user(username=f"u-{rol}", password="x", rol=rol)
                self.client.login(username=f"u-{rol}", password="x")

                self.assertEqual(self.client.get(PROMOCIONES).status_code, 403)
                self.assertEqual(self.client.post(PROMOCIONES, self.datos(), format="json").status_code, 403)
                self.assertEqual(self.client.get(f"{PROMOCIONES}/{creada['id']}").status_code, 403)
                self.assertEqual(
                    self.client.patch(f"{PROMOCIONES}/{creada['id']}", {"activa": False}, format="json").status_code,
                    403,
                )
        self.assertEqual(Promocion.objects.count(), 1)
        self.assertTrue(Promocion.objects.get().activa)

        self.client.login(username=f"u-{User.Rol.RECEPCIONISTA}", password="x")
        self.assertEqual(self.client.get(f"{PROMOCIONES}/disponibles?cliente={cliente.id}").status_code, 200)
        self.client.login(username=f"u-{User.Rol.OPERARIO}", password="x")
        self.assertEqual(self.client.get(f"{PROMOCIONES}/disponibles?cliente={cliente.id}").status_code, 403)

    def test_requiere_sesion_activa(self):
        self.client.logout()

        self.assertEqual(self.client.get(PROMOCIONES).status_code, 403)
        self.assertEqual(self.client.post(PROMOCIONES, self.datos(), format="json").status_code, 403)


class PromocionDescuentoTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.vip = Cliente.objects.create(
            documento="1", nombre_completo="Vip", telefono="300", clasificacion="VIP"
        )

    def promocion(self, segmentos=("VIP",), **extra):
        datos = {
            "nombre": "Promo", "tipo": "porcentaje", "valor": 10,
            "vigente_desde": self.hoy, "vigente_hasta": self.hoy + timedelta(days=5),
        }
        datos.update(extra)
        promocion = Promocion.objects.create(**datos)
        for clasificacion in segmentos:
            promocion.segmentos.create(clasificacion=clasificacion)
        return promocion

    def test_aplica_solo_la_promocion_que_mas_descuenta(self):
        self.promocion(nombre="Diez", valor=10)
        self.promocion(nombre="Fijo", tipo="monto_fijo", valor=5000)

        descuento = Promocion.objects.mayor_descuento(self.vip, Decimal("20000"), self.hoy)

        self.assertEqual(descuento, Decimal("5000"))

    def test_un_monto_fijo_no_supera_el_monto_de_la_orden(self):
        self.promocion(tipo="monto_fijo", valor=50000)

        self.assertEqual(
            Promocion.objects.mayor_descuento(self.vip, Decimal("20000"), self.hoy), Decimal("20000")
        )

    def test_sin_promocion_aplicable_el_descuento_es_cero(self):
        self.promocion(segmentos=("Ocasional",))

        self.assertEqual(
            Promocion.objects.mayor_descuento(self.vip, Decimal("20000"), self.hoy), Decimal("0")
        )


class PuntosPorConsumoTests(SimpleTestCase):
    def test_un_punto_por_cada_mil_pesos_sin_contar_la_fraccion(self):
        for valor, puntos in (("16000", 16), ("15900.50", 15), ("999", 0), ("0", 0)):
            with self.subTest(valor=valor):
                self.assertEqual(puntos_por_consumo(Decimal(valor)), puntos)

    @override_settings(PUNTOS_CADA_PESOS=Decimal("500"))
    def test_la_equivalencia_se_configura(self):
        self.assertEqual(puntos_por_consumo(Decimal("16000")), 32)
