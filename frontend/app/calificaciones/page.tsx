import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getCalificaciones, getCurrentUser } from "@/lib/api";
import { FECHA_LEGIBLE } from "@/lib/auditoria";
import { Estrellas } from "../components/estrellas";
import { ClayButton, ClayCard, ClayField, ClayInput, Encabezado } from "../components/ui/clay";

const ES_FECHA = /^\d{4}-\d{2}-\d{2}$/;

function fecha(valor: string | string[] | undefined) {
  return typeof valor === "string" && ES_FECHA.test(valor) ? valor : "";
}

export default async function CalificacionesPage({
  searchParams,
}: {
  searchParams: Promise<{ [clave: string]: string | string[] | undefined }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol !== "administrador" && user.rol !== "recepcionista") redirect("/");

  const params = await searchParams;
  const desde = fecha(params.desde);
  const hasta = fecha(params.hasta);
  const resumen = await getCalificaciones(cookieStore, { desde, hasta });

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Postventa · EP06" titulo="Calificaciones">
        Lo que opinan los clientes de sus ordenes entregadas, desde el rastreo de pedidos.
      </Encabezado>

      <ClayCard className="mb-6">
        <form method="get" className="grid gap-4 sm:grid-cols-3 sm:items-end">
          <ClayField label="Desde">
            <ClayInput type="date" name="desde" defaultValue={desde} />
          </ClayField>
          <ClayField label="Hasta">
            <ClayInput type="date" name="hasta" defaultValue={hasta} />
          </ClayField>
          <div className="flex flex-wrap gap-2">
            <ClayButton type="submit">Filtrar</ClayButton>
            {(desde || hasta) && (
              <Link href="/calificaciones" className="self-center text-sm text-(--sw-ink-soft) hover:underline">
                Quitar filtros
              </Link>
            )}
          </div>
        </form>
      </ClayCard>

      {resumen === null ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">
            No se pudieron cargar las calificaciones. Revisa que la fecha hasta sea posterior a la fecha desde.
          </p>
        </ClayCard>
      ) : (
        <>
          <ClayCard className="mb-6">
            <dl className="grid grid-cols-2 gap-5">
              <div>
                <dt className="text-xs font-extrabold tracking-[0.08em] text-(--sw-ink-soft) uppercase">Promedio</dt>
                <dd className="mt-1 text-2xl font-bold text-(--sw-ink)">
                  {resumen.promedio === null ? "—" : `${resumen.promedio.toLocaleString("es-CO")} / 5`}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-extrabold tracking-[0.08em] text-(--sw-ink-soft) uppercase">Total</dt>
                <dd className="mt-1 text-2xl font-bold text-(--sw-ink)">{resumen.total}</dd>
              </div>
            </dl>
          </ClayCard>

          {resumen.calificaciones.length === 0 ? (
            <ClayCard>
              <p className="text-sm text-(--sw-ink-soft)">Todavia no hay calificaciones en este rango.</p>
            </ClayCard>
          ) : (
            <ClayCard className="overflow-x-auto p-0">
              <table className="sw-tabla w-full text-left text-sm">
                <thead>
                  <tr className="text-xs font-bold tracking-wide text-(--sw-ink-soft) uppercase">
                    <th className="px-5 py-3">Orden</th>
                    <th className="px-5 py-3">Cliente</th>
                    <th className="px-5 py-3">Estrellas</th>
                    <th className="px-5 py-3">Comentario</th>
                    <th className="px-5 py-3">Fecha</th>
                  </tr>
                </thead>
                <tbody>
                  {resumen.calificaciones.map((c) => (
                    <tr key={c.orden_id} className="border-t border-(--sw-hairline)">
                      <td data-label="Orden" className="px-5 py-3">
                        <Link href={`/ordenes/${c.orden_id}`} className="font-semibold text-(--sw-ink) hover:underline">
                          {c.orden_codigo}
                        </Link>
                      </td>
                      <td data-label="Cliente" className="px-5 py-3 text-(--sw-ink)">{c.cliente_nombre}</td>
                      <td data-label="Estrellas" className="px-5 py-3 whitespace-nowrap">
                        <Estrellas estrellas={c.estrellas} />
                      </td>
                      <td data-label="Comentario" className="px-5 py-3 text-(--sw-ink-soft)">
                        {c.comentario || "—"}
                      </td>
                      <td data-label="Fecha" className="px-5 py-3 whitespace-nowrap text-(--sw-ink-soft)">
                        {FECHA_LEGIBLE.format(new Date(c.creada_en))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ClayCard>
          )}
        </>
      )}
    </main>
  );
}
