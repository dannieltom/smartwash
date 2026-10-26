import base64
import binascii
from decimal import Decimal

from django.db import models
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers

from accounts.models import User
from catalogo.models import Material, Servicio, Tarifa, TipoPrenda
from catalogo.precios import calcular_precio
from clientes.models import Cliente

from .historial import operacion_sobre_orden, registrar_evento
from .models import (
    ConfiguracionDescuentoNovedad,
    DanoPrenda,
    FotoDano,
    FotoNovedad,
    HistorialOrden,
    Novedad,
    Orden,
    OrdenServicio,
    Prenda,
)

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


def sin_ceros(valor):
    """15.00 → "15" y 2000.00 → "2000", para los textos del historial."""
    return f"{valor.normalize():f}"


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
    orden.exigir_no_cancelada()
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
    dano = serializers.SerializerMethodField()

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
            "dano",
        )

    def get_dano(self, prenda) -> str | None:
        return prenda.dano.tipo if hasattr(prenda, "dano") else None


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
            "descuento_novedad",
            "descuento_dano",
            "valor_total",
            "abono_requerido",
            "duracion_estimada_dias",
            "fecha_estimada_entrega",
            "fecha_entrega",
            "motivo_cancelacion",
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
            saldo_a_favor=f"{orden.saldo_a_favor():.2f}",
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
    orden.exigir_no_cancelada()
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


LIMITE_FOTO_BYTES = 500 * 1024
FIRMAS_DE_IMAGEN = ((b"\xff\xd8\xff", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", "image/png"))


def tipo_de_imagen(datos):
    # Se miran los bytes y no el tipo que declara el data URL: ese lo escribe el cliente.
    for firma, tipo in FIRMAS_DE_IMAGEN:
        if datos.startswith(firma):
            return tipo
    if datos[:4] == b"RIFF" and datos[8:12] == b"WEBP":
        return "image/webp"
    return None


class FotoField(serializers.CharField):
    """Acepta un data URL (data:image/jpeg;base64,...) o el base64 sin prefijo."""

    def to_internal_value(self, valor):
        _, _, codificado = super().to_internal_value(valor).rpartition("base64,")
        try:
            datos = base64.b64decode(codificado, validate=True)
        except (binascii.Error, ValueError):
            raise serializers.ValidationError("La foto no es un base64 valido.")
        tipo = tipo_de_imagen(datos)
        if tipo is None:
            raise serializers.ValidationError("El archivo no es una imagen JPEG, PNG o WebP.")
        if len(datos) > LIMITE_FOTO_BYTES:
            raise serializers.ValidationError(
                f"La foto pesa {len(datos) // 1024} KB; el maximo es 500 KB."
            )
        return {"contenido": base64.b64encode(datos).decode(), "tipo": tipo, "tamano": len(datos)}


def registrar_novedades(orden, novedades, origen, usuario):
    """Guarda las novedades [(prenda, descripcion, foto)] y deja la orden "Con novedad".

    Varias prendas generan una novedad cada una pero un solo evento en el historial.
    """
    anterior = orden.estado
    resumen = []
    for prenda, descripcion, foto in novedades:
        novedad = Novedad(
            orden=orden,
            prenda=prenda,
            descripcion=descripcion,
            origen=origen,
            estado_anterior=anterior,
        )
        novedad.registrar_autoria(usuario)
        novedad.save()
        if foto:
            foto = FotoNovedad(novedad=novedad, **foto)
            foto.registrar_autoria(usuario)
            foto.save()
        resumen.append(f"{prenda}: {descripcion} ({'con foto' if foto else 'sin foto'})")
    orden.estado = Orden.Estado.CON_NOVEDAD
    orden.registrar_autoria(usuario)
    orden.save()
    registrar_evento(
        orden,
        Evento.NOVEDAD,
        usuario,
        f"{anterior} → {orden.estado}, {Novedad.Origen(origen).label.lower()}. "
        + "; ".join(resumen),
    )


DECISIONES_POR_ORIGEN = {
    Novedad.Origen.PROCESO: (
        Novedad.Decision.CONTINUAR,
        Novedad.Decision.REPROCESAR,
        Novedad.Decision.NO_CONTINUAR,
    ),
    Novedad.Origen.ENTREGA: (
        Novedad.Decision.ENTREGAR_CON_DESCUENTO,
        Novedad.Decision.REPROCESAR_CON_DESCUENTO,
    ),
}


def aplicar_descuento(novedad, porcentaje, configuracion, gravedad=""):
    """Congela en la novedad el descuento de su prenda y devuelve la nota para el historial."""
    ya_descontado = (
        Novedad.objects.filter(prenda=novedad.prenda)
        .exclude(pk=novedad.pk)
        .aggregate(total=Sum("monto_descuento"))["total"]
        or Decimal("0")
    )
    novedad.gravedad = gravedad
    novedad.porcentaje_descuento = porcentaje
    novedad.monto_descuento = configuracion.monto_descuento(
        novedad.prenda.valor(), porcentaje, ya_descontado
    )
    etiqueta = f"{Novedad.Gravedad(gravedad).label.lower()} " if gravedad else ""
    return f"{novedad.prenda}: {etiqueta}{sin_ceros(porcentaje)} % → ${novedad.monto_descuento}"


def operario_para_reproceso(orden, elegido):
    """Por defecto vuelve al mismo operario; otro solo si se elige o si el original no esta activo."""
    if elegido is not None:
        return elegido
    if orden.operario is None or not orden.operario.is_active:
        raise serializers.ValidationError(
            {"operario": "El operario que proceso la orden no esta activo: selecciona otro."}
        )
    return orden.operario


def registrar_decision(orden, datos, usuario):
    """Aplica la decision del cliente a todas las novedades pendientes de la orden.

    "Entregar con descuento" deja la orden lista para que la vista la entregue
    en la misma transaccion; si el pago no alcanza, se revierte todo.
    """
    decision, observacion = datos["decision"], datos["observacion"]
    novedades = list(orden.novedades.pendientes().select_related("prenda"))
    if orden.estado != Orden.Estado.CON_NOVEDAD or not novedades:
        raise serializers.ValidationError(
            {"estado": f'La orden esta "{orden.estado}" y no tiene una novedad pendiente.'}
        )
    origen = Novedad.Origen(novedades[0].origen)
    permitidas = DECISIONES_POR_ORIGEN[origen]
    if decision not in permitidas:
        opciones = ", ".join(f'"{Novedad.Decision(d).label}"' for d in permitidas)
        raise serializers.ValidationError(
            {"decision": f"La novedad fue {origen.label.lower()}: las opciones son {opciones}."}
        )

    configuracion = ConfiguracionDescuentoNovedad.actual()
    descuentos = []
    reasignacion = None
    if decision == Novedad.Decision.CONTINUAR:
        orden.estado = novedades[0].estado_anterior
    elif decision == Novedad.Decision.REPROCESAR:
        # Sin costo para el cliente: solo se cuenta, como el reproceso de HU14.
        orden.estado = Orden.Estado.EN_PROCESO
        orden.numero_reprocesos += 1
    elif decision == Novedad.Decision.ENTREGAR_CON_DESCUENTO:
        gravedades = {g["novedad"]: g["gravedad"] for g in datos.get("gravedades", [])}
        if sorted(gravedades) != sorted(n.pk for n in novedades):
            raise serializers.ValidationError(
                {"gravedades": "Indica la gravedad de cada prenda con novedad."}
            )
        for novedad in novedades:
            gravedad = gravedades[novedad.pk]
            porcentaje = configuracion.porcentaje_para(gravedad)
            descuentos.append(aplicar_descuento(novedad, porcentaje, configuracion, gravedad))
    elif decision == Novedad.Decision.REPROCESAR_CON_DESCUENTO:
        operario = operario_para_reproceso(orden, datos.get("operario"))
        if operario != orden.operario:
            anterior = nombre_usuario(orden.operario) if orden.operario else "sin operario"
            reasignacion = f"{anterior} → {nombre_usuario(operario)} (reproceso por novedad de la entrega)"
            orden.operario = operario
        for novedad in novedades:
            descuentos.append(
                aplicar_descuento(novedad, configuracion.porcentaje_reproceso, configuracion)
            )
        orden.estado = Orden.Estado.EN_PROCESO
        orden.numero_reprocesos += 1

    ahora = timezone.now()
    for novedad in novedades:
        novedad.decision = decision
        novedad.decision_observacion = observacion
        novedad.decidida_por = usuario
        novedad.decidida_en = ahora
        novedad.registrar_autoria(usuario)
        novedad.save()
    orden.aplicar_descuentos_por_incidencia()
    orden.registrar_autoria(usuario)
    orden.save()

    detalle = f"{Novedad.Decision(decision).label}: {observacion}. "
    if descuentos:
        detalle += f"Descuentos: {'; '.join(descuentos)}. Nuevo total ${orden.valor_total}. "
    if orden.estado != Orden.Estado.CON_NOVEDAD:
        detalle += f"{Orden.Estado.CON_NOVEDAD} → {orden.estado}"
    elif decision != Novedad.Decision.ENTREGAR_CON_DESCUENTO:
        detalle += "La orden sigue Con novedad"
    registrar_evento(orden, Evento.DECISION_NOVEDAD, usuario, detalle.strip())
    if reasignacion:
        registrar_evento(orden, Evento.REASIGNACION, usuario, reasignacion)


class GravedadNovedadSerializer(serializers.Serializer):
    novedad = serializers.IntegerField()
    gravedad = serializers.ChoiceField(choices=Novedad.Gravedad.choices)


class DecisionNovedadSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=Novedad.Decision.choices)
    observacion = serializers.CharField(
        error_messages={
            "required": "La observacion es obligatoria: con quien se hablo y que decidio.",
            "blank": "La observacion es obligatoria: con quien se hablo y que decidio.",
        }
    )
    gravedades = GravedadNovedadSerializer(many=True, required=False)
    operario = serializers.PrimaryKeyRelatedField(
        queryset=operarios_activos(),
        required=False,
        allow_null=True,
        error_messages={
            "does_not_exist": "Selecciona un operario activo.",
            "incorrect_type": "Selecciona un operario activo.",
        },
    )


class NovedadEntradaSerializer(serializers.Serializer):
    prenda = serializers.IntegerField()
    descripcion = serializers.CharField(
        error_messages={
            "required": "La descripcion es obligatoria.",
            "blank": "La descripcion es obligatoria.",
        }
    )
    foto = FotoField(
        error_messages={
            "required": "La fotografia es obligatoria.",
            "blank": "La fotografia es obligatoria.",
            "null": "La fotografia es obligatoria.",
        }
    )


class NovedadSerializer(serializers.ModelSerializer):
    prenda_nombre = serializers.CharField(source="prenda.__str__", read_only=True)
    origen_nombre = serializers.CharField(source="get_origen_display", read_only=True)
    usuario_nombre = serializers.SerializerMethodField()
    foto_url = serializers.SerializerMethodField()

    class Meta:
        model = Novedad
        fields = (
            "id",
            "orden",
            "prenda",
            "prenda_nombre",
            "descripcion",
            "origen",
            "origen_nombre",
            "estado_anterior",
            "usuario_nombre",
            "creado_en",
            "foto_url",
            "decision",
            "decision_observacion",
            "gravedad",
            "porcentaje_descuento",
            "monto_descuento",
        )
        read_only_fields = fields

    def get_usuario_nombre(self, novedad) -> str | None:
        return nombre_usuario(novedad.creado_por) if novedad.creado_por else None

    def get_foto_url(self, novedad) -> str | None:
        if not hasattr(novedad, "foto"):
            return None
        return reverse("novedad-foto", args=[novedad.pk])


class CancelacionSerializer(serializers.Serializer):
    motivo = serializers.CharField(
        max_length=255,
        error_messages={
            "required": "Indica el motivo de la cancelacion.",
            "blank": "Indica el motivo de la cancelacion.",
            "null": "Indica el motivo de la cancelacion.",
        },
    )


class ResultadoVerificacion(models.TextChoices):
    COINCIDE = "coincide", "Coincide"
    NOVEDAD = "novedad", "Novedad"
    DANO = "dano", "Daño"
    PERDIDA = "perdida", "Pérdida"


class VerificacionPrendaSerializer(serializers.Serializer):
    prenda = serializers.IntegerField()
    resultado = serializers.ChoiceField(choices=ResultadoVerificacion.choices, required=False)
    # Forma anterior a HU35, que aun envia el frontend: coincide=false es una novedad.
    coincide = serializers.BooleanField(required=False)
    observacion = serializers.CharField(required=False, allow_blank=True, default="")
    foto = FotoField(required=False, allow_null=True, default=None)
    valor_declarado = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("1"), required=False, allow_null=True
    )

    def validate(self, attrs):
        resultado = attrs.get("resultado")
        if resultado is None:
            if "coincide" not in attrs:
                raise serializers.ValidationError({"resultado": "Indica el resultado de la prenda."})
            resultado = (
                ResultadoVerificacion.COINCIDE if attrs["coincide"] else ResultadoVerificacion.NOVEDAD
            )
        attrs["resultado"] = resultado
        attrs["observacion"] = attrs["observacion"].strip()
        if resultado == ResultadoVerificacion.COINCIDE:
            return attrs
        faltan = {}
        if not attrs["observacion"]:
            faltan["observacion"] = "Es obligatoria cuando la prenda no coincide con lo solicitado."
        if resultado == ResultadoVerificacion.PERDIDA:
            if attrs["foto"] is not None:
                faltan["foto"] = "Una prenda perdida no lleva foto."
        elif attrs["foto"] is None:
            faltan["foto"] = "La fotografia es obligatoria cuando la prenda no coincide."
        if resultado in DanoPrenda.Tipo.values and not attrs.get("valor_declarado"):
            faltan["valor_declarado"] = "Indica el valor de la prenda que declara el cliente."
        if faltan:
            raise serializers.ValidationError(faltan)
        return attrs


class EntregaSerializer(serializers.Serializer):
    prendas = VerificacionPrendaSerializer(
        many=True,
        allow_empty=False,
        error_messages={"empty": "Hay que verificar cada prenda de la orden."},
    )

    def verificar_contra(self, orden):
        """Exige una vez cada prenda que sigue en la orden y separa novedades de danos.

        Las prendas ya danadas o perdidas quedaron resueltas: no se vuelven a verificar.
        """
        verificaciones = self.validated_data["prendas"]
        registradas = {
            p.pk: p
            for p in orden.prendas.filter(dano__isnull=True).select_related("tipo_prenda", "material")
        }
        if sorted(v["prenda"] for v in verificaciones) != sorted(registradas):
            raise serializers.ValidationError(
                {"prendas": "Hay que verificar cada prenda de la orden, una sola vez."}
            )
        novedades, danos = [], []
        for v in verificaciones:
            prenda = registradas[v["prenda"]]
            if v["resultado"] == ResultadoVerificacion.NOVEDAD:
                novedades.append((prenda, v["observacion"], v["foto"]))
            elif v["resultado"] in DanoPrenda.Tipo.values:
                danos.append((prenda, v["resultado"], v["observacion"], v["foto"], v["valor_declarado"]))
        return novedades, danos


def registrar_danos(orden, danos, usuario):
    """Deja de cobrar el servicio de cada prenda danada o perdida y registra lo que se le debe al cliente."""
    resumen = []
    for prenda, tipo, descripcion, foto, valor_declarado in danos:
        dano = DanoPrenda(
            orden=orden,
            prenda=prenda,
            tipo=tipo,
            descripcion=descripcion,
            valor_declarado=valor_declarado,
            valor_servicio=prenda.valor(),
            operario=orden.operario,
        )
        dano.registrar_autoria(usuario)
        dano.save()
        if foto:
            foto = FotoDano(dano=dano, **foto)
            foto.registrar_autoria(usuario)
            foto.save()
        responsable = nombre_usuario(orden.operario) if orden.operario else "sin operario"
        resumen.append(
            f"{dano.get_tipo_display()} de {prenda}: {descripcion}. Servicio descontado "
            f"${dano.valor_servicio}; valor de la prenda ${valor_declarado}, a pagar al cliente. "
            f"Operario: {responsable}"
        )
    orden.aplicar_descuentos_por_incidencia()
    orden.registrar_autoria(usuario)
    orden.save()
    registrar_evento(
        orden,
        Evento.DANO_PRENDA,
        usuario,
        "; ".join(resumen) + f". Nuevo total ${orden.valor_total}",
    )


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


class OrdenAlertaSerializer(serializers.ModelSerializer):
    """`dias` es el retraso si la orden esta retrasada y lo que falta si esta proxima (0 = vence hoy)."""

    cliente_nombre = serializers.CharField(source="cliente.nombre_completo", read_only=True)
    tipo = serializers.SerializerMethodField()
    dias = serializers.SerializerMethodField()

    class Meta:
        model = Orden
        fields = (
            "id",
            "codigo",
            "cliente_nombre",
            "estado",
            "operario",
            "fecha_estimada_entrega",
            "tipo",
            "dias",
        )
        read_only_fields = fields

    def get_tipo(self, orden) -> str:
        return "retrasada" if orden.fecha_estimada_entrega < self.context["hoy"] else "proxima"

    def get_dias(self, orden) -> int:
        return abs((orden.fecha_estimada_entrega - self.context["hoy"]).days)


class OrdenConNovedadSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source="cliente.nombre_completo", read_only=True)
    operario_nombre = serializers.SerializerMethodField()
    novedades = NovedadSerializer(source="novedades_pendientes", many=True, read_only=True)

    class Meta:
        model = Orden
        fields = ("id", "codigo", "cliente_nombre", "estado", "operario_nombre", "novedades")
        read_only_fields = fields

    def get_operario_nombre(self, orden) -> str | None:
        return nombre_usuario(orden.operario) if orden.operario else None


class ConfiguracionDescuentoNovedadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionDescuentoNovedad
        fields = (
            "porcentaje_leve",
            "porcentaje_moderada",
            "porcentaje_notoria",
            "porcentaje_reproceso",
            "monto_minimo",
            "tope_porcentaje",
            "actualizado_en",
        )
        read_only_fields = ("actualizado_en",)

    def validate(self, attrs):
        leve, moderada, notoria = (
            attrs.get(campo, getattr(self.instance, campo))
            for campo in ("porcentaje_leve", "porcentaje_moderada", "porcentaje_notoria")
        )
        if not leve <= moderada <= notoria:
            raise serializers.ValidationError(
                "Los porcentajes deben ir de menor a mayor: leve, moderada y notoria."
            )
        return attrs


class DanoPrendaSerializer(serializers.ModelSerializer):
    orden_codigo = serializers.CharField(source="orden.codigo", read_only=True)
    cliente_nombre = serializers.CharField(source="orden.cliente.nombre_completo", read_only=True)
    prenda_nombre = serializers.CharField(source="prenda.__str__", read_only=True)
    tipo_nombre = serializers.CharField(source="get_tipo_display", read_only=True)
    estado_nombre = serializers.CharField(source="get_estado_display", read_only=True)
    operario_nombre = serializers.SerializerMethodField()
    registrado_por_nombre = serializers.SerializerMethodField()
    pagado_por_nombre = serializers.SerializerMethodField()
    foto_url = serializers.SerializerMethodField()

    class Meta:
        model = DanoPrenda
        fields = (
            "id",
            "orden",
            "orden_codigo",
            "cliente_nombre",
            "prenda",
            "prenda_nombre",
            "tipo",
            "tipo_nombre",
            "descripcion",
            "valor_declarado",
            "valor_servicio",
            "operario_nombre",
            "registrado_por_nombre",
            "creado_en",
            "estado",
            "estado_nombre",
            "pagado_por_nombre",
            "pagado_en",
            "observacion_pago",
            "foto_url",
        )
        read_only_fields = fields

    def get_operario_nombre(self, dano) -> str | None:
        return nombre_usuario(dano.operario) if dano.operario else None

    def get_registrado_por_nombre(self, dano) -> str | None:
        return nombre_usuario(dano.creado_por) if dano.creado_por else None

    def get_pagado_por_nombre(self, dano) -> str | None:
        return nombre_usuario(dano.pagado_por) if dano.pagado_por else None

    def get_foto_url(self, dano) -> str | None:
        return reverse("dano-foto", args=[dano.pk]) if hasattr(dano, "foto") else None


class PagoDanoSerializer(serializers.Serializer):
    observacion = serializers.CharField(
        error_messages={
            "required": "Indica como se le pago al cliente.",
            "blank": "Indica como se le pago al cliente.",
        }
    )
