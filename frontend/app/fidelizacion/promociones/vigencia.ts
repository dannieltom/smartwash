import type { Promocion } from "@/lib/api";

export type EstadoPromocion = "Inactiva" | "Programada" | "Activa" | "Vencida";

// El backend guarda fechas sin hora y calcula "hoy" en Bogota; aqui se hace igual
// para que una promocion vigente hasta hoy no se marque vencida por el UTC del navegador.
export function hoyEnColombia(): string {
  return new Date().toLocaleDateString("en-CA", { timeZone: "America/Bogota" });
}

export function estadoDeVigencia(desde: string, hasta: string, hoy: string): Exclude<EstadoPromocion, "Inactiva"> {
  if (hoy < desde) return "Programada";
  if (hoy > hasta) return "Vencida";
  return "Activa";
}

export function estadoDePromocion(promocion: Promocion, hoy: string): EstadoPromocion {
  if (!promocion.activa) return "Inactiva";
  return estadoDeVigencia(promocion.vigente_desde, promocion.vigente_hasta, hoy);
}
