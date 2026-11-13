"use client";

import type { DanoPrenda, Pagina } from "@/lib/api";
import Buscador from "../components/lista/buscador";
import FiltroFecha from "../components/lista/filtro-fecha";
import ResultadosLista, { LimpiarFiltros } from "../components/lista/resultados";
import { hayFiltros } from "../components/lista/url";
import { useLista } from "../components/lista/use-lista";
import { ClayCard, ClayField, ClaySelect } from "../components/ui/clay";
import { ESTADOS_DANO, leerFiltrosDanos } from "./filtros";
import TarjetaDano from "./tarjeta-dano";

export default function ListaDanos({
  inicial,
  consultaInicial,
  esAdmin,
}: {
  inicial: Pagina<DanoPrenda> | null;
  consultaInicial: string;
  esAdmin: boolean;
}) {
  const { filtros, datos, cargando, navegar, irAPagina } = useLista({
    ruta: "/danos",
    leer: leerFiltrosDanos,
    inicial,
    consultaInicial,
  });
  const conFiltros = hayFiltros(filtros);

  return (
    <>
      <ClayCard className="mb-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6 lg:items-end">
          <div className="sm:col-span-2">
            <Buscador
              etiqueta="Buscar daños"
              placeholder="Código, cliente, prenda u operario"
              valor={filtros.buscar}
              onBuscar={(buscar) => navegar({ buscar }, { reemplazar: true })}
            />
          </div>
          <ClayField label="Estado">
            <ClaySelect value={filtros.estado} onChange={(e) => navegar({ estado: e.target.value })}>
              <option value="">Todos</option>
              {ESTADOS_DANO.map((e) => (
                <option key={e.valor} value={e.valor}>
                  {e.etiqueta}
                </option>
              ))}
            </ClaySelect>
          </ClayField>
          <FiltroFecha {...filtros} anios={datos?.anios ?? []} onCambiar={navegar} />
        </div>
        <LimpiarFiltros
          visible={conFiltros}
          onLimpiar={() => navegar({ buscar: "", estado: "", anio: "", mes: "", dia: "" })}
        />
      </ClayCard>

      <ResultadosLista
        datos={datos}
        cargando={cargando}
        conFiltros={conFiltros}
        sustantivo={["daño", "daños"]}
        vacio="No hay daños ni pérdidas registrados."
        onPagina={irAPagina}
      >
        {(danos) => (
          <ul className="flex flex-col gap-4">
            {danos.map((d) => (
              <TarjetaDano key={d.id} d={d} esAdmin={esAdmin} />
            ))}
          </ul>
        )}
      </ResultadosLista>
    </>
  );
}
