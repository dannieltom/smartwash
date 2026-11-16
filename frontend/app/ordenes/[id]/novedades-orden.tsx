import type { ReactNode } from "react";

import type { Novedad } from "@/lib/api";
import { FECHA_LEGIBLE } from "@/lib/auditoria";
import { formatCOP } from "@/lib/format";
import { ClayBadge, ClayCard } from "../../components/ui/clay";

export const DECISION: Record<NonNullable<Novedad["decision"]>, string> = {
  continuar: "Continuar igual",
  agregar_servicio: "Agregar servicio",
  reprocesar: "Reprocesar",
  no_continuar: "No continuar",
  entregar_con_descuento: "Entregar con descuento",
  reprocesar_con_descuento: "Reprocesar con descuento",
};

export default function NovedadesOrden({
  novedades,
  encabezado,
  children,
}: {
  novedades: Novedad[];
  encabezado?: ReactNode;
  children?: ReactNode;
}) {
  if (novedades.length === 0) return null;

  return (
    <ClayCard className="mb-6">
      {encabezado ?? <h2 className="text-lg font-bold text-(--sw-ink)">Novedades</h2>}
      <ul className="mt-3 flex flex-col gap-4">
        {novedades.map((n) => (
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
                {n.origen_nombre} · {n.usuario_nombre ?? "Sistema"} · {FECHA_LEGIBLE.format(new Date(n.creado_en))}
              </p>
              <div className="mt-2">
                {n.decision ? (
                  <ClayBadge color={n.decision === "no_continuar" ? "peach" : "mint"}>
                    Decision del cliente: {DECISION[n.decision]}
                    {Number(n.monto_descuento) > 0 &&
                      ` · ${n.gravedad ? `${n.gravedad} ` : ""}${Number(n.porcentaje_descuento)} % (− ${formatCOP(n.monto_descuento)})`}
                    {n.decidida_por_nombre &&
                      n.decidida_en &&
                      ` · Decidió ${n.decidida_por_nombre} el ${FECHA_LEGIBLE.format(new Date(n.decidida_en))}`}
                  </ClayBadge>
                ) : (
                  <ClayBadge color="peach">Pendiente de decision del cliente</ClayBadge>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
      {children}
    </ClayCard>
  );
}
