"use client";

import Link from "next/link";
import { Fragment, useState } from "react";

import type { Cliente } from "@/lib/api";
import { ClayBadge, ClayButton, ClayCard, clayBtnClass } from "../components/ui/clay";
import ClienteForm from "./cliente-form";

export default function TablaClientes({ clientes }: { clientes: Cliente[] }) {
  const [editandoId, setEditandoId] = useState<number | null>(null);

  if (clientes.length === 0) {
    return (
      <ClayCard>
        <p className="text-sm text-(--sw-ink-soft)">Todavia no hay clientes registrados.</p>
      </ClayCard>
    );
  }

  return (
    <ClayCard className="overflow-x-auto p-0">
      <table className="sw-tabla w-full text-left text-sm">
        <thead>
          <tr className="text-xs font-bold tracking-wide text-(--sw-ink-soft) uppercase">
            <th className="px-5 py-3">Nombre</th>
            <th className="px-5 py-3">Documento</th>
            <th className="px-5 py-3">Telefono</th>
            <th className="px-5 py-3">Clasificacion</th>
            <th className="px-5 py-3">
              <span className="sr-only">Acciones</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {clientes.map((cliente) => (
            <Fragment key={cliente.id}>
              <tr className="border-t border-(--sw-hairline)">
                <td data-label="Nombre" className="px-5 py-3 font-semibold text-(--sw-ink)">{cliente.nombre_completo}</td>
                <td data-label="Documento" className="px-5 py-3 text-(--sw-ink-soft)">{cliente.documento}</td>
                <td data-label="Telefono" className="px-5 py-3 text-(--sw-ink-soft)">{cliente.telefono}</td>
                <td data-label="Clasificacion" className="px-5 py-3">
                  <ClayBadge color="mint">{cliente.clasificacion}</ClayBadge>
                </td>
                <td className="px-5 py-3">
                  <div className="flex justify-end gap-2">
                    <Link href={`/clientes/${cliente.id}/ordenes`} className={clayBtnClass("secundario")}>
                      Historial
                    </Link>
                    <ClayButton
                      type="button"
                      variant="secundario"
                      disabled={editandoId === cliente.id}
                      onClick={() => setEditandoId(cliente.id)}
                    >
                      Editar
                    </ClayButton>
                  </div>
                </td>
              </tr>
              {editandoId === cliente.id && (
                <tr className="bg-(--sw-bg-deep)/30">
                  <td colSpan={5} className="px-5 py-4">
                    <ClienteForm cliente={cliente} onTerminar={() => setEditandoId(null)} />
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </ClayCard>
  );
}
