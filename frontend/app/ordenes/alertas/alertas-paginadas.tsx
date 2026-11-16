"use client";

import type { AlertaOrden, Pagina } from "@/lib/api";
import Buscador from "../../components/lista/buscador";
import ResultadosLista, { LimpiarFiltros } from "../../components/lista/resultados";
import { hayFiltros } from "../../components/lista/url";
import { useLista } from "../../components/lista/use-lista";
import { ClayCard } from "../../components/ui/clay";
import { leerFiltrosAlertas } from "./filtros";
import ListaAlertas from "./lista-alertas";

/** Por urgencia (la mas retrasada primero), tambien al buscar y paginar. */
export default function AlertasPaginadas({
  inicial,
  consultaInicial,
}: {
  inicial: Pagina<AlertaOrden> | null;
  consultaInicial: string;
}) {
  const { filtros, datos, cargando, navegar, irAPagina } = useLista({
    ruta: "/ordenes/alertas",
    leer: leerFiltrosAlertas,
    inicial,
    consultaInicial,
  });
  const conFiltros = hayFiltros(filtros);

  return (
    <>
      <ClayCard className="mb-6">
        <Buscador
          etiqueta="Buscar alertas"
          placeholder="Código de la orden o cliente"
          valor={filtros.buscar}
          onBuscar={(buscar) => navegar({ buscar }, { reemplazar: true })}
        />
        <LimpiarFiltros visible={conFiltros} onLimpiar={() => navegar({ buscar: "" })} />
      </ClayCard>

      <ResultadosLista
        datos={datos}
        cargando={cargando}
        conFiltros={conFiltros}
        sustantivo={["alerta", "alertas"]}
        vacio="Sin novedades: ninguna orden esta retrasada ni proxima a vencer."
        onPagina={irAPagina}
      >
        {(alertas) => <ListaAlertas alertas={alertas} />}
      </ResultadosLista>
    </>
  );
}
