"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { buscarOrdenes, consultaDeOrdenes, type FiltrosOrdenes, type PaginaOrdenes } from "@/lib/api";
import { ClayButton, ClayCard, ClayField, ClayInput, ClaySelect } from "../components/ui/clay";
import { diasDelMes, ESTADOS, filtrosDesde, hayFiltros, MESES, paginasVisibles, urlDe } from "./filtros";
import TablaOrdenes from "./tabla-ordenes";

const RETRASO_BUSQUEDA_MS = 300;

/** Lo ultimo que se cargo y para que consulta: si la URL pide otra, se esta cargando. */
type Cargado = { datos: PaginaOrdenes | null; consulta: string };

function Paginacion({ datos, onCambiar }: { datos: PaginaOrdenes; onCambiar: (pagina: number) => void }) {
  if (datos.total === 0) return null;
  const desde = (datos.pagina - 1) * datos.tamano + 1;
  const hasta = Math.min(datos.pagina * datos.tamano, datos.total);
  const boton =
    "clay-press min-w-10 rounded-full px-3 py-2 text-sm font-bold text-(--sw-ink) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--sw-ink) disabled:cursor-not-allowed disabled:opacity-40";

  return (
    <nav aria-label="Paginación" className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-(--sw-ink-soft)">
        {desde <= datos.total
          ? `Mostrando ${desde}–${hasta} de ${datos.total} ${datos.total === 1 ? "orden" : "órdenes"}`
          : `${datos.total} ${datos.total === 1 ? "orden" : "órdenes"} en total`}
      </p>
      {datos.paginas > 1 && (
        <ul className="flex flex-wrap items-center gap-2">
          <li>
            <button
              type="button"
              className={`${boton} bg-(--sw-surface)`}
              disabled={datos.pagina <= 1}
              onClick={() => onCambiar(datos.pagina - 1)}
            >
              Anterior
            </button>
          </li>
          {paginasVisibles(datos.pagina, datos.paginas).map((n, i) =>
            n === "…" ? (
              <li key={`elipsis-${i}`} aria-hidden="true" className="px-1 text-(--sw-ink-soft)">
                …
              </li>
            ) : (
              <li key={n}>
                <button
                  type="button"
                  className={`${boton} ${n === datos.pagina ? "bg-(--sw-accent)" : "bg-(--sw-surface)"}`}
                  aria-current={n === datos.pagina ? "page" : undefined}
                  aria-label={`Página ${n}`}
                  onClick={() => onCambiar(n)}
                >
                  {n}
                </button>
              </li>
            ),
          )}
          <li>
            <button
              type="button"
              className={`${boton} bg-(--sw-surface)`}
              disabled={datos.pagina >= datos.paginas}
              onClick={() => onCambiar(datos.pagina + 1)}
            >
              Siguiente
            </button>
          </li>
        </ul>
      )}
    </nav>
  );
}

export default function ListaOrdenes({ inicial, consultaInicial }: { inicial: PaginaOrdenes | null; consultaInicial: string }) {
  const filtros = filtrosDesde(useSearchParams());
  const consulta = consultaDeOrdenes(filtros);
  const [cargado, setCargado] = useState<Cargado>({ datos: inicial, consulta: consultaInicial });
  const [texto, setTexto] = useState(filtros.buscar);
  const [textoDeLaUrl, setTextoDeLaUrl] = useState(filtros.buscar);
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Al volver atras la URL trae otro texto: el campo lo adopta sin pisar lo que se esta escribiendo.
  if (filtros.buscar !== textoDeLaUrl) {
    setTextoDeLaUrl(filtros.buscar);
    setTexto(filtros.buscar);
  }

  useEffect(() => {
    if (consulta === cargado.consulta) return;
    const controlador = { cancelado: false };
    buscarOrdenes(filtrosDesde(new URLSearchParams(consulta)))
      .then(async (response) => (response.ok ? ((await response.json()) as PaginaOrdenes) : null))
      .catch(() => null)
      .then((datos) => {
        if (!controlador.cancelado) setCargado({ datos, consulta });
      });
    return () => {
      controlador.cancelado = true;
    };
  }, [consulta, cargado.consulta]);

  useEffect(() => () => {
    if (temporizador.current) clearTimeout(temporizador.current);
  }, []);

  function navegar(cambios: Partial<FiltrosOrdenes>, { reemplazar = false } = {}) {
    // Cambiar un filtro vuelve a la primera pagina; solo la paginacion conserva la pagina pedida.
    if (temporizador.current) clearTimeout(temporizador.current);
    const siguientes = { ...filtros, buscar: texto, pagina: 1, ...cambios };
    setTextoDeLaUrl(siguientes.buscar);
    window.history[reemplazar ? "replaceState" : "pushState"](null, "", urlDe(siguientes));
  }

  function escribir(valor: string) {
    setTexto(valor);
    if (temporizador.current) clearTimeout(temporizador.current);
    temporizador.current = setTimeout(() => navegar({ buscar: valor }, { reemplazar: true }), RETRASO_BUSQUEDA_MS);
  }

  function limpiar() {
    setTexto("");
    navegar({ buscar: "", estado: "", anio: "", mes: "", dia: "" });
  }

  const { datos } = cargado;
  const cargando = consulta !== cargado.consulta;
  const anios = datos?.anios ?? [];
  const dias = filtros.anio && filtros.mes ? diasDelMes(filtros.anio, filtros.mes) : 0;
  const conFiltros = hayFiltros(filtros) || texto.trim() !== "";

  return (
    <>
      <ClayCard className="mb-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6 lg:items-end">
          <div className="sm:col-span-2">
            <ClayField label="Buscar órdenes">
              <ClayInput
                type="search"
                name="buscar"
                value={texto}
                onChange={(e) => escribir(e.target.value)}
                placeholder="Código, nombre, apellido, cédula o teléfono"
                autoComplete="off"
              />
            </ClayField>
          </div>
          <ClayField label="Estado">
            <ClaySelect value={filtros.estado} onChange={(e) => navegar({ estado: e.target.value })}>
              <option value="">Todos</option>
              {ESTADOS.map((e) => (
                <option key={e} value={e}>
                  {e}
                </option>
              ))}
            </ClaySelect>
          </ClayField>
          <ClayField label="Año">
            <ClaySelect value={filtros.anio} onChange={(e) => navegar({ anio: e.target.value, mes: "", dia: "" })}>
              <option value="">Todos</option>
              {[...new Set([...anios, ...(filtros.anio ? [Number(filtros.anio)] : [])])]
                .sort((a, b) => b - a)
                .map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
            </ClaySelect>
          </ClayField>
          <ClayField label="Mes">
            <ClaySelect
              value={filtros.mes}
              disabled={!filtros.anio}
              onChange={(e) => navegar({ mes: e.target.value, dia: "" })}
            >
              <option value="">Todos</option>
              {MESES.map((nombre, i) => (
                <option key={nombre} value={i + 1}>
                  {nombre}
                </option>
              ))}
            </ClaySelect>
          </ClayField>
          <ClayField label="Día">
            <ClaySelect value={filtros.dia} disabled={!filtros.mes} onChange={(e) => navegar({ dia: e.target.value })}>
              <option value="">Todos</option>
              {Array.from({ length: dias }, (_, i) => i + 1).map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </ClaySelect>
          </ClayField>
        </div>
        {conFiltros && (
          <div className="mt-4">
            <ClayButton type="button" variant="secundario" onClick={limpiar}>
              Limpiar filtros
            </ClayButton>
          </div>
        )}
      </ClayCard>

      <p role="status" className="sr-only">
        {!cargando && datos ? `${datos.total} ${datos.total === 1 ? "orden encontrada" : "órdenes encontradas"}` : ""}
      </p>
      <div aria-busy={cargando} className={cargando ? "opacity-60 transition-opacity" : "transition-opacity"}>
        {cargando && <p className="mb-3 text-sm text-(--sw-ink-soft)">Cargando órdenes...</p>}
        {datos === null ? (
          !cargando && (
            <ClayCard>
              <p className="text-sm text-(--sw-ink-soft)">
                No se pudieron cargar las órdenes. Verifica que el backend esté en ejecución.
              </p>
            </ClayCard>
          )
        ) : datos.total === 0 && hayFiltros(filtros) ? (
          <ClayCard>
            <p className="text-sm text-(--sw-ink-soft)">No encontramos órdenes con esos filtros.</p>
          </ClayCard>
        ) : (
          <>
            {datos.resultados.length === 0 && datos.total > 0 ? (
              <ClayCard>
                <p className="text-sm text-(--sw-ink-soft)">Esta página no tiene órdenes.</p>
              </ClayCard>
            ) : (
              <TablaOrdenes ordenes={datos.resultados} />
            )}
            <Paginacion datos={datos} onCambiar={(pagina) => navegar({ pagina: pagina })} />
          </>
        )}
      </div>
    </>
  );
}
