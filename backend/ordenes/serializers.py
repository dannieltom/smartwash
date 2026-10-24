from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from accounts.models import User
from catalogo.models import Material, Servicio, Tarifa, TipoPrenda
from catalogo.precios import calcular_precio
from clientes.models import Cliente

from .historial import operacion_sobre_orden, registrar_evento
from .models import HistorialOrden, Orden, OrdenServicio, Prenda

Evento = HistorialOrden.TipoEvento
ESTADOS_QUE_ADMITEN_LINEAS = (
    Orden.Estado.EN_ESPERA,
    Orden.Estado.RECIBIDA,
    Orden.Estado.CLASIFICADA,
)
ESTADOS_REASIGNABLES = (Orden.Estado.RECIBIDA, Orden.Estado.CLASIFICADA)
ESTADOS_CON_TRABAJO_EN_CURSO = (Orden.Estado.EN_PROCESO, Orden.Estado.CONTROL_CALIDAD)


def nombre_usuario(usuario):
    return usuario.get_full_name() or usuario.username


class HistorialOrdenSerializer(serializers.ModelSerializer):
    tipo_evento_nombre = serializers.CharField(source="get_tipo_evento_display")
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = HistorialOrden
        fields = (
            "id",
            "fecha",
            "tipo_evento",
            "tipo_evento_nombre",
            "usuario",
            "usuario_nombre",
            "detalle",
        )
        read_only_fields = fields

    def get_usuario_nombre(self, evento) -> str:
        if evento.usuario is None:
            return "Sistema"
        return evento.usuario.get_full_name() or evento.usuario.username


def exigir_orden_editable(orden):
    if orden.estado not in ESTADOS_QUE_ADMITEN_LINEAS:
        raise serializers.ValidationError(
            f'La orden esta "{orden.estado}": desde "En proceso" lo adicional va en otra orden.'
        )


def tarifa_aplicable(tipo_prenda, servicio):
    tarifa = Tarifa.objects.aplicable(tipo_prenda, servicio, timezone.localdate())
    if tarifa is None:
        raise serializers.ValidationError(
            f'No hay tarifa vigente para "{servicio}" (ni general ni para "{tipo_prenda}").'
        )
    return tarifa


def exigir_peso_registrado(prenda):
    if prenda.peso is None:
        raise serializers.ValidationError(
            "La prenda no tiene peso registrado y el precio depende del peso."
        )


def agregar_servicio(prenda, tarifa, usuario):
    precio = calcular_precio(tarifa, prenda.peso, prenda.material)
    linea = OrdenServicio(
        prenda=prenda,
        tarifa=tarifa,
        valor_aplicado=precio.precio_unitario * prenda.cantidad,
        valor_base=tarifa.valor_base,
        precio_por_kilo=tarifa.precio_por_kilo,
        peso=prenda.peso,
        nivel_dificultad=precio.nivel,
        factor=precio.factor,
        es_excepcion=precio.es_excepcion,
    )
    linea.registrar_autoria(usuario)
    linea.save()
    return linea


def agregar_prenda(orden, datos, usuario):
    tarifas = datos.pop("tarifas")
    prenda = Prenda(orden=orden, **datos)
    prenda.registrar_autoria(usuario)
    prenda.save()
    for tarifa in tarifas:
        agregar_servicio(prenda, tarifa, usuario)
    return prenda


def guardar_recalculo(orden, usuario):
    orden.recalcular()
    orden.registrar_autoria(usuario)
    orden.save()


class PrendaEntradaSerializer(serializers.ModelSerializer):
    tipo_prenda = serializers.PrimaryKeyRelatedField(queryset=TipoPrenda.objects.all())
    material = serializers.PrimaryKeyRelatedField(queryset=Material.objects.all())
    cantidad = serializers.IntegerField(min_value=1)
    peso = serializers.DecimalField(max_digits=7, decimal_places=2, min_value=Decimal("0.01"))
    servicios = serializers.PrimaryKeyRelatedField(
        queryset=Servicio.objects.all(),
        many=True,
        allow_empty=False,
        error_messages={"empty": "Cada prenda debe tener al menos un servicio."},
    )

    class Meta:
        model = Prenda
        fields = (
            "tipo_prenda",
            "material",
            "cantidad",
            "peso",
            "talla",
            "genero",
            "color",
            "estado_inicial",
            "servicios",
        )

    def validate(self, attrs):
        servicios = attrs.pop("servicios")
        if len(set(servicios)) != len(servicios):
            raise serializers.ValidationError({"servicios": "Hay servicios repetidos."})
        attrs["tarifas"] = [tarifa_aplicable(attrs["tipo_prenda"], s) for s in servicios]
        return attrs


class OrdenServicioSerializer(serializers.ModelSerializer):
    servicio = serializers.IntegerField(source="tarifa.servicio_id", read_only=True)
    servicio_nombre = serializers.CharField(source="tarifa.servicio.nombre", read_only=True)

    class Meta:
        model = OrdenServicio
        fields = (
            "id",
            "servicio",
            "servicio_nombre",
            "valor_aplicado",
            "valor_base",
            "precio_por_kilo",
            "peso",
            "nivel_dificultad",
            "factor",
            "es_excepcion",
        )


class PrendaSerializer(serializers.ModelSerializer):
    tipo_prenda_nombre = serializers.CharField(source="tipo_prenda.nombre", read_only=True)
    material_nombre = serializers.CharField(source="material.nombre", read_only=True, allow_null=True)
    servicios = OrdenServicioSerializer(many=True, read_only=True)

    class Meta:
        model = Prenda
        fields = (
            "id",
            "tipo_prenda",
            "tipo_prenda_nombre",
            "material",
            "material_nombre",
            "cantidad",
            "peso",
            "talla",
            "genero",
            "color",
            "estado_inicial",
            "servicios",
        )


class OrdenSerializer(serializers.ModelSerializer):
    cliente = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.all())
    cliente_nombre = serializers.CharField(source="cliente.nombre_completo", read_only=True)
    prendas = PrendaEntradaSerializer(
        many=True,
        write_only=True,
        allow_empty=False,
        error_messages={
            "empty": "La orden debe tener al menos una prenda.",
            "required": "La orden debe tener al menos una prenda.",
        },
    )
    detalle_prendas = PrendaSerializer(source="prendas", many=True, read_only=True)

    class Meta:
        model = Orden
        fields = (
            "id",
            "codigo",
            "cliente",
            "cliente_nombre",
            "recepcionista",
            "operario",
            "estado",
            "estado_pago",
            "subtotal",
            "descuento",
            "valor_total",
            "abono_requerido",
            "duracion_estimada_dias",
            "fecha_estimada_entrega",
            "fecha_entrega",
            "creado_en",
            "prendas",
            "detalle_prendas",
        )
        read_only_fields = tuple(
            f for f in fields if f not in ("cliente", "prendas", "detalle_prendas")
        )

    def to_representation(self, orden):
        datos = super().to_representation(orden)
        # ponytail: una consulta de pagos por orden; anotar el queryset si el
        # listado crece hasta notarse.
        pagado = orden.total_pagado()
        datos.update(
            total_pagado=f"{pagado:.2f}",
            saldo_pendiente=f"{max(orden.valor_total - pagado, 0):.2f}",
            tiene_abono=orden.tiene_abono(),
            pago_completo=pagado >= orden.valor_total,
        )
        return datos

    def create(self, validated_data):
        usuario = self.context["request"].user
        with operacion_sobre_orden():
            orden = Orden(cliente=validated_data["cliente"], recepcionista=usuario)
            orden.registrar_autoria(usuario)
            orden.save()
            for datos in validated_data["prendas"]:
                agregar_prenda(orden, datos, usuario)
            guardar_recalculo(orden, usuario)
            registrar_evento(
                orden,
                Evento.CREACION,
                usuario,
                f"Orden registrada para {orden.cliente} por ${orden.valor_total}",
            )
        return orden


def operarios_activos():
    return User.objects.filter(rol=User.Rol.OPERARIO, is_active=True)


class OperarioSerializer(serializers.ModelSerializer):
    nombre = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "nombre")

    def get_nombre(self, usuario) -> str:
        return nombre_usuario(usuario)


class AsignacionSerializer(serializers.Serializer):
    # Un id de otro rol, inactivo o inexistente recibe el mismo mensaje: la
    # respuesta no revela que cuentas existen.
    operario = serializers.PrimaryKeyRelatedField(
        queryset=operarios_activos(),
        error_messages={
            "does_not_exist": "Selecciona un operario activo.",
            "incorrect_type": "Selecciona un operario activo.",
            "required": "Selecciona el operario.",
            "null": "Selecciona el operario.",
        },
    )


def asignar_operario(orden, operario, usuario):
    """Asigna o reasigna la orden y devuelve el evento para el historial.

    Desde "En proceso" la orden queda fija con su operario; solo el
    administrador la mueve, y solo si ese operario ya no esta activo.
    """
    orden.exigir_abono()
    if orden.estado == Orden.Estado.EN_ESPERA:
        raise serializers.ValidationError(
            {"estado": 'La orden esta "En espera"; no se puede asignar a un operario.'}
        )
    anterior = orden.operario
    if anterior == operario:
        raise serializers.ValidationError(
            {"operario": "La orden ya esta asignada a ese operario."}
        )
    operario_desactivado = anterior is None or not anterior.is_active
    excepcion_admin = (
        orden.estado in ESTADOS_CON_TRABAJO_EN_CURSO
        and usuario.rol == User.Rol.ADMINISTRADOR
        and operario_desactivado
    )
    if orden.estado in ESTADOS_CON_TRABAJO_EN_CURSO and not excepcion_admin:
        raise serializers.ValidationError(
            {
                "estado": f'La orden esta "{orden.estado}" y queda fija con su operario. '
                "Solo el administrador puede reasignarla si el operario fue desactivado."
            }
        )
    if orden.estado not in ESTADOS_REASIGNABLES and not excepcion_admin:
        raise serializers.ValidationError(
            {"estado": f'La orden esta "{orden.estado}"; no se puede asignar ni reasignar.'}
        )

    orden.operario = operario
    orden.registrar_autoria(usuario)
    orden.save()

    if anterior is None:
        return Evento.ASIGNACION, f"Asignada a {nombre_usuario(operario)}"
    detalle = f"{nombre_usuario(anterior)} → {nombre_usuario(operario)}"
    if excepcion_admin:
        detalle += " (el operario anterior fue desactivado)"
    return Evento.REASIGNACION, detalle


class AgregarServicioSerializer(serializers.Serializer):
    servicio = serializers.PrimaryKeyRelatedField(queryset=Servicio.objects.all())

    def validate_servicio(self, servicio):
        prenda = self.context["prenda"]
        if prenda.servicios.filter(tarifa__servicio=servicio).exists():
            raise serializers.ValidationError("La prenda ya tiene este servicio.")
        exigir_peso_registrado(prenda)
        return tarifa_aplicable(prenda.tipo_prenda, servicio)


class CambioEstadoSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=Orden.Estado.choices)


class VerificacionPrendaSerializer(serializers.Serializer):
    prenda = serializers.IntegerField()
    coincide = serializers.BooleanField()
    observacion = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        attrs["observacion"] = attrs["observacion"].strip()
        if not attrs["coincide"] and not attrs["observacion"]:
            raise serializers.ValidationError(
                {"observacion": "Es obligatoria cuando la prenda no coincide con lo solicitado."}
            )
        return attrs


class EntregaSerializer(serializers.Serializer):
    prendas = VerificacionPrendaSerializer(
        many=True,
        allow_empty=False,
        error_messages={"empty": "Hay que verificar cada prenda de la orden."},
    )

    def verificar_contra(self, orden):
        """Devuelve el detalle para el historial; exige cada prenda una sola vez."""
        verificaciones = self.validated_data["prendas"]
        registradas = {p.pk: p for p in orden.prendas.select_related("tipo_prenda", "material")}
        if sorted(v["prenda"] for v in verificaciones) != sorted(registradas):
            raise serializers.ValidationError(
                {"prendas": "Hay que verificar cada prenda de la orden, una sola vez."}
            )
        discrepancias = [
            f"{registradas[v['prenda']]}: {v['observacion']}"
            for v in verificaciones
            if not v["coincide"]
        ]
        detalle = f"{len(registradas)} prendas verificadas"
        if discrepancias:
            return f"{detalle}. Discrepancias: " + "; ".join(discrepancias)
        return f"{detalle}, todas coinciden con lo solicitado"



class PrendaBandejaSerializer(serializers.ModelSerializer):
    tipo_prenda_nombre = serializers.CharField(source="tipo_prenda.nombre", read_only=True)
    material_nombre = serializers.CharField(source="material.nombre", read_only=True, allow_null=True)
    servicios = serializers.SerializerMethodField()

    class Meta:
        model = Prenda
        fields = (
            "id",
            "tipo_prenda_nombre",
            "material_nombre",
            "cantidad",
            "peso",
            "talla",
            "genero",
            "color",
            "estado_inicial",
            "servicios",
        )

    def get_servicios(self, prenda) -> list[str]:
        return [linea.tarifa.servicio.nombre for linea in prenda.servicios.all()]


class OrdenBandejaSerializer(serializers.ModelSerializer):
    # Sin cliente ni valores: el operario solo necesita saber que procesar y para cuando.
    prendas = PrendaBandejaSerializer(many=True, read_only=True)

    class Meta:
        model = Orden
        fields = ("id", "codigo", "estado", "fecha_estimada_entrega", "prendas")
        read_only_fields = fields


class OrdenHistorialClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Orden
        fields = ("id", "codigo", "creado_en", "estado", "valor_total", "estado_pago")
        read_only_fields = fields
