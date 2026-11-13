"use client";

import type { Pagina, UsuarioAdmin } from "@/lib/api";
import Buscador from "../components/lista/buscador";
import ResultadosLista, { LimpiarFiltros } from "../components/lista/resultados";
import { hayFiltros } from "../components/lista/url";
import { useLista } from "../components/lista/use-lista";
import { ClayCard, ClayField, ClaySelect } from "../components/ui/clay";
import { leerFiltrosUsuarios, ROLES } from "./filtros";
import TablaUsuarios from "./tabla-usuarios";

export default function ListaUsuarios({
  inicial,
  consultaInicial,
}: {
  inicial: Pagina<UsuarioAdmin> | null;
  consultaInicial: string;
}) {
  const { filtros, datos, cargando, navegar, irAPagina } = useLista({
    ruta: "/usuarios",
    leer: leerFiltrosUsuarios,
    inicial,
    consultaInicial,
  });
  const conFiltros = hayFiltros(filtros);

  return (
    <>
      <ClayCard className="mb-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 lg:items-end">
          <div className="sm:col-span-2">
            <Buscador
              etiqueta="Buscar usuarios"
              placeholder="Usuario, nombre, apellido o correo"
              valor={filtros.buscar}
              onBuscar={(buscar) => navegar({ buscar }, { reemplazar: true })}
            />
          </div>
          <ClayField label="Rol">
            <ClaySelect value={filtros.rol} onChange={(e) => navegar({ rol: e.target.value })}>
              <option value="">Todos</option>
              {ROLES.map((r) => (
                <option key={r.valor} value={r.valor}>
                  {r.etiqueta}
                </option>
              ))}
            </ClaySelect>
          </ClayField>
          <ClayField label="Estado">
            <ClaySelect value={filtros.activo} onChange={(e) => navegar({ activo: e.target.value })}>
              <option value="">Todos</option>
              <option value="true">Activos</option>
              <option value="false">Inactivos</option>
            </ClaySelect>
          </ClayField>
        </div>
        <LimpiarFiltros visible={conFiltros} onLimpiar={() => navegar({ buscar: "", rol: "", activo: "" })} />
      </ClayCard>

      <ResultadosLista
        datos={datos}
        cargando={cargando}
        conFiltros={conFiltros}
        sustantivo={["usuario", "usuarios"]}
        vacio="Todavia no hay usuarios."
        onPagina={irAPagina}
      >
        {(usuarios) => <TablaUsuarios usuarios={usuarios} />}
      </ResultadosLista>
    </>
  );
}
