"use client";

import { Fragment, useState, type ReactNode } from "react";

import type { Material, NivelDificultad, Servicio, TipoPrenda } from "@/lib/api";
import { ClayButton, ClayCard } from "../components/ui/clay";
import MaterialForm from "./material-form";
import NivelForm from "./nivel-form";
import { BuscadorLocal, useFiltroLocal } from "../components/lista/filtro-local";
import ServicioForm from "./servicio-form";
import TipoPrendaForm from "./tipo-prenda-form";

type Columna = { titulo: string; valor: string };

function TablaEditable<T extends { id: number }>({
  filas: todas,
  editable,
  vacio,
  buscar,
  columnas,
  formulario,
}: {
  filas: T[];
  editable: boolean;
  vacio: string;
  /** Etiqueta del buscador, p. ej. "Buscar servicios". */
  buscar: string;
  columnas: (fila: T) => Columna[];
  formulario: (fila: T, terminar: () => void) => ReactNode;
}) {
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const { texto, setTexto, filtradas: filas } = useFiltroLocal(todas, (fila) => columnas(fila).map((c) => c.valor));

  if (todas.length === 0) {
    return (
      <ClayCard>
        <p className="text-sm text-(--sw-ink-soft)">{vacio}</p>
      </ClayCard>
    );
  }

  const buscador = <BuscadorLocal etiqueta={buscar} texto={texto} onCambiar={setTexto} />;
  if (filas.length === 0) {
    return (
      <>
        {buscador}
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">Ninguna fila coincide con la búsqueda.</p>
        </ClayCard>
      </>
    );
  }

  return (
    <>
    {buscador}
    <ClayCard className="overflow-x-auto p-0">
      <table className="sw-tabla w-full text-left text-sm">
        <thead>
          <tr className="text-xs font-bold tracking-wide text-(--sw-ink-soft) uppercase">
            {columnas(filas[0]).map((columna) => (
              <th key={columna.titulo} className="px-5 py-3">
                {columna.titulo}
              </th>
            ))}
            {editable && (
              <th className="px-5 py-3">
                <span className="sr-only">Acciones</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila) => {
            const celdas = columnas(fila);
            return (
              <Fragment key={fila.id}>
                <tr className="border-t border-(--sw-hairline)">
                  {celdas.map((celda, indice) => (
                    <td
                      key={celda.titulo}
                      data-label={celda.titulo}
                      className={
                        indice === 0
                          ? "px-5 py-3 font-semibold text-(--sw-ink)"
                          : "px-5 py-3 text-(--sw-ink-soft)"
                      }
                    >
                      {celda.valor || "—"}
                    </td>
                  ))}
                  {editable && (
                    <td className="px-5 py-3 text-right">
                      <ClayButton
                        type="button"
                        variant="secundario"
                        disabled={editandoId === fila.id}
                        onClick={() => setEditandoId(fila.id)}
                      >
                        Editar
                      </ClayButton>
                    </td>
                  )}
                </tr>
                {editandoId === fila.id && (
                  <tr className="bg-(--sw-bg-deep)/30">
                    <td colSpan={celdas.length + 1} className="px-5 py-4">
                      {formulario(fila, () => setEditandoId(null))}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </ClayCard>
    </>
  );
}

export function TablaTiposPrenda({ tiposPrenda, editable }: { tiposPrenda: TipoPrenda[]; editable: boolean }) {
  return (
    <TablaEditable
      filas={tiposPrenda}
      editable={editable}
      vacio="Todavia no hay tipos de prenda."
      buscar="Buscar tipos de prenda"
      columnas={(tipo) => [
        { titulo: "Tipo de prenda", valor: tipo.nombre },
        { titulo: "Peso estandar", valor: tipo.peso_estandar ? `${Number(tipo.peso_estandar)} kg` : "" },
      ]}
      formulario={(tipo, terminar) => <TipoPrendaForm tipoPrenda={tipo} onTerminar={terminar} />}
    />
  );
}

export function TablaNiveles({ niveles, editable }: { niveles: NivelDificultad[]; editable: boolean }) {
  return (
    <TablaEditable
      filas={niveles}
      editable={editable}
      vacio="Todavia no hay niveles de dificultad."
      buscar="Buscar niveles de dificultad"
      columnas={(nivel) => [
        { titulo: "Nivel de dificultad", valor: nivel.nombre },
        { titulo: "Factor", valor: `x${Number(nivel.factor)}` },
      ]}
      formulario={(nivel, terminar) => <NivelForm nivel={nivel} onTerminar={terminar} />}
    />
  );
}

export function TablaMateriales({
  materiales,
  niveles,
  editable,
}: {
  materiales: Material[];
  niveles: NivelDificultad[];
  editable: boolean;
}) {
  return (
    <TablaEditable
      filas={materiales}
      editable={editable}
      vacio="Todavia no hay materiales."
      buscar="Buscar materiales"
      columnas={(material) => [
        { titulo: "Material", valor: material.nombre },
        { titulo: "Nivel de dificultad", valor: material.nivel_dificultad_nombre },
        { titulo: "Factor", valor: `x${Number(material.factor)}` },
      ]}
      formulario={(material, terminar) => (
        <MaterialForm material={material} niveles={niveles} onTerminar={terminar} />
      )}
    />
  );
}

export function TablaServicios({ servicios, editable }: { servicios: Servicio[]; editable: boolean }) {
  return (
    <TablaEditable
      filas={servicios}
      editable={editable}
      vacio="Todavia no hay servicios."
      buscar="Buscar servicios"
      columnas={(servicio) => [
        { titulo: "Servicio", valor: servicio.nombre },
        { titulo: "Descripcion", valor: servicio.descripcion },
      ]}
      formulario={(servicio, terminar) => <ServicioForm servicio={servicio} onTerminar={terminar} />}
    />
  );
}
