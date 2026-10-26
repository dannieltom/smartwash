import type { EventoOrden, Orden } from "@/lib/api";
import { FECHA_LEGIBLE } from "@/lib/auditoria";
import { hayQueLlamar, ultimoAviso } from "../avisos";

/** Resultado del aviso por correo de "orden lista" (HU31), para que recepcion
 * sepa si el cliente ya se entero o hay que llamarlo. */
export default function AvisoCliente({ orden, historial }: { orden: Orden; historial: EventoOrden[] }) {
  if (orden.estado !== "Lista para entrega") return null;
  const aviso = ultimoAviso(historial);
  if (!aviso) return null;

  if (hayQueLlamar(aviso)) {
    return (
      <div role="alert" className="clay-sm mb-6 border-l-8 border-l-(--sw-coral) p-4 text-sm">
        <p className="font-semibold text-(--sw-ink)">Llamar al cliente: no recibio el aviso por correo</p>
        <p className="mt-1 text-(--sw-ink-soft)">
          {aviso.detalle} ({FECHA_LEGIBLE.format(new Date(aviso.fecha))})
        </p>
      </div>
    );
  }

  return (
    <p className="mb-6 text-sm text-(--sw-ink-soft)">
      {aviso.detalle} ({FECHA_LEGIBLE.format(new Date(aviso.fecha))})
    </p>
  );
}
