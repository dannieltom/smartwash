import type { Promocion } from "@/lib/api";
import { formatCOP, formatFecha } from "@/lib/format";
import { ClayBadge, ClayCard } from "../../components/ui/clay";
import { estadoDePromocion, hoyEnColombia, type EstadoPromocion } from "./vigencia";

const COLOR: Record<EstadoPromocion, "mint" | "blue" | "peach"> = {
  Activa: "mint",
  Programada: "blue",
  Vencida: "peach",
  Inactiva: "peach",
};

export default function TablaPromociones({ promociones }: { promociones: Promocion[] }) {
  if (promociones.length === 0) {
    return (
      <ClayCard>
        <p className="text-sm text-(--sw-ink-soft)">Todavia no hay promociones.</p>
      </ClayCard>
    );
  }

  const hoy = hoyEnColombia();
  return (
    <ClayCard className="overflow-x-auto p-0">
      <table className="sw-tabla w-full text-left text-sm">
        <thead>
          <tr className="text-xs font-bold tracking-wide text-(--sw-ink-soft) uppercase">
            <th className="px-5 py-3">Promocion</th>
            <th className="px-5 py-3">Beneficio</th>
            <th className="px-5 py-3">Segmentos</th>
            <th className="px-5 py-3">Vigencia</th>
            <th className="px-5 py-3">Estado</th>
          </tr>
        </thead>
        <tbody>
          {promociones.map((promocion) => {
            const estado = estadoDePromocion(promocion, hoy);
            return (
              <tr key={promocion.id} className="border-t border-(--sw-hairline)">
                <td data-label="Promocion" className="px-5 py-3 font-semibold text-(--sw-ink)">
                  {promocion.nombre}
                  {promocion.descripcion && (
                    <span className="block text-xs font-normal text-(--sw-ink-soft)">{promocion.descripcion}</span>
                  )}
                </td>
                <td data-label="Beneficio" className="px-5 py-3 text-(--sw-ink-soft) tabular-nums">
                  {promocion.tipo === "porcentaje" ? `${Number(promocion.valor)}%` : formatCOP(promocion.valor)}
                </td>
                <td data-label="Segmentos" className="px-5 py-3 text-(--sw-ink-soft)">
                  {promocion.segmentos.join(", ")}
                </td>
                <td data-label="Vigencia" className="px-5 py-3 text-(--sw-ink-soft)">
                  {formatFecha(promocion.vigente_desde)} – {formatFecha(promocion.vigente_hasta)}
                </td>
                <td data-label="Estado" className="px-5 py-3">
                  <ClayBadge color={COLOR[estado]}>{estado}</ClayBadge>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </ClayCard>
  );
}
