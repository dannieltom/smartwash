import type { Pagina } from "@/lib/api";
import { paginasVisibles } from "./url";

const BOTON =
  "clay-press min-w-10 rounded-full px-3 py-2 text-sm font-bold text-(--sw-ink) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--sw-ink) disabled:cursor-not-allowed disabled:opacity-40";

/** "Mostrando 21–40 de 134 ordenes", Anterior/Siguiente y 1 … 4 5 6 … 12. */
export default function Paginacion({
  datos,
  sustantivo,
  onCambiar,
}: {
  datos: Pick<Pagina<unknown>, "total" | "pagina" | "paginas" | "tamano">;
  /** [singular, plural]: ["orden", "órdenes"]. */
  sustantivo: [string, string];
  onCambiar: (pagina: number) => void;
}) {
  if (datos.total === 0) return null;
  const nombre = datos.total === 1 ? sustantivo[0] : sustantivo[1];
  const desde = (datos.pagina - 1) * datos.tamano + 1;
  const hasta = Math.min(datos.pagina * datos.tamano, datos.total);

  return (
    <nav aria-label="Paginación" className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-(--sw-ink-soft)">
        {desde <= datos.total ? `Mostrando ${desde}–${hasta} de ${datos.total} ${nombre}` : `${datos.total} ${nombre} en total`}
      </p>
      {datos.paginas > 1 && (
        <ul className="flex flex-wrap items-center gap-2">
          <li>
            <button
              type="button"
              className={`${BOTON} bg-(--sw-surface)`}
              disabled={datos.pagina <= 1}
              onClick={() => onCambiar(datos.pagina - 1)}
            >
              Anterior
            </button>
          </li>
          {paginasVisibles(datos.pagina, datos.paginas).map((n, i) =>
            n === "…" ? (
              <li key={`elipsis-${i}`} aria-hidden="true" className="px-1 text-(--sw-ink-soft)">
                …
              </li>
            ) : (
              <li key={n}>
                <button
                  type="button"
                  className={`${BOTON} ${n === datos.pagina ? "bg-(--sw-accent)" : "bg-(--sw-surface)"}`}
                  aria-current={n === datos.pagina ? "page" : undefined}
                  aria-label={`Página ${n}`}
                  onClick={() => onCambiar(n)}
                >
                  {n}
                </button>
              </li>
            ),
          )}
          <li>
            <button
              type="button"
              className={`${BOTON} bg-(--sw-surface)`}
              disabled={datos.pagina >= datos.paginas}
              onClick={() => onCambiar(datos.pagina + 1)}
            >
              Siguiente
            </button>
          </li>
        </ul>
      )}
    </nav>
  );
}
