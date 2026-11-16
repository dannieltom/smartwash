"use client";

import { useRouter } from "next/navigation";
import { Fragment, useState } from "react";

import { actualizarReglaDescuento, leerErroresApi, type ReglaDescuento } from "@/lib/api";
import { formatCOP, formatFecha } from "@/lib/format";
import { ClayBadge, ClayButton, ClayCard } from "../components/ui/clay";
import { BuscadorLocal, useFiltroLocal } from "../components/lista/filtro-local";
import ReglaDescuentoForm from "./regla-form";

export default function TablaReglas({ reglas: todas }: { reglas: ReglaDescuento[] }) {
  const router = useRouter();
  const { texto, setTexto, filtradas: reglas } = useFiltroLocal(todas, (regla) => [
    regla.nombre,
    regla.clasificacion_cliente || "Cualquier cliente",
  ]);
  const [editandoId, setEditandoId] = useState<number | null>(null);
  const [ocupadoId, setOcupadoId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function alternarActiva(regla: ReglaDescuento) {
    setOcupadoId(regla.id);
    setError(null);
    const response = await actualizarReglaDescuento(regla.id, { activa: !regla.activa }).catch(() => null);
    setOcupadoId(null);

    if (response?.ok) {
      router.refresh();
      return;
    }
    const detalle = response ? Object.values(await leerErroresApi(response)).flat().join(" ") : "";
    setError(detalle || "No se pudo cambiar el estado de la regla.");
  }

  if (todas.length === 0) {
    return (
      <ClayCard>
        <p className="text-sm text-(--sw-ink-soft)">Todavia no hay reglas de descuento.</p>
      </ClayCard>
    );
  }

  return (
    <>
      <BuscadorLocal etiqueta="Buscar reglas" texto={texto} onCambiar={setTexto} />
      {reglas.length === 0 && (
        <ClayCard className="mb-4">
          <p className="text-sm text-(--sw-ink-soft)">Ninguna regla coincide con la búsqueda.</p>
        </ClayCard>
      )}
      {error && (
        <p role="alert" className="mb-4 text-sm font-medium text-(--sw-danger)">
          {error}
        </p>
      )}
      <ClayCard className="overflow-x-auto p-0">
        <table className="sw-tabla w-full text-left text-sm">
          <thead>
            <tr className="text-xs font-bold tracking-wide text-(--sw-ink-soft) uppercase">
              <th className="px-5 py-3">Regla</th>
              <th className="px-5 py-3">Valor</th>
              <th className="px-5 py-3">Aplica a</th>
              <th className="px-5 py-3">Vigencia</th>
              <th className="px-5 py-3">Estado</th>
              <th className="px-5 py-3">
                <span className="sr-only">Acciones</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {reglas.map((regla) => (
              <Fragment key={regla.id}>
                <tr className="border-t border-(--sw-hairline)">
                  <td data-label="Regla" className="px-5 py-3 font-semibold text-(--sw-ink)">{regla.nombre}</td>
                  <td data-label="Valor" className="px-5 py-3 text-(--sw-ink-soft) tabular-nums">
                    {regla.tipo === "porcentaje" ? `${regla.valor}%` : formatCOP(regla.valor)}
                  </td>
                  <td data-label="Aplica a" className="px-5 py-3 text-(--sw-ink-soft)">
                    {regla.clasificacion_cliente || "Cualquier cliente"}
                  </td>
                  <td data-label="Vigencia" className="px-5 py-3 text-(--sw-ink-soft)">
                    {formatFecha(regla.vigente_desde)}
                    {regla.vigente_hasta ? ` – ${formatFecha(regla.vigente_hasta)}` : " en adelante"}
                  </td>
                  <td data-label="Estado" className="px-5 py-3">
                    <ClayBadge color={regla.activa ? "mint" : "peach"}>
                      {regla.activa ? "Activa" : "Inactiva"}
                    </ClayBadge>
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex flex-wrap justify-end gap-2">
                      <ClayButton
                        type="button"
                        variant="secundario"
                        disabled={editandoId === regla.id}
                        onClick={() => setEditandoId(regla.id)}
                      >
                        Editar
                      </ClayButton>
                      <ClayButton
                        type="button"
                        variant="secundario"
                        disabled={ocupadoId === regla.id}
                        onClick={() => alternarActiva(regla)}
                      >
                        {ocupadoId === regla.id ? "..." : regla.activa ? "Desactivar" : "Activar"}
                      </ClayButton>
                    </div>
                  </td>
                </tr>
                {editandoId === regla.id && (
                  <tr className="bg-(--sw-bg-deep)/30">
                    <td colSpan={6} className="px-5 py-4">
                      <ReglaDescuentoForm regla={regla} onTerminar={() => setEditandoId(null)} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </ClayCard>
    </>
  );
}
