"use client";

import Link from "next/link";
import { useState } from "react";

import type { OrdenConNovedad } from "@/lib/api";
import { FECHA_LEGIBLE } from "@/lib/auditoria";
import { ClayBadge, ClayButton, ClayCard, clayBtnClass } from "../../components/ui/clay";
import ModalDecisionProceso from "./modal-decision-proceso";

export default function ListaNovedades({ ordenes }: { ordenes: OrdenConNovedad[] }) {
  const [enDecision, setEnDecision] = useState<OrdenConNovedad | null>(null);

  if (ordenes.length === 0) {
    return (
      <ClayCard>
        <p className="text-sm text-(--sw-ink-soft)">No hay ordenes con novedad pendientes de decision.</p>
      </ClayCard>
    );
  }

  return (
    <>
      <ul className="flex flex-col gap-4">
        {ordenes.map((orden) => {
          const esDeEntrega = orden.novedades.every((n) => n.origen === "entrega");
          return (
            <li key={orden.id}>
              <ClayCard>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-bold text-(--sw-ink)">{orden.codigo}</p>
                    <p className="mt-1 text-sm text-(--sw-ink-soft)">{orden.cliente_nombre}</p>
                  </div>
                  {esDeEntrega ? (
                    <Link href={`/ordenes/${orden.id}`} className={clayBtnClass("secundario")}>
                      Ver orden y decidir
                    </Link>
                  ) : (
                    <ClayButton type="button" onClick={() => setEnDecision(orden)}>
                      Registrar decision
                    </ClayButton>
                  )}
                </div>

                <ul className="mt-4 flex flex-col gap-4">
                  {orden.novedades.map((n) => (
                    <li key={n.id} className="flex flex-wrap gap-4 border-t border-(--sw-hairline) pt-3">
                      {n.foto_url ? (
                        <a href={n.foto_url} target="_blank" rel="noreferrer" title="Ver la foto completa">
                          {/* eslint-disable-next-line @next/next/no-img-element -- la foto la sirve el backend con la sesion */}
                          <img
                            src={n.foto_url}
                            alt={`Foto de la novedad en ${n.prenda_nombre}`}
                            className="h-24 w-24 rounded-xl object-cover"
                            loading="lazy"
                          />
                        </a>
                      ) : (
                        <div className="flex h-24 w-24 items-center justify-center rounded-xl bg-(--sw-surface) text-xs text-(--sw-ink-soft)">
                          Sin foto
                        </div>
                      )}
                      <div className="min-w-0 flex-1 text-sm">
                        <p className="font-semibold text-(--sw-ink)">{n.prenda_nombre}</p>
                        <p className="mt-1 text-(--sw-ink)">{n.descripcion}</p>
                        <p className="mt-1 text-xs text-(--sw-ink-soft)">
                          {n.usuario_nombre ?? "Sistema"} · {FECHA_LEGIBLE.format(new Date(n.creado_en))}
                        </p>
                        <div className="mt-2">
                          <ClayBadge color={n.origen === "proceso" ? "lavender" : "peach"}>
                            {n.origen_nombre}
                          </ClayBadge>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </ClayCard>
            </li>
          );
        })}
      </ul>

      {enDecision && <ModalDecisionProceso orden={enDecision} onCerrar={() => setEnDecision(null)} />}
    </>
  );
}
