"""Pruebas comunes de las listas paginadas (core/listas.py). Se mezclan en un APITestCase por modulo."""

from datetime import datetime, timedelta
from math import ceil
from zoneinfo import ZoneInfo

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

BOGOTA = ZoneInfo("America/Bogota")


class PruebasDeListaMixin:
    """La clase define `url`, `crear(cuando)` (crea un registro con esa fecha) y `clave(objeto)`, que se
    compara con `resultado[campo_clave]`. Con `con_fecha` tambien prueba el filtro anio/mes/dia."""

    url = None
    campo_clave = "id"
    con_fecha = False
    invalidos = ()

    def crear(self, cuando):
        raise NotImplementedError

    def clave(self, objeto):
        return objeto.pk

    def listar(self, **params):
        return self.client.get(self.url, params)

    def claves(self, response):
        self.assertEqual(response.status_code, 200, response.content[:300])
        return [r[self.campo_clave] for r in response.json()["resultados"]]

    def crear_varios(self, cantidad):
        """Del mas antiguo al mas reciente, despues de todo lo que creo setUp."""
        base = timezone.now() + timedelta(days=1)
        return [self.crear(base + timedelta(minutes=i)) for i in range(cantidad)]

    def test_sin_parametros_responde_la_lista_completa_como_antes(self):
        self.crear_varios(3)

        completa = self.listar()

        self.assertEqual(completa.status_code, 200)
        self.assertIsInstance(completa.json(), list)
        self.assertEqual(len(completa.json()), self.listar(pagina=1).json()["total"])

    def test_pagina_con_el_tamano_pedido_de_la_mas_reciente_a_la_mas_antigua(self):
        antes = self.listar(pagina=1).json()["total"]
        creados = self.crear_varios(5)

        datos = self.listar(tamano=2).json()

        total = antes + 5
        self.assertEqual(
            {k: datos[k] for k in ("total", "pagina", "paginas", "tamano")},
            {"total": total, "pagina": 1, "paginas": ceil(total / 2), "tamano": 2},
        )
        esperado = [self.clave(o) for o in reversed(creados)]
        self.assertEqual(self.claves(self.listar(tamano=2)), esperado[:2])
        self.assertEqual(self.claves(self.listar(tamano=2, pagina=2)), esperado[2:4])

    def test_la_ultima_creada_va_primero(self):
        ahora = timezone.now() + timedelta(days=1)
        primera = self.crear(ahora - timedelta(hours=2))
        tercera = self.crear(ahora)
        segunda = self.crear(ahora - timedelta(hours=1))

        self.assertEqual(
            self.claves(self.listar(pagina=1))[:3], [self.clave(tercera), self.clave(segunda), self.clave(primera)]
        )

    def test_una_pagina_fuera_de_rango_viene_vacia(self):
        self.crear_varios(1)

        response = self.listar(pagina=999)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["resultados"], [])

    def test_el_tamano_se_recorta_a_100(self):
        self.assertEqual(self.listar(tamano=500).json()["tamano"], 100)

    def test_parametros_invalidos_responden_400(self):
        casos = [{"pagina": "0"}, {"pagina": "dos"}, {"tamano": "-5"}, *self.invalidos]
        if self.con_fecha:
            casos += [{"mes": "3"}, {"anio": "2021", "dia": "4"}, {"anio": "2021", "mes": "2", "dia": "31"}]
        for params in casos:
            with self.subTest(params=params):
                self.assertEqual(self.listar(**params).status_code, 400)

    def test_filtra_por_fecha_en_hora_de_bogota(self):
        if not self.con_fecha:
            self.skipTest("Esta lista no filtra por fecha.")
        noche = self.crear(datetime(2021, 3, 14, 23, 30, tzinfo=BOGOTA))
        siguiente = self.crear(datetime(2021, 3, 15, 8, 0, tzinfo=BOGOTA))
        abril = self.crear(datetime(2021, 4, 2, 10, 0, tzinfo=BOGOTA))
        anterior = self.crear(datetime(2020, 12, 31, 23, 59, tzinfo=BOGOTA))
        clave = self.clave

        self.assertEqual(self.claves(self.listar(anio=2021)), [clave(abril), clave(siguiente), clave(noche)])
        self.assertEqual(self.claves(self.listar(anio=2021, mes=3)), [clave(siguiente), clave(noche)])
        self.assertEqual(self.claves(self.listar(anio=2021, mes=3, dia=14)), [clave(noche)])
        self.assertEqual(self.claves(self.listar(anio=2020, mes=12, dia=31)), [clave(anterior)])
        self.assertTrue({2021, 2020} <= set(self.listar(pagina=1).json()["anios"]))

    def test_las_consultas_no_dependen_del_tamano_de_la_pagina(self):
        self.crear_varios(1)
        with CaptureQueriesContext(connection) as una:
            self.listar(pagina=1)

        self.crear_varios(6)
        with self.assertNumQueries(len(una.captured_queries)):
            self.assertGreaterEqual(len(self.listar(pagina=1).json()["resultados"]), 7)
