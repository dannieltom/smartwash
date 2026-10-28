from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from rest_framework.test import APITestCase

from .models import Cliente

User = get_user_model()


class ClienteTests(TestCase):
    def test_no_admite_dos_clientes_con_el_mismo_documento(self):
        Cliente.objects.create(
            documento="1090123456", nombre_completo="Ana Gomez", telefono="3001112233"
        )
        with self.assertRaises(IntegrityError):
            Cliente.objects.create(
                documento="1090123456", nombre_completo="Otro", telefono="3004445566"
            )

    def test_nace_clasificado_como_ocasional(self):
        cliente = Cliente.objects.create(
            documento="1090123456", nombre_completo="Ana Gomez", telefono="3001112233"
        )
        self.assertEqual(cliente.clasificacion, Cliente.Clasificacion.OCASIONAL)


class ClienteApiTests(APITestCase):
    def setUp(self):
        self.recepcion = User.objects.create_user(
            username="recepcion", password="smartwash123", rol=User.Rol.RECEPCIONISTA
        )
        self.client.login(username="recepcion", password="smartwash123")
        self.ana = Cliente.objects.create(
            documento="1090123456", nombre_completo="Ana Gomez", telefono="3001112233"
        )

    def datos_cliente(self, **extra):
        datos = {
            "nombre_completo": "Luis Perez",
            "documento": "1090999888",
            "telefono": "3157778899",
            "correo": "luis@correo.test",
        }
        datos.update(extra)
        return datos

    def test_registra_un_cliente_y_lo_deja_como_ocasional(self):
        response = self.client.post("/api/clientes", self.datos_cliente())
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["clasificacion"], "Ocasional")
        self.assertTrue(Cliente.objects.filter(documento="1090999888").exists())

    def test_registra_el_cliente_sin_correo(self):
        response = self.client.post("/api/clientes", self.datos_cliente(correo=""))
        self.assertEqual(response.status_code, 201)

    def test_registra_quien_creo_y_quien_edito_al_cliente(self):
        self.client.post("/api/clientes", self.datos_cliente())
        luis = Cliente.objects.get(documento="1090999888")
        self.assertEqual(luis.creado_por, self.recepcion)

        admin = User.objects.create_user(
            username="admin", password="smartwash123", rol=User.Rol.ADMINISTRADOR
        )
        self.client.login(username="admin", password="smartwash123")
        self.client.patch(
            f"/api/clientes/{luis.pk}", {"telefono": "3000000000"}, content_type="application/json"
        )
        luis.refresh_from_db()
        self.assertEqual(luis.creado_por, self.recepcion)
        self.assertEqual(luis.actualizado_por, admin)

    def test_edita_los_datos_de_un_cliente(self):
        response = self.client.patch(
            f"/api/clientes/{self.ana.pk}",
            {"telefono": "3219998877", "correo": "ana@correo.test"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.telefono, "3219998877")
        self.assertEqual(self.ana.correo, "ana@correo.test")
        self.assertEqual(self.ana.actualizado_por, self.recepcion)

    def test_editar_sin_cambiar_el_documento_no_lo_cuenta_como_duplicado(self):
        response = self.client.patch(
            f"/api/clientes/{self.ana.pk}",
            {"documento": "1090123456", "nombre_completo": "Ana M. Gomez"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

    def test_rechaza_un_documento_duplicado(self):
        response = self.client.post("/api/clientes", self.datos_cliente(documento="1090123456"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("documento", response.json())
        self.assertEqual(Cliente.objects.count(), 1)

    def test_el_documento_duplicado_se_detecta_aunque_cambien_los_espacios(self):
        response = self.client.post(
            "/api/clientes", self.datos_cliente(documento=" 1090 123 456 ")
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("documento", response.json())

    def test_normaliza_los_espacios_al_guardar(self):
        self.client.post(
            "/api/clientes",
            self.datos_cliente(documento=" 1090 999 888 ", nombre_completo="  Luis   Perez "),
        )
        luis = Cliente.objects.get(documento="1090999888")
        self.assertEqual(luis.nombre_completo, "Luis Perez")

    def test_rechaza_editar_con_el_documento_de_otro_cliente(self):
        luis = Cliente.objects.create(
            documento="1090999888", nombre_completo="Luis Perez", telefono="3157778899"
        )
        response = self.client.patch(
            f"/api/clientes/{luis.pk}",
            {"documento": "1090123456", "telefono": "3000000000"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        luis.refresh_from_db()
        self.assertEqual(luis.documento, "1090999888")
        self.assertEqual(luis.telefono, "3157778899")

    def test_una_edicion_invalida_no_cambia_nada(self):
        response = self.client.patch(
            f"/api/clientes/{self.ana.pk}",
            {"nombre_completo": "Otro Nombre", "correo": "no-es-un-correo"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.nombre_completo, "Ana Gomez")
        self.assertIsNone(self.ana.actualizado_por)

    def test_la_clasificacion_es_de_solo_lectura(self):
        self.client.post("/api/clientes", self.datos_cliente(clasificacion="VIP"))
        self.assertEqual(
            Cliente.objects.get(documento="1090999888").clasificacion,
            Cliente.Clasificacion.OCASIONAL,
        )
        self.client.patch(
            f"/api/clientes/{self.ana.pk}", {"clasificacion": "VIP"}, content_type="application/json"
        )
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.clasificacion, Cliente.Clasificacion.OCASIONAL)

    def test_el_saldo_de_puntos_se_muestra_y_es_de_solo_lectura(self):
        Cliente.objects.filter(pk=self.ana.pk).update(puntos=16)
        detalle = self.client.get(f"/api/clientes/{self.ana.pk}")
        self.assertEqual(detalle.json()["puntos"], 16)
        lista = self.client.get("/api/clientes")
        self.assertEqual([c["puntos"] for c in lista.json()], [16])

        self.client.patch(
            f"/api/clientes/{self.ana.pk}", {"puntos": 9999}, content_type="application/json"
        )
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.puntos, 16)

        self.client.post("/api/clientes", self.datos_cliente(puntos=500))
        self.assertEqual(Cliente.objects.get(documento="1090999888").puntos, 0)

    def test_lista_y_consulta_clientes(self):
        lista = self.client.get("/api/clientes")
        self.assertEqual(lista.status_code, 200)
        self.assertEqual([c["documento"] for c in lista.json()], ["1090123456"])
        detalle = self.client.get(f"/api/clientes/{self.ana.pk}")
        self.assertEqual(detalle.json()["nombre_completo"], "Ana Gomez")

    def test_no_permite_borrar_clientes(self):
        response = self.client.delete(f"/api/clientes/{self.ana.pk}")
        self.assertEqual(response.status_code, 405)
        self.assertTrue(Cliente.objects.filter(pk=self.ana.pk).exists())

    def test_exige_sesion(self):
        self.client.logout()
        self.assertEqual(self.client.get("/api/clientes").status_code, 403)
        self.assertEqual(self.client.post("/api/clientes", self.datos_cliente()).status_code, 403)
        self.assertEqual(self.client.get(f"/api/clientes/{self.ana.pk}").status_code, 403)
        self.assertEqual(
            self.client.patch(
                f"/api/clientes/{self.ana.pk}", {"telefono": "1"}, content_type="application/json"
            ).status_code,
            403,
        )
        self.assertEqual(Cliente.objects.count(), 1)
