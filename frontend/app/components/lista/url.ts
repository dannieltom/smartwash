import type { Filtros } from "@/lib/api";

/** Lo que se lee de la URL: URLSearchParams en el cliente, o un adaptador de los searchParams de la pagina. */
export type Lector = { get(clave: string): string | null };

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

/** Adapta los searchParams ya resueltos de una pagina del servidor. */
export function lectorDe(params: { [clave: string]: string | string[] | undefined }): Lector {
  return {
    get: (clave) => {
      const valor = params[clave];
      return typeof valor === "string" ? valor : null;
    },
  };
}

/** El numero entre 1 y `maximo` como texto, o "" si no es valido. */
export function numero(valor: string | null, maximo: number): string {
  return valor && /^\d+$/.test(valor) && Number(valor) >= 1 && Number(valor) <= maximo ? String(Number(valor)) : "";
}

/** El valor si es una de las opciones, o "". */
export function elegido(valor: string | null, opciones: readonly string[]): string {
  return valor && opciones.includes(valor) ? valor : "";
}

export function texto(valor: string | null, maximo = 100): string {
  return (valor ?? "").slice(0, maximo);
}

export function diasDelMes(anio: string, mes: string): number {
  return new Date(Number(anio), Number(mes), 0).getDate();
}

/** anio, mes y dia validos y encadenados: sin anio no hay mes, sin mes no hay dia. */
export function fechaDesde(params: Lector): { anio: string; mes: string; dia: string } {
  const anio = numero(params.get("anio"), 9998);
  const mes = anio ? numero(params.get("mes"), 12) : "";
  const dia = mes ? numero(params.get("dia"), diasDelMes(anio, mes)) : "";
  return { anio, mes, dia };
}

export function paginaDesde(params: Lector): number {
  return Number(numero(params.get("pagina"), 100000) || 1);
}

/** La URL de la lista: sin los filtros vacios y sin `pagina` cuando es la primera. */
export function urlDeLista(filtros: Filtros, pagina: number): string {
  const params = new URLSearchParams();
  for (const [clave, valor] of Object.entries(filtros)) {
    if (valor.trim()) params.set(clave, valor.trim());
  }
  if (pagina > 1) params.set("pagina", String(pagina));
  const consulta = params.toString();
  return consulta ? `?${consulta}` : "?";
}

export function hayFiltros(filtros: Filtros, ignorar: readonly string[] = []): boolean {
  return Object.entries(filtros).some(([clave, valor]) => !ignorar.includes(clave) && valor.trim() !== "");
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
