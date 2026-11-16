"use client";

import type { Cliente, Pagina } from "@/lib/api";
import Buscador from "../components/lista/buscador";
import ResultadosLista, { LimpiarFiltros } from "../components/lista/resultados";
import { hayFiltros } from "../components/lista/url";
import { useLista } from "../components/lista/use-lista";
import { ClayCard, ClayField, ClaySelect } from "../components/ui/clay";
import { CLASIFICACIONES, leerFiltrosClientes } from "./filtros";
import TablaClientes from "./tabla-clientes";

export default function ListaClientes({ inicial, consultaInicial }: { inicial: Pagina<Cliente> | null; consultaInicial: string }) {
  const { filtros, datos, cargando, navegar, irAPagina } = useLista({
    ruta: "/clientes",
    leer: leerFiltrosClientes,
    inicial,
    consultaInicial,
  });
  const conFiltros = hayFiltros(filtros);

  return (
    <>
      <ClayCard className="mb-6">
        <div className="grid gap-4 sm:grid-cols-3 sm:items-end">
          <div className="sm:col-span-2">
            <Buscador
              etiqueta="Buscar clientes"
              placeholder="Nombre, cédula, teléfono o correo"
              valor={filtros.buscar}
              onBuscar={(buscar) => navegar({ buscar }, { reemplazar: true })}
            />
          </div>
          <ClayField label="Clasificación">
            <ClaySelect value={filtros.clasificacion} onChange={(e) => navegar({ clasificacion: e.target.value })}>
              <option value="">Todas</option>
              {CLASIFICACIONES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </ClaySelect>
          </ClayField>
        </div>
        <LimpiarFiltros visible={conFiltros} onLimpiar={() => navegar({ buscar: "", clasificacion: "" })} />
      </ClayCard>

      <ResultadosLista
        datos={datos}
        cargando={cargando}
        conFiltros={conFiltros}
        sustantivo={["cliente", "clientes"]}
        vacio="Todavia no hay clientes registrados."
        onPagina={irAPagina}
      >
        {(clientes) => <TablaClientes clientes={clientes} />}
      </ResultadosLista>
    </>
  );
}
