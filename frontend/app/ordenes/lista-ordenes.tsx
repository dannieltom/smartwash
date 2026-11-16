"use client";

import type { Orden, Pagina } from "@/lib/api";
import Buscador from "../components/lista/buscador";
import FiltroFecha from "../components/lista/filtro-fecha";
import ResultadosLista, { LimpiarFiltros } from "../components/lista/resultados";
import { hayFiltros } from "../components/lista/url";
import { useLista } from "../components/lista/use-lista";
import { ClayCard, ClayField, ClaySelect } from "../components/ui/clay";
import { ESTADOS, leerFiltrosOrdenes } from "./filtros";
import TablaOrdenes from "./tabla-ordenes";

export default function ListaOrdenes({ inicial, consultaInicial }: { inicial: Pagina<Orden> | null; consultaInicial: string }) {
  const { filtros, datos, cargando, navegar, irAPagina } = useLista({
    ruta: "/ordenes",
    leer: leerFiltrosOrdenes,
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
              etiqueta="Buscar órdenes"
              placeholder="Código, nombre, apellido, cédula o teléfono"
              valor={filtros.buscar}
              onBuscar={(buscar) => navegar({ buscar }, { reemplazar: true })}
            />
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
        sustantivo={["orden", "órdenes"]}
        vacio="Todavia no hay ordenes registradas."
        onPagina={irAPagina}
      >
        {(ordenes) => <TablaOrdenes ordenes={ordenes} />}
      </ResultadosLista>
    </>
  );
}
