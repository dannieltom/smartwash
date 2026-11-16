from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from catalogo.models import Servicio, Tarifa, TipoPrenda
from clientes.models import Cliente
from fidelizacion.models import BeneficioInactividad, Promocion, ReglaInactividad
from ordenes.models import HistorialOrden, Orden, OrdenServicio, Prenda
from pagos.models import Pago

from .periodos import periodo_de

User = get_user_model()
Evento = HistorialOrden.TipoEvento


class IndicadoresBase(APITestCase):
    def setUp(self):
        self.hoy = timezone.localdate()
        self.admin = User.objects.create_user(username="admin", password="x", rol=User.Rol.ADMINISTRADOR)
        self.recepcion = User.objects.create_user(username="recep", password="x", rol=User.Rol.RECEPCIONISTA)
        self.operario = User.objects.create_user(username="op", password="x", rol=User.Rol.OPERARIO)
        self.contador = 0
        self.servicios = {}
        self.tipos = {}

    def entrar(self, usuario):
        self.client.force_authenticate(usuario)

    def dia(self, dias_atras):
        return self.hoy - timedelta(days=dias_atras)

    def instante(self, dias_atras, hora=12):
        return timezone.make_aware(datetime.combine(self.dia(dias_atras), time(hora, 0)))

    def cliente(self, nombre="Ana", **extra):
        self.contador += 1
        return Cliente.objects.create(
            documento=str(1000 + self.contador), nombre_completo=nombre, telefono="300", **extra
        )

    def orden(self, cliente=None, estado=Orden.Estado.RECIBIDA, creada_hace=0, recibida_hace=None):
        self.contador += 1
        orden = Orden.objects.create(
            codigo=f"OR-{self.contador}",
            cliente=cliente or self.cliente(),
            recepcionista=self.recepcion,
            estado=estado,
        )
        Orden.objects.filter(pk=orden.pk).update(
            creado_en=self.instante(creada_hace),
            abono_alcanzado_en=None if recibida_hace is None else self.dia(recibida_hace),
        )
        orden.refresh_from_db()
        return orden

    def servicio(self, nombre):
        if nombre not in self.servicios:
            self.servicios[nombre] = Servicio.objects.create(nombre=nombre)
        return self.servicios[nombre]

    def tipo(self, nombre):
        if nombre not in self.tipos:
            self.tipos[nombre] = TipoPrenda.objects.create(nombre=nombre)
        return self.tipos[nombre]

    def prenda(self, orden, tipo, cantidad, **servicios):
        """servicios: nombre="valor" de la linea (ya multiplicado por la cantidad)."""
        prenda = Prenda.objects.create(orden=orden, tipo_prenda=self.tipo(tipo), cantidad=cantidad)
        for nombre, valor in servicios.items():
            servicio = self.servicio(nombre)
            tarifa = Tarifa.objects.filter(servicio=servicio).first() or Tarifa.objects.create(
                servicio=servicio, valor_base=0, precio_por_kilo=0,
                plazo_entrega_dias=1, vigente_desde=date(2020, 1, 1),
            )
            OrdenServicio.objects.create(prenda=prenda, tarifa=tarifa, valor_aplicado=Decimal(valor))
        return prenda

    def pagar(self, orden, monto, hace=0):
        with mock.patch("django.utils.timezone.now", return_value=self.instante(hace)):
            return Pago.objects.create(orden=orden, monto=Decimal(monto), metodo="efectivo")

    def devolver(self, orden, detalle, hace=0):
        with mock.patch("django.utils.timezone.now", return_value=self.instante(hace)):
            HistorialOrden.objects.create(orden=orden, tipo_evento=Evento.DEVOLUCION, detalle=detalle)


class PeriodoTests(APITestCase):
    HOY = date(2026, 11, 16)

    def periodo(self, **params):
        return periodo_de(params, self.HOY)

    def test_sin_parametros_es_hoy(self):
        periodo = self.periodo()
        self.assertEqual((periodo.tipo, periodo.desde, periodo.hasta), ("dia", self.HOY, self.HOY))

    def test_un_mes_anterior_se_cuenta_completo_y_el_actual_hasta_hoy(self):
        anterior = self.periodo(mes="2026-10")
        actual = self.periodo(mes="2026-11")

        self.assertEqual((anterior.desde, anterior.hasta), (date(2026, 10, 1), date(2026, 10, 31)))
        self.assertEqual((actual.desde, actual.hasta), (date(2026, 11, 1), self.HOY))

    def test_febrero_de_un_anio_bisiesto(self):
        periodo = periodo_de({"mes": "2024-02"}, self.HOY)

        self.assertEqual(periodo.hasta, date(2024, 2, 29))

    def test_un_rango_incluye_ambos_extremos(self):
        periodo = self.periodo(desde="2026-11-08", hasta="2026-11-16")

        self.assertEqual(len(periodo.dias), 9)

    def test_rechaza_lo_invalido(self):
        casos = [
            {"dia": "ayer"},
            {"dia": "2026-11-17"},
            {"mes": "2026-12"},
            {"mes": "2026-13"},
            {"mes": "2026-1"},
            {"desde": "2026-11-10"},
            {"desde": "2026-11-10", "hasta": "2026-11-09"},
            {"desde": "2026-11-10", "hasta": "2026-11-17"},
            {"desde": "2025-01-01", "hasta": "2026-11-16"},
            {"dia": "2026-11-10", "mes": "2026-10"},
            {"dia": "2026-11-10", "desde": "2026-11-01", "hasta": "2026-11-10"},
        ]
        for params in casos:
            with self.subTest(params=params):
                with self.assertRaises(Exception) as contexto:
                    self.periodo(**params)
                self.assertEqual(type(contexto.exception).__name__, "ValidationError")


class VentasTests(IndicadoresBase):
    RUTA = "/api/indicadores/ventas"

    def setUp(self):
        super().setUp()
        self.entrar(self.admin)

    def test_por_defecto_muestra_lo_cobrado_hoy_con_su_grafico(self):
        orden = self.orden()
        self.pagar(orden, "10000")
        self.pagar(orden, "5000")
        self.pagar(orden, "7000", hace=1)

        datos = self.client.get(self.RUTA).json()

        self.assertEqual(datos["periodo"]["tipo"], "dia")
        self.assertEqual(datos["total"], "15000.00")
        self.assertEqual(datos["por_dia"], [{"fecha": self.hoy.isoformat(), "total": "15000.00"}])
        self.assertFalse(datos["sin_datos"])

    def test_un_dia_cualquiera(self):
        orden = self.orden()
        self.pagar(orden, "7000", hace=7)
        self.pagar(orden, "1000", hace=1)

        datos = self.client.get(self.RUTA, {"dia": self.dia(7).isoformat()}).json()

        self.assertEqual(datos["total"], "7000.00")

    def test_un_mes_da_el_total_y_el_detalle_dia_por_dia(self):
        orden = self.orden()
        primero = date(self.hoy.year - 1, 10, 1)
        for dia, monto in ((primero, "1000"), (primero + timedelta(days=9), "2500")):
            horas = timezone.make_aware(datetime.combine(dia, time(9, 0)))
            with mock.patch("django.utils.timezone.now", return_value=horas):
                Pago.objects.create(orden=orden, monto=Decimal(monto), metodo="efectivo")

        datos = self.client.get(self.RUTA, {"mes": f"{primero.year}-10"}).json()

        self.assertEqual(datos["total"], "3500.00")
        self.assertEqual(len(datos["por_dia"]), 31)
        self.assertEqual(datos["por_dia"][0], {"fecha": "%d-10-01" % primero.year, "total": "1000.00"})
        self.assertEqual(datos["por_dia"][9]["total"], "2500.00")
        self.assertEqual(datos["por_dia"][1]["total"], "0.00")

    def test_el_mes_en_curso_es_el_acumulado_hasta_hoy(self):
        self.pagar(self.orden(), "4000")

        datos = self.client.get(self.RUTA, {"mes": self.hoy.strftime("%Y-%m")}).json()

        self.assertEqual(datos["periodo"]["hasta"], self.hoy.isoformat())
        self.assertEqual(len(datos["por_dia"]), self.hoy.day)
        self.assertEqual(datos["total"], "4000.00")

    def test_un_rango_da_el_total_y_el_detalle_por_dia(self):
        orden = self.orden()
        self.pagar(orden, "1000", hace=8)
        self.pagar(orden, "2000", hace=0)
        self.pagar(orden, "9999", hace=9)

        datos = self.client.get(
            self.RUTA, {"desde": self.dia(8).isoformat(), "hasta": self.hoy.isoformat()}
        ).json()

        self.assertEqual(datos["total"], "3000.00")
        self.assertEqual(len(datos["por_dia"]), 9)
        self.assertEqual(datos["por_dia"][0]["total"], "1000.00")

    def test_las_devoluciones_restan_el_dia_en_que_se_registraron(self):
        orden = self.orden()
        self.pagar(orden, "10000", hace=2)
        self.devolver(orden, "$10000.00 devueltos al cliente. Motivo: cancelada", hace=0)
        self.devolver(orden, "$500 devueltos al cliente: lo pagado supera el total", hace=0)

        hoy = self.client.get(self.RUTA).json()
        antier = self.client.get(self.RUTA, {"dia": self.dia(2).isoformat()}).json()

        self.assertEqual(hoy["total"], "-10500.00")
        self.assertEqual(antier["total"], "10000.00")
        self.assertFalse(hoy["sin_datos"])

    def test_un_evento_que_no_es_devolucion_no_resta(self):
        orden = self.orden()
        self.pagar(orden, "3000")
        with mock.patch("django.utils.timezone.now", return_value=self.instante(0)):
            HistorialOrden.objects.create(orden=orden, tipo_evento=Evento.PAGO, detalle="$900 en efectivo")

        self.assertEqual(self.client.get(self.RUTA).json()["total"], "3000.00")

    def test_el_dia_se_cuenta_en_hora_de_colombia(self):
        orden = self.orden()
        tarde = timezone.make_aware(datetime.combine(self.dia(1), time(23, 30)))
        with mock.patch("django.utils.timezone.now", return_value=tarde):
            Pago.objects.create(orden=orden, monto=Decimal("800"), metodo="efectivo")

        ayer = self.client.get(self.RUTA, {"dia": self.dia(1).isoformat()}).json()
        hoy = self.client.get(self.RUTA).json()

        self.assertEqual((ayer["total"], hoy["total"]), ("800.00", "0.00"))

    def test_un_dia_sin_pagos_esta_en_cero_y_sin_datos(self):
        datos = self.client.get(self.RUTA, {"dia": self.dia(3).isoformat()}).json()

        self.assertEqual(datos["total"], "0.00")
        self.assertEqual(datos["por_dia"][0]["total"], "0.00")
        self.assertTrue(datos["sin_datos"])

    def test_un_periodo_invalido_responde_400(self):
        for params in ({"dia": "x"}, {"mes": "2999-01"}, {"desde": "2026-01-01"}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(self.RUTA, params).status_code, 400)

    def test_la_recepcionista_solo_ve_el_total_de_hoy(self):
        self.pagar(self.orden(), "6000")
        self.entrar(self.recepcion)

        permitidos = (None, {"dia": self.hoy.isoformat()})
        for params in permitidos:
            with self.subTest(params=params):
                respuesta = self.client.get(self.RUTA, params)
                self.assertEqual(respuesta.status_code, 200)
                self.assertEqual(respuesta.json()["total"], "6000.00")
        prohibidos = (
            {"dia": self.dia(1).isoformat()},
            {"mes": self.hoy.strftime("%Y-%m")},
            {"desde": self.hoy.isoformat(), "hasta": self.hoy.isoformat()},
        )
        for params in prohibidos:
            with self.subTest(params=params):
                self.assertEqual(self.client.get(self.RUTA, params).status_code, 403)

    def test_el_operario_y_quien_no_inicio_sesion_no_acceden(self):
        self.entrar(self.operario)
        self.assertEqual(self.client.get(self.RUTA).status_code, 403)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.RUTA).status_code, 403)


class ServiciosYPrendasTests(IndicadoresBase):
    RUTA = "/api/indicadores/servicios-y-prendas"

    def setUp(self):
        super().setUp()
        self.entrar(self.admin)

    def test_ordena_de_mayor_a_menor_con_cantidad_y_valor(self):
        orden = self.orden(recibida_hace=0)
        self.prenda(orden, "Camisa", 3, Lavado="9000", Planchado="3000")
        self.prenda(orden, "Pantalon", 2, Lavado="8000")
        self.prenda(orden, "Sabana", 1, Lavado="5000", Planchado="2000")

        datos = self.client.get(self.RUTA).json()

        self.assertEqual(
            [(s["nombre"], s["cantidad"], s["valor"]) for s in datos["servicios"]],
            [("Lavado", 6, "22000.00"), ("Planchado", 4, "5000.00")],
        )
        self.assertEqual(
            [(t["nombre"], t["cantidad"], t["valor"]) for t in datos["tipos_de_prenda"]],
            [("Camisa", 3, "12000.00"), ("Pantalon", 2, "8000.00"), ("Sabana", 1, "7000.00")],
        )
        self.assertIn("pueden no coincidir", datos["nota"])

    def test_una_prenda_con_varios_servicios_cuenta_una_sola_vez_por_tipo(self):
        orden = self.orden(recibida_hace=0)
        self.prenda(orden, "Camisa", 2, Lavado="1000", Planchado="1000", Tintoreria="1000")

        tipos = self.client.get(self.RUTA).json()["tipos_de_prenda"]

        self.assertEqual([(t["cantidad"], t["valor"]) for t in tipos], [(2, "3000.00")])

    def test_cuenta_el_dia_en_que_paso_a_recibida_y_no_las_canceladas_ni_en_espera(self):
        buena = self.orden(recibida_hace=0)
        self.prenda(buena, "Camisa", 1, Lavado="1000")
        antigua = self.orden(recibida_hace=3)
        self.prenda(antigua, "Pantalon", 1, Lavado="1000")
        cancelada = self.orden(estado=Orden.Estado.CANCELADA, recibida_hace=0)
        self.prenda(cancelada, "Sabana", 1, Lavado="1000")
        en_espera = self.orden(estado=Orden.Estado.EN_ESPERA)
        self.prenda(en_espera, "Abrigo", 1, Lavado="1000")

        hoy = self.client.get(self.RUTA).json()
        hace_3 = self.client.get(self.RUTA, {"dia": self.dia(3).isoformat()}).json()

        self.assertEqual([t["nombre"] for t in hoy["tipos_de_prenda"]], ["Camisa"])
        self.assertEqual([t["nombre"] for t in hace_3["tipos_de_prenda"]], ["Pantalon"])

    def test_acepta_mes_y_rango_y_limita_la_lista(self):
        orden = self.orden(recibida_hace=2)
        for tipo in ("A", "B", "C"):
            self.prenda(orden, tipo, 1, Lavado="1000")

        datos = self.client.get(
            self.RUTA, {"desde": self.dia(5).isoformat(), "hasta": self.hoy.isoformat(), "limite": "2"}
        ).json()

        self.assertEqual(len(datos["tipos_de_prenda"]), 2)
        self.assertEqual(self.client.get(self.RUTA, {"limite": "0"}).status_code, 400)

    def test_sin_ordenes_responde_vacio_y_sin_datos(self):
        datos = self.client.get(self.RUTA).json()

        self.assertEqual((datos["servicios"], datos["tipos_de_prenda"]), ([], []))
        self.assertTrue(datos["sin_datos"])

    def test_solo_el_administrador(self):
        for usuario in (self.recepcion, self.operario):
            with self.subTest(rol=usuario.rol):
                self.entrar(usuario)
                self.assertEqual(self.client.get(self.RUTA).status_code, 403)


class ClientesFrecuentesTests(IndicadoresBase):
    RUTA = "/api/indicadores/clientes-frecuentes"

    def setUp(self):
        super().setUp()
        self.entrar(self.admin)

    def test_ordena_por_numero_de_ordenes_e_ignora_las_canceladas(self):
        ana, luis = self.cliente("Ana"), self.cliente("Luis")
        for _ in range(3):
            self.orden(ana)
        self.orden(luis)
        self.orden(luis, estado=Orden.Estado.EN_ESPERA)
        for _ in range(5):
            self.orden(luis, estado=Orden.Estado.CANCELADA)

        datos = self.client.get(self.RUTA).json()

        self.assertEqual(
            [(c["nombre_completo"], c["ordenes"]) for c in datos["clientes"]], [("Ana", 3), ("Luis", 2)]
        )
        self.assertEqual(datos["clientes"][0]["id"], ana.pk)

    def test_solo_cuenta_las_ordenes_del_periodo(self):
        ana = self.cliente("Ana")
        self.orden(ana, creada_hace=0)
        self.orden(ana, creada_hace=10)

        hoy = self.client.get(self.RUTA).json()["clientes"]
        rango = self.client.get(
            self.RUTA, {"desde": self.dia(12).isoformat(), "hasta": self.hoy.isoformat()}
        ).json()["clientes"]

        self.assertEqual((hoy[0]["ordenes"], rango[0]["ordenes"]), (1, 2))

    def test_el_empate_se_ordena_por_nombre(self):
        self.orden(self.cliente("Zoe"))
        self.orden(self.cliente("Ana"))

        nombres = [c["nombre_completo"] for c in self.client.get(self.RUTA).json()["clientes"]]

        self.assertEqual(nombres, ["Ana", "Zoe"])

    def test_sin_ordenes_responde_vacio_y_sin_datos(self):
        datos = self.client.get(self.RUTA).json()

        self.assertEqual(datos["clientes"], [])
        self.assertTrue(datos["sin_datos"])

    def test_solo_el_administrador(self):
        for usuario in (self.recepcion, self.operario):
            with self.subTest(rol=usuario.rol):
                self.entrar(usuario)
                self.assertEqual(self.client.get(self.RUTA).status_code, 403)

    def test_el_historial_del_cliente_sigue_disponible_para_el_administrador(self):
        ana = self.cliente("Ana")
        self.orden(ana)

        respuesta = self.client.get(f"/api/clientes/{ana.pk}/ordenes")

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["numero_ordenes"], 1)


class OrdenesPorEstadoTests(IndicadoresBase):
    RUTA = "/api/indicadores/ordenes-por-estado"

    def test_lista_todos_los_estados_aunque_esten_en_cero(self):
        self.entrar(self.admin)
        self.orden(estado=Orden.Estado.EN_ESPERA)
        self.orden(estado=Orden.Estado.EN_ESPERA)
        self.orden(estado=Orden.Estado.CANCELADA)

        datos = self.client.get(self.RUTA).json()

        cuenta = {fila["estado"]: fila["ordenes"] for fila in datos["estados"]}
        self.assertEqual(len(cuenta), len(Orden.Estado.values))
        self.assertEqual(cuenta["Con novedad"], 0)
        self.assertEqual(datos["estados"][0]["estado"], "En espera")
        self.assertEqual(cuenta["En espera"], 2)
        self.assertEqual(cuenta["Cancelada"], 1)
        self.assertEqual(cuenta["Entregada"], 0)
        self.assertEqual(datos["total"], 3)

    def test_solo_el_administrador(self):
        for usuario in (self.recepcion, self.operario):
            with self.subTest(rol=usuario.rol):
                self.entrar(usuario)
                self.assertEqual(self.client.get(self.RUTA).status_code, 403)


class FidelizacionIndicadoresTests(IndicadoresBase):
    RUTA = "/api/indicadores/fidelizacion"

    def setUp(self):
        super().setUp()
        self.entrar(self.admin)

    def test_resume_clientes_puntos_promociones_y_beneficios(self):
        self.cliente(clasificacion="VIP", puntos=300)
        self.cliente(clasificacion="VIP", puntos=100)
        self.cliente(clasificacion="Frecuente", puntos=50)
        Promocion.objects.create(
            nombre="Vigente", tipo="porcentaje", valor=10,
            vigente_desde=self.hoy, vigente_hasta=self.hoy,
        )
        Promocion.objects.create(
            nombre="Vencida", tipo="porcentaje", valor=10,
            vigente_desde=self.dia(9), vigente_hasta=self.dia(1),
        )
        regla = ReglaInactividad.objects.create(nombre="Mes", dias_sin_compra=30, puntos=40)
        cliente = Cliente.objects.first()
        BeneficioInactividad.objects.create(
            cliente=cliente, regla=regla, puntos=40, ultima_actividad=self.dia(60)
        )

        datos = self.client.get(self.RUTA).json()

        clasificaciones = {c["clasificacion"]: c["clientes"] for c in datos["clientes_por_clasificacion"]}
        self.assertEqual(clasificaciones, {"Ocasional": 0, "Frecuente": 1, "VIP": 2})
        self.assertEqual(datos["puntos_en_circulacion"], 450)
        self.assertEqual(datos["promociones_vigentes"], 1)
        self.assertEqual(datos["puntos_por_inactividad"], 40)

    def test_sin_reglas_de_inactividad_los_inactivos_no_se_calculan(self):
        self.assertIsNone(self.client.get(self.RUTA).json()["clientes_inactivos"])

    def test_con_reglas_cuenta_a_los_inactivos(self):
        ReglaInactividad.objects.create(nombre="Mes", dias_sin_compra=30, puntos=40)
        antiguo = self.cliente()
        Cliente.objects.filter(pk=antiguo.pk).update(creado_en=self.instante(90))
        self.cliente()

        self.assertEqual(self.client.get(self.RUTA).json()["clientes_inactivos"], 1)

    def test_vacio_todo_esta_en_cero(self):
        datos = self.client.get(self.RUTA).json()

        self.assertEqual((datos["puntos_en_circulacion"], datos["promociones_vigentes"]), (0, 0))

    def test_solo_el_administrador(self):
        for usuario in (self.recepcion, self.operario):
            with self.subTest(rol=usuario.rol):
                self.entrar(usuario)
                self.assertEqual(self.client.get(self.RUTA).status_code, 403)
