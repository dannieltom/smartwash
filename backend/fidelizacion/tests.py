from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APITestCase

from .models import ReglaDescuento, puntos_por_consumo

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


class PuntosPorConsumoTests(SimpleTestCase):
    def test_un_punto_por_cada_mil_pesos_sin_contar_la_fraccion(self):
        for valor, puntos in (("16000", 16), ("15900.50", 15), ("999", 0), ("0", 0)):
            with self.subTest(valor=valor):
                self.assertEqual(puntos_por_consumo(Decimal(valor)), puntos)

    @override_settings(PUNTOS_CADA_PESOS=Decimal("500"))
    def test_la_equivalencia_se_configura(self):
        self.assertEqual(puntos_por_consumo(Decimal("16000")), 32)
