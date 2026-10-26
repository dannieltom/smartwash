import type { Novedad } from "@/lib/api";
import { FECHA_LEGIBLE } from "@/lib/auditoria";
import { ClayBadge, ClayCard } from "../../components/ui/clay";

const DECISION: Record<NonNullable<Novedad["decision"]>, string> = {
  continuar: "Continuar igual",
  reprocesar: "Reprocesar",
  no_continuar: "No continuar",
};

export default function NovedadesOrden({ novedades }: { novedades: Novedad[] }) {
  if (novedades.length === 0) return null;

  return (
    <ClayCard className="mb-6">
      <h2 className="text-lg font-bold text-(--sw-ink)">Novedades</h2>
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
                  <ClayBadge color="mint">Decision del cliente: {DECISION[n.decision]}</ClayBadge>
                ) : (
                  <ClayBadge color="peach">Pendiente de decision del cliente</ClayBadge>
                )}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </ClayCard>
  );
}
