"use client";

import Link from "next/link";

import type { NovedadHistorial, Pagina } from "@/lib/api";
import { FECHA_LEGIBLE } from "@/lib/auditoria";
import { formatCOP } from "@/lib/format";
import Buscador from "../../components/lista/buscador";
import FiltroFecha from "../../components/lista/filtro-fecha";
import ResultadosLista, { LimpiarFiltros } from "../../components/lista/resultados";
import { hayFiltros } from "../../components/lista/url";
import { useLista } from "../../components/lista/use-lista";
import { ClayBadge, ClayCard, ClayField, ClaySelect } from "../../components/ui/clay";
import { DECISIONES, GRAVEDADES, leerFiltrosHistorial, ORIGENES } from "./filtros";

function TarjetaNovedad({ n }: { n: NovedadHistorial }) {
  const resuelta = n.estado === "resuelta";
  return (
    <li>
      <ClayCard>
        <div className="flex flex-wrap gap-4">
          {n.foto_url ? (
            <a href={n.foto_url} target="_blank" rel="noreferrer" title="Ver la foto completa">
              {/* eslint-disable-next-line @next/next/no-img-element -- la foto la sirve el backend con la sesion */}
              <img
                src={n.foto_url}
                alt={`Foto de la novedad en ${n.prenda_nombre}`}
                className="h-24 w-24 rounded-xl object-cover"
                loading="lazy"
              />
            </a>
          ) : (
            <div className="flex h-24 w-24 items-center justify-center rounded-xl bg-(--sw-surface) text-xs text-(--sw-ink-soft)">
              Sin foto
            </div>
          )}
          <div className="min-w-0 flex-1 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Link href={`/ordenes/${n.orden_id}`} className="font-bold text-(--sw-ink) underline">
                {n.orden_codigo}
              </Link>
              <span className="text-(--sw-ink-soft)">· {n.cliente_nombre}</span>
              <ClayBadge color={resuelta ? "mint" : "peach"}>{resuelta ? "Resuelta" : "Pendiente"}</ClayBadge>
            </div>
            <p className="mt-1 font-semibold text-(--sw-ink)">{n.prenda_nombre}</p>
            <p className="mt-1 text-(--sw-ink)">{n.descripcion}</p>
            <p className="mt-1 text-xs text-(--sw-ink-soft)">
              {n.origen_nombre} · Registró {n.registrada_por ?? "Sistema"} el {FECHA_LEGIBLE.format(new Date(n.creado_en))}
            </p>
            {resuelta && n.decision_nombre && (
              <div className="mt-3 border-t border-(--sw-hairline) pt-2">
                <p className="text-(--sw-ink)">
                  Decisión: <strong>{n.decision_nombre}</strong>
                </p>
                {n.decision_observacion && <p className="mt-1 text-(--sw-ink-soft)">“{n.decision_observacion}”</p>}
                {n.decidida_por_nombre && n.decidida_en && (
                  <p className="mt-1 text-xs text-(--sw-ink-soft)">
                    Decidió {n.decidida_por_nombre} el {FECHA_LEGIBLE.format(new Date(n.decidida_en))}
                  </p>
                )}
                {Number(n.monto_descuento) > 0 && (
                  <p className="mt-1 text-(--sw-ink)">
                    Descuento{n.gravedad ? ` ${n.gravedad}` : ""}: {Number(n.porcentaje_descuento)} % (−{" "}
                    {formatCOP(n.monto_descuento)})
                  </p>
                )}
              </div>
            )}
          </div>
        </div>
      </ClayCard>
    </li>
  );
}

export default function HistorialNovedades({
  inicial,
  consultaInicial,
}: {
  inicial: Pagina<NovedadHistorial> | null;
  consultaInicial: string;
}) {
  const { filtros, datos, cargando, navegar, irAPagina } = useLista({
    ruta: "/novedades",
    leer: leerFiltrosHistorial,
    inicial,
    consultaInicial,
  });
  const conFiltros = hayFiltros(filtros, ["vista"]);
  const seleccion = (clave: "estado" | "origen" | "decision" | "gravedad", etiqueta: string, opciones: readonly (readonly [string, string])[]) => (
    <ClayField label={etiqueta}>
      <ClaySelect value={filtros[clave]} onChange={(e) => navegar({ [clave]: e.target.value })}>
        <option value="">Todas</option>
        {opciones.map(([valor, nombre]) => (
          <option key={valor} value={valor}>
            {nombre}
          </option>
        ))}
      </ClaySelect>
    </ClayField>
  );

  return (
    <>
      <ClayCard className="mb-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 lg:items-end">
          <div className="sm:col-span-2">
            <Buscador
              etiqueta="Buscar novedades"
              placeholder="Código, cliente, cédula, descripción o prenda"
              valor={filtros.buscar}
              onBuscar={(buscar) => navegar({ buscar }, { reemplazar: true })}
            />
          </div>
          {seleccion("estado", "Estado", [
            ["pendiente", "Pendientes"],
            ["resuelta", "Resueltas"],
          ])}
          {seleccion(
            "origen",
            "Origen",
            ORIGENES.map((o) => [o.valor, o.etiqueta] as const),
          )}
          {seleccion("decision", "Decisión", DECISIONES)}
          {seleccion(
            "gravedad",
            "Gravedad",
            GRAVEDADES.map((g) => [g.valor, g.etiqueta] as const),
          )}
          <FiltroFecha {...filtros} anios={datos?.anios ?? []} onCambiar={navegar} />
        </div>
        <LimpiarFiltros
          visible={conFiltros}
          onLimpiar={() =>
            navegar({ buscar: "", estado: "", origen: "", decision: "", gravedad: "", anio: "", mes: "", dia: "" })
          }
        />
      </ClayCard>

      <ResultadosLista
        datos={datos}
        cargando={cargando}
        conFiltros={conFiltros}
        sustantivo={["novedad", "novedades"]}
        vacio="Todavia no hay novedades registradas."
        onPagina={irAPagina}
      >
        {(novedades) => (
          <ul className="flex flex-col gap-4">
            {novedades.map((n) => (
              <TarjetaNovedad key={n.id} n={n} />
            ))}
          </ul>
        )}
      </ResultadosLista>
    </>
  );
}
