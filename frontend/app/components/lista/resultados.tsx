import type { ReactNode } from "react";

import type { Pagina } from "@/lib/api";
import { ClayButton, ClayCard } from "../ui/clay";
import Paginacion from "./paginacion";

export function LimpiarFiltros({ visible, onLimpiar }: { visible: boolean; onLimpiar: () => void }) {
  if (!visible) return null;
  return (
    <div className="mt-4">
      <ClayButton type="button" variant="secundario" onClick={onLimpiar}>
        Limpiar filtros
      </ClayButton>
    </div>
  );
}

function Aviso({ children }: { children: ReactNode }) {
  return (
    <ClayCard>
      <p className="text-sm text-(--sw-ink-soft)">{children}</p>
    </ClayCard>
  );
}

/** Carga, error y vacio iguales en todas las listas, con la paginacion debajo. */
export default function ResultadosLista<T>({
  datos,
  cargando,
  conFiltros,
  sustantivo,
  vacio,
  onPagina,
  children,
}: {
  datos: Pagina<T> | null;
  cargando: boolean;
  conFiltros: boolean;
  /** [singular, plural]: ["cliente", "clientes"]. */
  sustantivo: [string, string];
  /** El mensaje cuando no hay ningun registro, sin filtros. */
  vacio: string;
  onPagina: (pagina: number) => void;
  children: (resultados: T[]) => ReactNode;
}) {
  return (
    <>
      <p role="status" className="sr-only">
        {!cargando && datos ? `${datos.total} ${datos.total === 1 ? sustantivo[0] : sustantivo[1]}` : ""}
      </p>
      <div aria-busy={cargando} className={cargando ? "opacity-60 transition-opacity" : "transition-opacity"}>
        {cargando && <p className="mb-3 text-sm text-(--sw-ink-soft)">Cargando {sustantivo[1]}...</p>}
        {datos === null ? (
          !cargando && <Aviso>No se pudieron cargar las {sustantivo[1]}. Verifica que el backend esté en ejecución.</Aviso>
        ) : datos.total === 0 ? (
          <Aviso>{conFiltros ? `No encontramos ${sustantivo[1]} con esos filtros.` : vacio}</Aviso>
        ) : (
          <>
            {datos.resultados.length === 0 ? <Aviso>Esta página no tiene {sustantivo[1]}.</Aviso> : children(datos.resultados)}
            <Paginacion datos={datos} sustantivo={sustantivo} onCambiar={onPagina} />
          </>
        )}
      </div>
    </>
  );
}
