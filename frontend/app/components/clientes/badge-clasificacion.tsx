import type { Cliente } from "@/lib/api";
import { formatCOP } from "@/lib/format";
import { ClayBadge } from "../ui/clay";

type Clasificacion = Cliente["clasificacion"];

const COLOR: Record<Clasificacion, "blue" | "mint" | "lavender"> = {
  Ocasional: "blue",
  Frecuente: "mint",
  VIP: "lavender",
};

// Espejo de clasificacion_por_consumo (backend/ordenes/models.py); si cambian los umbrales, cambian ambos.
const REGLAS: { clasificacion: Clasificacion; regla: string }[] = [
  { clasificacion: "Ocasional", regla: "Estado base inicial." },
  { clasificacion: "Frecuente", regla: "A partir de 3 ordenes entregadas." },
  { clasificacion: "VIP", regla: `A partir de 10 ordenes o ${formatCOP(500000)} consumidos.` },
];

export default function BadgeClasificacion({
  clasificacion,
  conReglas = false,
}: {
  clasificacion: Clasificacion;
  conReglas?: boolean;
}) {
  const badge = <ClayBadge color={COLOR[clasificacion]}>{clasificacion}</ClayBadge>;
  if (!conReglas) return badge;

  return (
    <span className="group relative inline-flex" tabIndex={0} aria-describedby="reglas-clasificacion">
      {badge}
      <span
        id="reglas-clasificacion"
        role="tooltip"
        className="clay-sm absolute top-full left-0 z-10 mt-2 hidden w-64 p-3 text-xs group-focus:block group-hover:block"
      >
        <span className="block font-bold text-(--sw-ink)">Como se clasifica</span>
        <ul className="mt-1 flex flex-col gap-1 text-(--sw-ink-soft)">
          {REGLAS.map((r) => (
            <li key={r.clasificacion}>
              <strong className="text-(--sw-ink)">{r.clasificacion}:</strong> {r.regla}
            </li>
          ))}
        </ul>
        <span className="mt-2 block text-(--sw-ink-soft)">
          Se actualiza sola al entregar una orden y no disminuye.
        </span>
      </span>
    </span>
  );
}
