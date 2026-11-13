"use client";

import type { AccionAuditoria, Pagina } from "@/lib/api";
import Buscador from "../components/lista/buscador";
import FiltroFecha from "../components/lista/filtro-fecha";
import ResultadosLista, { LimpiarFiltros } from "../components/lista/resultados";
import { hayFiltros } from "../components/lista/url";
import { useLista } from "../components/lista/use-lista";
import { ClayCard, ClayField, ClaySelect } from "../components/ui/clay";
import { leerFiltrosTrazabilidad } from "./filtros";
import TablaTrazabilidad from "./tabla-trazabilidad";
import { TIPOS_USUARIO } from "./tipos";

export default function ListaTrazabilidad({
  inicial,
  consultaInicial,
}: {
  inicial: Pagina<AccionAuditoria> | null;
  consultaInicial: string;
}) {
  const { filtros, datos, cargando, navegar, irAPagina } = useLista({
    ruta: "/usuarios/trazabilidad",
    leer: leerFiltrosTrazabilidad,
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
              etiqueta="Buscar acciones"
              placeholder="Detalle, usuario o nombre"
              valor={filtros.buscar}
              onBuscar={(buscar) => navegar({ buscar }, { reemplazar: true })}
            />
          </div>
          <ClayField label="Tipo de usuario">
            <ClaySelect value={filtros.rol} onChange={(e) => navegar({ rol: e.target.value })}>
              <option value="">Todos</option>
              {TIPOS_USUARIO.map((tipo) => (
                <option key={tipo.valor} value={tipo.valor}>
                  {tipo.etiqueta}
                </option>
              ))}
            </ClaySelect>
          </ClayField>
          <FiltroFecha {...filtros} anios={datos?.anios ?? []} onCambiar={navegar} />
        </div>
        <LimpiarFiltros
          visible={conFiltros}
          onLimpiar={() => navegar({ buscar: "", rol: "", anio: "", mes: "", dia: "" })}
        />
      </ClayCard>

      <ResultadosLista
        datos={datos}
        cargando={cargando}
        conFiltros={conFiltros}
        sustantivo={["acción", "acciones"]}
        vacio="No hay acciones registradas."
        onPagina={irAPagina}
      >
        {(acciones) => <TablaTrazabilidad acciones={acciones} />}
      </ResultadosLista>
    </>
  );
}
