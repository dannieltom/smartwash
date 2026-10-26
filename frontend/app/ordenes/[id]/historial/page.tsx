import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getCurrentUser, getHistorialOrden, getOrden, type TipoEventoOrden } from "@/lib/api";
import { FECHA_LEGIBLE } from "@/lib/auditoria";
import { ClayBadge, ClayCard, Encabezado } from "../../../components/ui/clay";
import { hayQueLlamar } from "../../avisos";

const COLOR_EVENTO: Record<TipoEventoOrden, "blue" | "mint" | "lavender" | "peach"> = {
  creacion: "blue",
  pago: "mint",
  asignacion: "lavender",
  reasignacion: "lavender",
  cambio_estado: "blue",
  prenda_agregada: "peach",
  servicio_agregado: "peach",
  entrega: "mint",
  novedad: "peach",
  decision_novedad: "lavender",
  notificacion: "mint",
  cancelacion: "peach",
  devolucion: "peach",
};

function Mensaje({ children }: { children: string }) {
  return (
    <ClayCard>
      <p className="text-sm text-(--sw-ink-soft)">{children}</p>
    </ClayCard>
  );
}

export default async function HistorialOrdenPage({ params }: { params: Promise<{ id: string }> }) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");

  const id = Number((await params).id);
  if (user.rol === "operario") redirect(`/ordenes/${id}`);

  const [orden, historial] = await Promise.all([
    getOrden(id, cookieStore),
    getHistorialOrden(id, cookieStore),
  ]);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-8 sm:py-12">
      <Link href={`/ordenes/${id}`} className="text-sm text-(--sw-ink-soft) hover:underline">
        ← {orden ? orden.codigo : "Orden"}
      </Link>
      <Encabezado eyebrow="Orden · Historial" titulo="Historial de la orden">
        {orden ? `${orden.codigo} · ${orden.cliente_nombre}` : `Orden #${id}`}. Los registros no se pueden
        editar ni eliminar.
      </Encabezado>

      {historial === null ? (
        <Mensaje>No se pudo cargar el historial. Verifica que el backend este en ejecucion.</Mensaje>
      ) : historial.length === 0 ? (
        <Mensaje>Esta orden no tiene eventos registrados.</Mensaje>
      ) : (
        <ClayCard className="overflow-x-auto p-0">
          <table className="sw-tabla w-full text-left text-sm">
            <thead>
              <tr className="text-xs font-bold tracking-wide text-(--sw-ink-soft) uppercase">
                <th className="px-5 py-3">Fecha</th>
                <th className="px-5 py-3">Evento</th>
                <th className="px-5 py-3">Usuario</th>
                <th className="px-5 py-3">Detalle</th>
              </tr>
            </thead>
            <tbody>
              {historial.map((evento) => {
                const llamar = hayQueLlamar(evento);
                return (
                  <tr
                    key={evento.id}
                    className={`border-t border-(--sw-hairline) ${llamar ? "bg-(--sw-peach)/25" : ""}`}
                  >
                    <td data-label="Fecha" className="px-5 py-3 whitespace-nowrap text-(--sw-ink-soft)">
                      {FECHA_LEGIBLE.format(new Date(evento.fecha))}
                    </td>
                    <td data-label="Evento" className="px-5 py-3">
                      <ClayBadge color={llamar ? "peach" : (COLOR_EVENTO[evento.tipo_evento] ?? "blue")}>
                        {evento.tipo_evento_nombre}
                      </ClayBadge>
                    </td>
                    <td data-label="Usuario" className="px-5 py-3 text-(--sw-ink)">{evento.usuario_nombre}</td>
                    <td data-label="Detalle" className="px-5 py-3 text-(--sw-ink-soft)">
                      {llamar ? (
                        <>
                          <span className="font-semibold text-(--sw-ink)">Llamar al cliente.</span> {evento.detalle}
                        </>
                      ) : (
                        evento.detalle
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </ClayCard>
      )}
    </main>
  );
}
