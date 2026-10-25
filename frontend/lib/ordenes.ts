import type { EstadoOrden } from "@/lib/api";

/** Lo que devuelve OrdenAlertaSerializer. `dias` es el retraso si la orden esta
 * retrasada y lo que falta si esta proxima (0 = vence hoy). */
export interface AlertaOrden {
  id: number;
  codigo: string;
  cliente_nombre: string;
  estado: EstadoOrden | "Con novedad";
  operario: number | null;
  fecha_estimada_entrega: string;
  tipo: "retrasada" | "proxima";
  dias: number;
}

export async function getAlertasOrdenes(
  cookieStore: { toString(): string },
): Promise<AlertaOrden[] | null> {
  const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
  try {
    const response = await fetch(`${backend}/api/ordenes/alertas`, {
      headers: { cookie: cookieStore.toString() },
      cache: "no-store",
    });
    return response.ok ? ((await response.json()) as AlertaOrden[]) : null;
  } catch {
    return null;
  }
}
