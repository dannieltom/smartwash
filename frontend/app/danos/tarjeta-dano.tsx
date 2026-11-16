import Link from "next/link";

import type { DanoPrenda } from "@/lib/api";
import { FECHA_LEGIBLE } from "@/lib/auditoria";
import { formatCOP } from "@/lib/format";
import { ClayBadge, ClayCard } from "../components/ui/clay";
import PagarDano from "./pagar-dano";

export default function TarjetaDano({ d, esAdmin }: { d: DanoPrenda; esAdmin: boolean }) {
  return (
    <li>
      <ClayCard>
        <div className="flex flex-wrap gap-4">
          {d.foto_url ? (
            <a href={d.foto_url} target="_blank" rel="noreferrer" title="Ver la foto completa">
              {/* eslint-disable-next-line @next/next/no-img-element -- la foto la sirve el backend con la sesion */}
              <img
                src={d.foto_url}
                alt={`Foto del dano en ${d.cantidad_afectada} de ${d.prenda_nombre}`}
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
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-semibold text-(--sw-ink)">
                {d.cantidad_afectada} de {d.prenda_nombre}
              </p>
              <ClayBadge color={d.tipo === "perdida" ? "lavender" : "peach"}>{d.tipo_nombre}</ClayBadge>
              <ClayBadge color={d.estado === "pagado" ? "mint" : "blue"}>{d.estado_nombre}</ClayBadge>
            </div>
            <p className="mt-1 text-(--sw-ink-soft)">
              <Link href={`/ordenes/${d.orden}`} className="font-semibold underline">
                {d.orden_codigo}
              </Link>{" "}
              · {d.cliente_nombre}
            </p>
            <p className="mt-1 text-(--sw-ink)">{d.descripcion}</p>
            <p className="mt-2 text-(--sw-ink)">
              Se le debe al cliente: <strong>{formatCOP(d.valor_declarado)}</strong>
              <span className="text-(--sw-ink-soft)">
                {" "}
                ({d.cantidad_afectada} × {formatCOP(d.valor_unitario_declarado)} por unidad) · servicio no
                cobrado {formatCOP(d.valor_servicio)}
              </span>
            </p>
            <p className="mt-1 text-xs text-(--sw-ink-soft)">
              Operario: {d.operario_nombre ?? "Sin asignar"} · Registro {d.registrado_por_nombre ?? "Sistema"}{" "}
              · {FECHA_LEGIBLE.format(new Date(d.creado_en))}
            </p>
            {d.estado === "pagado" && d.pagado_en && (
              <p className="mt-1 text-xs text-(--sw-ink-soft)">
                Pagado por {d.pagado_por_nombre ?? "Sistema"} · {FECHA_LEGIBLE.format(new Date(d.pagado_en))}
                {d.observacion_pago && ` · ${d.observacion_pago}`}
              </p>
            )}
          </div>
        </div>
        {esAdmin && d.estado === "pendiente" && <PagarDano dano={d} />}
      </ClayCard>
    </li>
  );
}
