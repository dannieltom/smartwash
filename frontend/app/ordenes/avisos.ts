import type { EventoOrden } from "@/lib/api";

// El backend no marca el resultado con un campo propio: lo dice en el detalle.
// Los dos casos sin correo enviado ("No se pudo enviar el aviso..." y "El
// cliente no tiene correo registrado...") terminan pidiendo avisar por telefono.
export function hayQueLlamar(evento: EventoOrden): boolean {
  return evento.tipo_evento === "notificacion" && /avisar por tel[eé]fono/i.test(evento.detalle);
}

/** El aviso mas reciente al cliente, si la orden ya tiene alguno (HU31). */
export function ultimoAviso(historial: EventoOrden[]): EventoOrden | undefined {
  return historial.filter((e) => e.tipo_evento === "notificacion").at(-1);
}
