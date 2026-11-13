import type { EstadoOrden, FiltrosOrdenes } from "@/lib/api";

export const ESTADOS: EstadoOrden[] = [
  "En espera",
  "Recibida",
  "Clasificada",
  "En proceso",
  "Control de calidad",
  "Con novedad",
  "Lista para entrega",
  "Entregada",
  "Cancelada",
];

export const MESES = [
  "enero",
  "febrero",
  "marzo",
  "abril",
  "mayo",
  "junio",
  "julio",
  "agosto",
  "septiembre",
  "octubre",
  "noviembre",
  "diciembre",
];

type Lector = { get(clave: string): string | null };

function numero(valor: string | null, maximo: number) {
  return valor && /^\d+$/.test(valor) && Number(valor) >= 1 && Number(valor) <= maximo ? String(Number(valor)) : "";
}

/** Lee los filtros de la URL descartando lo invalido, para no pedirle al backend algo que rechaza con 400. */
export function filtrosDesde(params: Lector): FiltrosOrdenes {
  const estado = params.get("estado") ?? "";
  const anio = numero(params.get("anio"), 9998);
  const mes = anio ? numero(params.get("mes"), 12) : "";
  const dia = mes ? numero(params.get("dia"), diasDelMes(anio, mes)) : "";
  return {
    buscar: (params.get("buscar") ?? "").slice(0, 100),
    estado: (ESTADOS as string[]).includes(estado) ? estado : "",
    anio,
    mes,
    dia,
    pagina: Number(numero(params.get("pagina"), 100000) || 1),
  };
}

/** La URL de la pagina: sin los filtros vacios y sin `pagina` cuando es la primera. */
export function urlDe(filtros: FiltrosOrdenes): string {
  const params = new URLSearchParams();
  for (const clave of ["buscar", "estado", "anio", "mes", "dia"] as const) {
    const valor = filtros[clave].trim();
    if (valor) params.set(clave, valor);
  }
  if (filtros.pagina > 1) params.set("pagina", String(filtros.pagina));
  const consulta = params.toString();
  return consulta ? `?${consulta}` : "?";
}

export function diasDelMes(anio: string, mes: string): number {
  return new Date(Number(anio), Number(mes), 0).getDate();
}

export function hayFiltros(filtros: FiltrosOrdenes): boolean {
  return Boolean(filtros.buscar.trim() || filtros.estado || filtros.anio);
}

/** 1 … 4 5 6 … 12: la primera, la ultima y las vecinas de la actual. */
export function paginasVisibles(actual: number, total: number): (number | "…")[] {
  const numeros = [...new Set([1, actual - 1, actual, actual + 1, total])]
    .filter((n) => n >= 1 && n <= total)
    .sort((a, b) => a - b);
  const resultado: (number | "…")[] = [];
  numeros.forEach((n, i) => {
    const anterior = numeros[i - 1];
    if (anterior !== undefined && n - anterior === 2) resultado.push(anterior + 1);
    else if (anterior !== undefined && n - anterior > 2) resultado.push("…");
    resultado.push(n);
  });
  return resultado;
}
