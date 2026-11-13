"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { buscarPagina, consultaDeLista, type Filtros, type Pagina } from "@/lib/api";
import { paginaDesde, urlDeLista, type Lector } from "./url";

/** Lo ultimo que se cargo y para que consulta: si la URL pide otra, se esta cargando. */
type Cargado<T> = { datos: Pagina<T> | null; consulta: string };

/**
 * Filtros y pagina viven en la URL (refrescar, compartir y volver atras los conservan); la lista se
 * vuelve a pedir a `ruta` cada vez que cambian. `inicial` es lo que ya trajo la pagina del servidor.
 */
export function useLista<F extends Filtros, T>({
  ruta,
  leer,
  inicial,
  consultaInicial,
}: {
  ruta: string;
  leer: (params: Lector) => F;
  inicial: Pagina<T> | null;
  consultaInicial: string;
}) {
  const params = useSearchParams();
  const filtros = leer(params);
  const pagina = paginaDesde(params);
  const consulta = consultaDeLista(filtros, pagina);
  const [cargado, setCargado] = useState<Cargado<T>>({ datos: inicial, consulta: consultaInicial });
  const [inicialPrevio, setInicialPrevio] = useState(inicial);

  // router.refresh() (p. ej. al guardar un registro) vuelve a pintar la pagina del servidor con datos nuevos.
  if (inicial !== inicialPrevio) {
    setInicialPrevio(inicial);
    setCargado({ datos: inicial, consulta: consultaInicial });
  }

  useEffect(() => {
    if (consulta === cargado.consulta) return;
    const controlador = { cancelado: false };
    buscarPagina(ruta, consulta)
      .then(async (response) => (response.ok ? ((await response.json()) as Pagina<T>) : null))
      .catch(() => null)
      .then((datos) => {
        if (!controlador.cancelado) setCargado({ datos, consulta });
      });
    return () => {
      controlador.cancelado = true;
    };
  }, [ruta, consulta, cargado.consulta]);

  /** Cambiar un filtro vuelve a la pagina 1; solo la paginacion pide otra. */
  function navegar(cambios: Partial<F>, { pagina: nueva = 1, reemplazar = false } = {}) {
    const siguientes = { ...filtros, ...cambios };
    window.history[reemplazar ? "replaceState" : "pushState"](null, "", urlDeLista(siguientes, nueva));
  }

  return {
    filtros,
    pagina,
    datos: cargado.datos,
    cargando: consulta !== cargado.consulta,
    navegar,
    irAPagina: (nueva: number) => navegar({}, { pagina: nueva }),
  };
}
