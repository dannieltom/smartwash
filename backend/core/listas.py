"""Piezas comunes de las listas paginadas: pagina y tamano, busqueda por palabras y fechas.

Un endpoint de lista sin ninguno de sus parametros responde la lista completa como antes;
con alguno, responde paginado con {"total", "pagina", "paginas", "tamano", "resultados"}.
"""

from datetime import date, datetime, time, timedelta
from functools import reduce
from math import ceil
from operator import or_

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response

TAMANO_POR_DEFECTO = 20
TAMANO_MAXIMO = 100
PAGINACION = ("buscar", "pagina", "tamano")
FECHA = ("anio", "mes", "dia")


def pide_paginacion(params, nombres):
    return any(nombre in params for nombre in nombres)


def entero(params, nombre, por_defecto=None):
    texto = params.get(nombre, "").strip()
    if not texto:
        return por_defecto
    if not texto.isdigit() or int(texto) < 1:
        raise serializers.ValidationError({nombre: "Debe ser un numero entero mayor o igual a 1."})
    return int(texto)


def opcion(params, nombre, validos, mensaje="Ese valor no existe."):
    """El valor del filtro si es uno de `validos`; "" si no viene; 400 si viene otro."""
    valor = params.get(nombre, "").strip()
    if valor and valor not in validos:
        raise serializers.ValidationError({nombre: mensaje})
    return valor


def buscar_por_palabras(queryset, texto, campos):
    """Cada palabra debe aparecer (sin distinguir mayusculas) en alguno de los campos."""
    for palabra in texto.split():
        queryset = queryset.filter(reduce(or_, (Q(**{f"{campo}__icontains": palabra}) for campo in campos)))
    return queryset


def rango_de_fecha(params):
    """[inicio, fin) en hora de Bogota para anio, anio+mes o anio+mes+dia; None sin filtro de fecha."""
    anio, mes, dia = (entero(params, nombre) for nombre in FECHA)
    if mes is not None and anio is None:
        raise serializers.ValidationError({"mes": "Para filtrar por mes elige tambien el año."})
    if dia is not None and mes is None:
        raise serializers.ValidationError({"dia": "Para filtrar por dia elige tambien el mes."})
    if anio is None:
        return None
    try:
        if dia is not None:
            inicio = date(anio, mes, dia)
            fin = inicio + timedelta(days=1)
        elif mes is not None:
            inicio = date(anio, mes, 1)
            fin = date(anio + mes // 12, mes % 12 + 1, 1)
        else:
            inicio, fin = date(anio, 1, 1), date(anio + 1, 1, 1)
    except ValueError:
        raise serializers.ValidationError({"dia" if dia else "mes" if mes else "anio": "Esa fecha no existe."})
    local = timezone.get_current_timezone()
    return tuple(timezone.make_aware(datetime.combine(d, time.min), local) for d in (inicio, fin))


def filtrar_por_fecha(queryset, params, campo):
    rango = rango_de_fecha(params)
    if rango is None:
        return queryset
    return queryset.filter(**{f"{campo}__gte": rango[0], f"{campo}__lt": rango[1]})


def anios_de(queryset, campo):
    """Los anos (en hora de Bogota) en que hay registros, del mas reciente al mas antiguo."""
    return [dia.year for dia in queryset.order_by().dates(campo, "year", order="DESC")]


def pagina_y_tamano(params):
    return entero(params, "pagina", 1), min(entero(params, "tamano", TAMANO_POR_DEFECTO), TAMANO_MAXIMO)


def respuesta_paginada(queryset, params, serializar, **extra):
    """`queryset` ya filtrado y ordenado; `serializar` recibe la lista de la pagina.

    Lo que va en `extra` (p. ej. `anios`) se agrega a la respuesta antes de los resultados.
    """
    pagina, tamano = pagina_y_tamano(params)
    total = queryset.count()
    inicio = (pagina - 1) * tamano
    resultados = list(queryset[inicio : inicio + tamano]) if inicio < total else []
    return Response(
        {
            "total": total,
            "pagina": pagina,
            "paginas": ceil(total / tamano),
            "tamano": tamano,
            **extra,
            "resultados": serializar(resultados),
        }
    )


class ListaPaginadaMixin:
    """Para una ListAPIView: sin parametros de lista responde como siempre; con alguno, paginado.

    Cada vista declara `parametros_de_lista` (los que activan la paginacion) y `filtrar_lista`,
    que aplica sus filtros y el orden. `con_anios` agrega los anos de ese campo de fecha.
    """

    parametros_de_lista = PAGINACION
    con_anios = None

    def filtrar_lista(self, queryset, params):
        return queryset

    def list(self, request, *args, **kwargs):
        params = request.query_params
        if not pide_paginacion(params, self.parametros_de_lista):
            return super().list(request, *args, **kwargs)
        visibles = self.get_queryset()
        extra = {"anios": anios_de(visibles, self.con_anios)} if self.con_anios else {}
        return respuesta_paginada(
            self.filtrar_lista(visibles, params),
            params,
            lambda pagina: self.get_serializer(pagina, many=True).data,
            **extra,
        )
