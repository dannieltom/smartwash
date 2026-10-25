import Link from "next/link";

import { formatFecha } from "@/lib/format";
import type { AlertaOrden } from "@/lib/ordenes";
import { ClayCard } from "../../components/ui/clay";

const ESTILO = {
  retrasada: {
    borde: "border-l-red-600",
    badge: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  },
  proxima: {
    borde: "border-l-yellow-500",
    badge: "bg-yellow-100 text-yellow-900 dark:bg-yellow-950 dark:text-yellow-200",
  },
} as const;

function plural(dias: number, singular: string, pluralTexto: string) {
  return `${dias} ${dias === 1 ? singular : pluralTexto}`;
}

function etiqueta({ tipo, dias }: AlertaOrden) {
  if (tipo === "retrasada") return `Retrasada ${plural(dias, "dia", "dias")}`;
  return dias === 0 ? "Vence hoy" : `Vence en ${plural(dias, "dia", "dias")}`;
}

export default function ListaAlertas({ alertas }: { alertas: AlertaOrden[] }) {
  if (alertas.length === 0) {
    return (
      <ClayCard>
        <p className="text-sm text-(--sw-ink-soft)">Sin novedades</p>
      </ClayCard>
    );
  }

  return (
    <ul className="flex flex-col gap-4">
      {alertas.map((alerta) => (
        <li key={alerta.id}>
          <ClayCard className={`border-l-4 ${ESTILO[alerta.tipo].borde}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <Link href={`/ordenes/${alerta.id}`} className="font-bold text-(--sw-ink) hover:underline">
                  {alerta.codigo}
                </Link>
                <p className="mt-1 text-sm text-(--sw-ink-soft)">{alerta.cliente_nombre}</p>
                <p className="mt-1 text-xs text-(--sw-ink-soft)">
                  {alerta.estado} · Entrega estimada: {formatFecha(alerta.fecha_estimada_entrega)}
                </p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-xs font-semibold ${ESTILO[alerta.tipo].badge}`}
              >
                {etiqueta(alerta)}
              </span>
            </div>
          </ClayCard>
        </li>
      ))}
    </ul>
  );
}
