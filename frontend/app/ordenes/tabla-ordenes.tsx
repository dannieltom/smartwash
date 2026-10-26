import Link from "next/link";

import type { Orden } from "@/lib/api";
import { formatCOP } from "@/lib/format";
import { ClayBadge, ClayCard } from "../components/ui/clay";
import EstadoAbono from "./abono";

export const COLOR_ESTADO: Record<Orden["estado"], "blue" | "mint" | "lavender" | "peach"> = {
  Recibida: "blue",
  Clasificada: "blue",
  "En proceso": "lavender",
  "Control de calidad": "lavender",
  "Lista para entrega": "mint",
  Entregada: "mint",
  Cancelada: "peach",
  "En espera": "peach",
  "Con novedad": "peach",
};

export default function TablaOrdenes({ ordenes }: { ordenes: Orden[] }) {
  if (ordenes.length === 0) {
    return (
      <ClayCard>
        <p className="text-sm text-(--sw-ink-soft)">Todavia no hay ordenes registradas.</p>
      </ClayCard>
    );
  }

  return (
    <ClayCard className="overflow-x-auto p-0">
      <table className="sw-tabla w-full text-left text-sm">
        <thead>
          <tr className="text-xs font-bold tracking-wide text-(--sw-ink-soft) uppercase">
            <th className="px-5 py-3">Codigo</th>
            <th className="px-5 py-3">Cliente</th>
            <th className="px-5 py-3">Estado</th>
            <th className="px-5 py-3">Pago</th>
            <th className="px-5 py-3">Abono</th>
            <th className="px-5 py-3">Total</th>
          </tr>
        </thead>
        <tbody>
          {ordenes.map((orden) => (
            <tr key={orden.id} className="border-t border-(--sw-hairline)">
              <td data-label="Codigo" className="px-5 py-3 font-semibold text-(--sw-ink)">
                <Link href={`/ordenes/${orden.id}`} className="hover:underline">
                  {orden.codigo}
                </Link>
              </td>
              <td data-label="Cliente" className="px-5 py-3 text-(--sw-ink-soft)">{orden.cliente_nombre}</td>
              <td data-label="Estado" className="px-5 py-3">
                <ClayBadge color={COLOR_ESTADO[orden.estado]}>{orden.estado}</ClayBadge>
              </td>
              <td data-label="Pago" className="px-5 py-3 text-(--sw-ink-soft)">{orden.estado_pago}</td>
              <td data-label="Abono" className="px-5 py-3">
                <EstadoAbono orden={orden} />
              </td>
              <td data-label="Total" className="px-5 py-3 font-semibold text-(--sw-ink) tabular-nums">
                {formatCOP(orden.valor_total)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ClayCard>
  );
}
