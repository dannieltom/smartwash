"use client";

import Link from "next/link";

import type { CalificacionRegistrada, PaginaCalificaciones } from "@/lib/api";
import { FECHA_LEGIBLE } from "@/lib/auditoria";
import { Estrellas } from "../components/estrellas";
import Buscador from "../components/lista/buscador";
import ResultadosLista, { LimpiarFiltros } from "../components/lista/resultados";
import { hayFiltros } from "../components/lista/url";
import { useLista } from "../components/lista/use-lista";
import { ClayCard, ClayField, ClayInput, ClaySelect } from "../components/ui/clay";
import { leerFiltrosCalificaciones } from "./filtros";

function Tabla({ calificaciones }: { calificaciones: CalificacionRegistrada[] }) {
  return (
    <ClayCard className="overflow-x-auto p-0">
      <table className="sw-tabla w-full text-left text-sm">
        <thead>
          <tr className="text-xs font-bold tracking-wide text-(--sw-ink-soft) uppercase">
            <th className="px-5 py-3">Orden</th>
            <th className="px-5 py-3">Cliente</th>
            <th className="px-5 py-3">Estrellas</th>
            <th className="px-5 py-3">Comentario</th>
            <th className="px-5 py-3">Fecha</th>
          </tr>
        </thead>
        <tbody>
          {calificaciones.map((c) => (
            <tr key={c.orden_id} className="border-t border-(--sw-hairline)">
              <td data-label="Orden" className="px-5 py-3">
                <Link href={`/ordenes/${c.orden_id}`} className="font-semibold text-(--sw-ink) hover:underline">
                  {c.orden_codigo}
                </Link>
              </td>
              <td data-label="Cliente" className="px-5 py-3 text-(--sw-ink)">{c.cliente_nombre}</td>
              <td data-label="Estrellas" className="px-5 py-3 whitespace-nowrap">
                <Estrellas estrellas={c.estrellas} />
              </td>
              <td data-label="Comentario" className="px-5 py-3 text-(--sw-ink-soft)">{c.comentario || "—"}</td>
              <td data-label="Fecha" className="px-5 py-3 whitespace-nowrap text-(--sw-ink-soft)">
                {FECHA_LEGIBLE.format(new Date(c.creada_en))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ClayCard>
  );
}

export default function ListaCalificaciones({
  inicial,
  consultaInicial,
}: {
  inicial: PaginaCalificaciones | null;
  consultaInicial: string;
}) {
  const { filtros, datos, cargando, navegar, irAPagina } = useLista<
    ReturnType<typeof leerFiltrosCalificaciones>,
    CalificacionRegistrada,
    PaginaCalificaciones
  >({
    ruta: "/calificaciones",
    leer: leerFiltrosCalificaciones,
    inicial,
    consultaInicial,
  });
  const conFiltros = hayFiltros(filtros);

  return (
    <>
      <ClayCard className="mb-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
          <div className="sm:col-span-2">
            <Buscador
              etiqueta="Buscar calificaciones"
              placeholder="Código, cliente o comentario"
              valor={filtros.buscar}
              onBuscar={(buscar) => navegar({ buscar }, { reemplazar: true })}
            />
          </div>
          <ClayField label="Estrellas">
            <ClaySelect value={filtros.estrellas} onChange={(e) => navegar({ estrellas: e.target.value })}>
              <option value="">Todas</option>
              {[5, 4, 3, 2, 1].map((n) => (
                <option key={n} value={n}>
                  {n} {n === 1 ? "estrella" : "estrellas"}
                </option>
              ))}
            </ClaySelect>
          </ClayField>
          <ClayField label="Desde">
            <ClayInput type="date" value={filtros.desde} onChange={(e) => navegar({ desde: e.target.value })} />
          </ClayField>
          <ClayField label="Hasta">
            <ClayInput type="date" value={filtros.hasta} onChange={(e) => navegar({ hasta: e.target.value })} />
          </ClayField>
        </div>
        <LimpiarFiltros
          visible={conFiltros}
          onLimpiar={() => navegar({ buscar: "", estrellas: "", desde: "", hasta: "" })}
        />
      </ClayCard>

      {datos && (
        <ClayCard className="mb-6">
          <dl className="grid grid-cols-2 gap-5">
            <div>
              <dt className="text-xs font-extrabold tracking-[0.08em] text-(--sw-ink-soft) uppercase">Promedio</dt>
              <dd className="mt-1 text-2xl font-bold text-(--sw-ink)">
                {datos.promedio === null ? "—" : `${datos.promedio.toLocaleString("es-CO")} / 5`}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-extrabold tracking-[0.08em] text-(--sw-ink-soft) uppercase">Total</dt>
              <dd className="mt-1 text-2xl font-bold text-(--sw-ink)">{datos.total}</dd>
            </div>
          </dl>
        </ClayCard>
      )}

      <ResultadosLista
        datos={datos}
        cargando={cargando}
        conFiltros={conFiltros}
        sustantivo={["calificación", "calificaciones"]}
        vacio="Todavia no hay calificaciones."
        onPagina={irAPagina}
      >
        {(calificaciones) => <Tabla calificaciones={calificaciones} />}
      </ResultadosLista>
    </>
  );
}
