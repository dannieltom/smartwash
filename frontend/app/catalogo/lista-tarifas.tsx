"use client";

import type { Pagina, Tarifa } from "@/lib/api";
import Buscador from "../components/lista/buscador";
import ResultadosLista, { LimpiarFiltros } from "../components/lista/resultados";
import { hayFiltros } from "../components/lista/url";
import { useLista } from "../components/lista/use-lista";
import { ClayCard, ClayField, ClaySelect } from "../components/ui/clay";
import { leerFiltrosTarifas } from "./filtros";
import TablaTarifas from "./tabla-tarifas";

/** Agrupadas por servicio y tipo de prenda (la general primero), tambien al paginar. */
export default function ListaTarifas({
  inicial,
  consultaInicial,
  editable,
}: {
  inicial: Pagina<Tarifa> | null;
  consultaInicial: string;
  editable: boolean;
}) {
  const { filtros, datos, cargando, navegar, irAPagina } = useLista({
    ruta: "/catalogo/tarifas",
    leer: leerFiltrosTarifas,
    inicial,
    consultaInicial,
  });
  const conFiltros = hayFiltros(filtros);

  return (
    <>
      <ClayCard className="mb-4">
        <div className="grid gap-4 sm:grid-cols-3 sm:items-end">
          <div className="sm:col-span-2">
            <Buscador
              etiqueta="Buscar tarifas"
              placeholder="Servicio o tipo de prenda"
              valor={filtros.buscar}
              onBuscar={(buscar) => navegar({ buscar }, { reemplazar: true })}
            />
          </div>
          <ClayField label="Vigencia">
            <ClaySelect value={filtros.vigentes} onChange={(e) => navegar({ vigentes: e.target.value })}>
              <option value="">Todas</option>
              <option value="1">Solo vigentes</option>
            </ClaySelect>
          </ClayField>
        </div>
        <LimpiarFiltros visible={conFiltros} onLimpiar={() => navegar({ buscar: "", vigentes: "" })} />
      </ClayCard>

      <ResultadosLista
        datos={datos}
        cargando={cargando}
        conFiltros={conFiltros}
        sustantivo={["tarifa", "tarifas"]}
        vacio="Todavia no hay tarifas."
        onPagina={irAPagina}
      >
        {(tarifas) => <TablaTarifas tarifas={tarifas} editable={editable} conTipo />}
      </ResultadosLista>
    </>
  );
}
