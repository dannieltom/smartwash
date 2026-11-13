from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework.throttling import SimpleRateThrottle

from clientes.models import Cliente
from core.pruebas import PruebasDeListaMixin
from ordenes.models import Orden

from .models import Calificacion

User = get_user_model()


def crear_orden(codigo, estado=Orden.Estado.ENTREGADA, correo="ana@example.com"):
    recepcionista, _ = User.objects.get_or_create(username="recepcion", defaults={"rol": User.Rol.RECEPCIONISTA})
    cliente, _ = Cliente.objects.get_or_create(
        documento="1090123456",
        defaults={"nombre_completo": "Ana Gomez", "telefono": "3001112233", "correo": correo},
    )
    orden = Orden.objects.create(codigo=codigo, cliente=cliente, recepcionista=recepcionista)
    Orden.objects.filter(pk=orden.pk).update(estado=estado)
    orden.refresh_from_db()
    return orden


class CalificarOrdenApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.orden = crear_orden("SW-ABCD2345")

    def calificar(self, codigo="SW-ABCD2345", **datos):
        datos.setdefault("estrellas", 4)
        return self.client.post(f"/api/ordenes/consulta/{codigo}/calificacion", datos, format="json")

    def test_sin_sesion_califica_una_orden_entregada(self):
        response = self.calificar(estrellas=5, comentario="Muy bien")

        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json(), {"estrellas": 5, "comentario": "Muy bien"})
        calificacion = Calificacion.objects.get()
        self.assertEqual((calificacion.orden, calificacion.estrellas), (self.orden, 5))

    def test_el_comentario_es_opcional(self):
        response = self.calificar()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"estrellas": 4, "comentario": ""})

    def test_no_califica_una_orden_que_no_esta_entregada(self):
        for estado in Orden.Estado.values:
            if estado == Orden.Estado.ENTREGADA:
                continue
            with self.subTest(estado=estado):
                cache.clear()
                Orden.objects.filter(pk=self.orden.pk).update(estado=estado)

                response = self.calificar()

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {"detail": "Solo puedes calificar una orden ya entregada."})
        self.assertFalse(Calificacion.objects.exists())

    def test_una_orden_se_califica_una_sola_vez(self):
        self.calificar(estrellas=2)

        response = self.calificar(estrellas=5)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "Esta orden ya fue calificada."})
        self.assertEqual(Calificacion.objects.get().estrellas, 2)

    def test_las_estrellas_van_de_1_a_5(self):
        for estrellas in (0, 6, -1, "muchas", None):
            with self.subTest(estrellas=estrellas):
                response = self.calificar(estrellas=estrellas)

                self.assertEqual(response.status_code, 400)
                self.assertIn("estrellas", response.json())
        self.assertFalse(Calificacion.objects.exists())

    def test_el_comentario_no_pasa_de_500_caracteres(self):
        self.assertEqual(self.calificar(comentario="x" * 501).status_code, 400)
        self.assertEqual(self.calificar(comentario="x" * 500).status_code, 201)

    def test_un_codigo_inexistente_responde_404_con_el_mensaje_de_la_consulta(self):
        response = self.calificar(codigo="SW-ZZZZ9999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "No encontramos una orden con ese codigo. Revisa el comprobante."})

    def test_limita_los_intentos_por_codigo(self):
        with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {"calificar-orden-codigo": "2/hour"}):
            self.calificar(estrellas=0)
            self.calificar(estrellas=0)

            response = self.calificar()

        self.assertEqual(response.status_code, 429)
        self.assertFalse(Calificacion.objects.exists())

    def test_limita_los_intentos_por_ip(self):
        crear_orden("SW-OTRA0001")
        with mock.patch.dict(SimpleRateThrottle.THROTTLE_RATES, {"calificar-orden": "1/hour"}):
            self.calificar()

            response = self.calificar(codigo="SW-OTRA0001")

        self.assertEqual(response.status_code, 429)

    def test_exige_el_token_csrf_aunque_sea_publica(self):
        response = APIClient(enforce_csrf_checks=True).post(
            "/api/ordenes/consulta/SW-ABCD2345/calificacion", {"estrellas": 5}, format="json"
        )

        self.assertEqual(response.status_code, 403)

    def test_la_consulta_publica_incluye_la_calificacion(self):
        self.assertIsNone(self.client.get("/api/ordenes/consulta/SW-ABCD2345").json()["calificacion"])
        self.calificar(estrellas=3, comentario="Regular")

        datos = self.client.get("/api/ordenes/consulta/SW-ABCD2345").json()

        self.assertEqual(datos["calificacion"], {"estrellas": 3, "comentario": "Regular"})

    def test_la_consulta_por_cedula_incluye_solo_las_estrellas(self):
        self.calificar(estrellas=1, comentario="Mal")

        datos = self.client.post(
            "/api/ordenes/consulta-por-documento",
            {"documento": "1090123456", "correo": "ana@example.com"},
            format="json",
        ).json()

        self.assertEqual(datos["historial"][0]["calificacion"], {"estrellas": 1})

    def test_el_detalle_interno_de_la_orden_incluye_la_calificacion(self):
        self.calificar(estrellas=4, comentario="Bien")
        self.client.force_authenticate(User.objects.get(username="recepcion"))

        datos = self.client.get(f"/api/ordenes/{self.orden.pk}").json()

        self.assertEqual(datos["calificacion"], {"estrellas": 4, "comentario": "Bien"})


class CalificacionInmutableTests(TestCase):
    def setUp(self):
        self.calificacion = Calificacion.objects.create(orden=crear_orden("SW-ABCD2345"), estrellas=4)

    def test_no_se_puede_editar_ni_borrar(self):
        self.calificacion.estrellas = 5
        with self.assertRaises(PermissionDenied):
            self.calificacion.save()
        with self.assertRaises(PermissionDenied):
            self.calificacion.delete()
        with self.assertRaises(PermissionDenied):
            Calificacion.objects.update(estrellas=1)
        with self.assertRaises(PermissionDenied):
            Calificacion.objects.all().delete()

    def test_la_base_rechaza_estrellas_fuera_de_rango(self):
        for estrellas in (0, 6):
            with self.subTest(estrellas=estrellas), self.assertRaises(IntegrityError), transaction.atomic():
                Calificacion.objects.create(orden=crear_orden(f"SW-RANGO{estrellas:03d}"), estrellas=estrellas)


class CalificacionesApiTests(APITestCase):
    URL = "/api/calificaciones"

    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="x", rol=User.Rol.ADMINISTRADOR)
        self.recepcion = User.objects.create_user(username="rita", password="x", rol=User.Rol.RECEPCIONISTA)
        self.operario = User.objects.create_user(username="pedro", password="x", rol=User.Rol.OPERARIO)
        self.vieja = Calificacion.objects.create(orden=crear_orden("SW-VIEJA001"), estrellas=2, comentario="Tarde")
        self.nueva = Calificacion.objects.create(orden=crear_orden("SW-NUEVA001"), estrellas=5)

    def consultar(self, usuario, **filtros):
        self.client.force_authenticate(usuario)
        return self.client.get(self.URL, filtros)

    def test_administrador_y_recepcionista_ven_el_promedio_y_la_lista(self):
        for usuario in (self.admin, self.recepcion):
            with self.subTest(usuario=usuario.username):
                response = self.consultar(usuario)

                self.assertEqual(response.status_code, 200)
                datos = response.json()
                self.assertEqual((datos["promedio"], datos["total"]), (3.5, 2))
                self.assertEqual([c["orden_codigo"] for c in datos["calificaciones"]], ["SW-NUEVA001", "SW-VIEJA001"])
                self.assertEqual(
                    set(datos["calificaciones"][0]),
                    {"orden_id", "orden_codigo", "cliente_nombre", "estrellas", "comentario", "creada_en"},
                )
                self.assertEqual(datos["calificaciones"][1]["cliente_nombre"], "Ana Gomez")

    def test_operario_y_anonimo_no_pueden_verlas(self):
        self.assertEqual(self.consultar(self.operario).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.URL).status_code, 403)

    def test_sin_calificaciones_el_promedio_es_nulo(self):
        response = self.consultar(self.admin, desde="2000-01-01", hasta="2000-01-02")

        self.assertEqual(response.json(), {"promedio": None, "total": 0, "calificaciones": []})

    def test_filtra_por_fechas(self):
        hoy = timezone.localdate()
        with mock.patch("django.utils.timezone.now", return_value=timezone.now() - timedelta(days=10)):
            Calificacion.objects.create(orden=crear_orden("SW-ANTIGUA1"), estrellas=1)

        reciente = self.consultar(self.admin, desde=(hoy - timedelta(days=1)).isoformat(), hasta=hoy.isoformat()).json()
        antigua = self.consultar(self.admin, hasta=(hoy - timedelta(days=5)).isoformat()).json()

        self.assertEqual((reciente["total"], reciente["promedio"]), (2, 3.5))
        self.assertEqual([c["orden_codigo"] for c in antigua["calificaciones"]], ["SW-ANTIGUA1"])

    def test_rechaza_fechas_invalidas_o_al_reves(self):
        self.assertEqual(self.consultar(self.admin, desde="ayer").status_code, 400)
        self.assertEqual(self.consultar(self.admin, desde="2026-11-10", hasta="2026-11-01").status_code, 400)


class ListaCalificacionesPaginadaApiTests(PruebasDeListaMixin, APITestCase):
    url = "/api/calificaciones"
    campo_clave = "orden_codigo"
    invalidos = ({"estrellas": "0"}, {"estrellas": "6"}, {"estrellas": "muchas"})

    def setUp(self):
        self.client.force_authenticate(
            User.objects.create_user(username="rita", password="x", rol=User.Rol.RECEPCIONISTA)
        )
        self.numero = 0

    def crear(self, cuando, estrellas=4, comentario="", cliente=None):
        self.numero += 1
        orden = crear_orden(f"SW-CAL{self.numero:05d}")
        if cliente:
            Orden.objects.filter(pk=orden.pk).update(cliente=cliente)
        calificacion = Calificacion.objects.create(orden=orden, estrellas=estrellas, comentario=comentario)
        # La calificacion es inmutable: la fecha se ajusta por SQL solo para la prueba.
        with connection.cursor() as cursor:
            cursor.execute("UPDATE satisfaccion_calificacion SET creada_en = %s WHERE id = %s", [cuando, calificacion.pk])
        return calificacion

    def clave(self, calificacion):
        return calificacion.orden.codigo

    def test_sin_parametros_responde_la_lista_completa_como_antes(self):
        self.crear_varios(3)

        datos = self.client.get(self.url).json()

        self.assertEqual(set(datos), {"promedio", "total", "calificaciones"})
        self.assertEqual(datos["total"], 3)

    def test_el_promedio_y_el_total_son_de_todo_lo_filtrado(self):
        manana = timezone.now() + timedelta(days=1)
        for estrellas in (5, 4, 1):
            self.crear(manana, estrellas=estrellas)

        datos = self.listar(tamano=1).json()

        self.assertEqual((datos["promedio"], datos["total"], len(datos["resultados"])), (3.3, 3, 1))
        self.assertEqual(self.listar(estrellas=5).json()["promedio"], 5.0)

    def test_busca_por_codigo_cliente_y_comentario(self):
        manana = timezone.now() + timedelta(days=1)
        luis = Cliente.objects.create(documento="555", nombre_completo="Luis Perez", telefono="3")
        tarde = self.crear(manana, comentario="Llego tarde")
        de_luis = self.crear(manana, cliente=luis)

        for texto, esperada in ((tarde.orden.codigo.lower(), tarde), ("TARDE", tarde), ("luis perez", de_luis)):
            with self.subTest(texto=texto):
                self.assertEqual(self.claves(self.listar(buscar=texto)), [esperada.orden.codigo])

    def test_filtra_por_estrellas_y_conserva_desde_y_hasta(self):
        manana = timezone.now() + timedelta(days=1)
        una = self.crear(manana, estrellas=1)
        self.crear(manana, estrellas=5)
        vieja = self.crear(timezone.now() - timedelta(days=30), estrellas=1)

        self.assertEqual(self.claves(self.listar(estrellas=1)), [una.orden.codigo, vieja.orden.codigo])
        desde = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.assertEqual(self.claves(self.listar(estrellas=1, desde=desde)), [una.orden.codigo])

    def test_el_operario_no_tiene_acceso(self):
        self.client.force_authenticate(User.objects.create_user(username="pedro", password="x", rol=User.Rol.OPERARIO))

        self.assertEqual(self.listar(pagina=1).status_code, 403)
