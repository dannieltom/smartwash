import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getCurrentUser, getHistorialCliente } from "@/lib/api";
import { FECHA_LEGIBLE } from "@/lib/auditoria";
import { formatCOP } from "@/lib/format";
import { ClayBadge, ClayCard, Encabezado } from "../../../components/ui/clay";
import { COLOR_ESTADO } from "../../../ordenes/tabla-ordenes";

export default async function HistorialClientePage({ params }: { params: Promise<{ id: string }> }) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol === "operario") redirect("/");

  const historial = await getHistorialCliente(Number((await params).id), cookieStore);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Link href="/clientes" className="text-sm text-(--sw-ink-soft) hover:underline">
        ← Clientes
      </Link>

      {historial === null ? (
        <ClayCard className="mt-6">
          <p className="text-sm text-(--sw-ink-soft)">
            No se encontro el cliente o no se pudo cargar su historial. Verifica que el backend este en
            ejecucion.
          </p>
        </ClayCard>
      ) : (
        <>
          <Encabezado eyebrow="Clientes · Historial de ordenes" titulo={historial.cliente.nombre_completo} />

          <ClayCard className="mb-6">
            <dl className="grid grid-cols-2 gap-5">
              <div>
                <dt className="text-xs font-semibold tracking-wide text-(--sw-ink-soft) uppercase">Ordenes</dt>
                <dd className="mt-1 text-2xl font-bold text-(--sw-ink) tabular-nums">{historial.numero_ordenes}</dd>
              </div>
              <div>
                <dt className="text-xs font-semibold tracking-wide text-(--sw-ink-soft) uppercase">
                  Total comprado
                </dt>
                <dd className="mt-1 text-2xl font-bold text-(--sw-ink) tabular-nums">
                  {formatCOP(historial.total_comprado)}
                </dd>
              </div>
            </dl>
            <p className="mt-3 text-xs text-(--sw-ink-soft)">
              El total comprado no incluye las ordenes canceladas.
            </p>
          </ClayCard>

          {historial.ordenes.length === 0 ? (
            <ClayCard>
              <p className="text-sm text-(--sw-ink-soft)">Este cliente no tiene ordenes previas.</p>
            </ClayCard>
          ) : (
            <ClayCard className="overflow-x-auto p-0">
              <table className="sw-tabla w-full text-left text-sm">
                <thead>
                  <tr className="text-xs font-bold tracking-wide text-(--sw-ink-soft) uppercase">
                    <th className="px-5 py-3">Codigo</th>
                    <th className="px-5 py-3">Fecha</th>
                    <th className="px-5 py-3">Estado</th>
                    <th className="px-5 py-3">Total</th>
                    <th className="px-5 py-3">Pago</th>
                  </tr>
                </thead>
                <tbody>
                  {historial.ordenes.map((orden) => (
                    <tr key={orden.id} className="border-t border-(--sw-hairline)">
                      <td data-label="Codigo" className="px-5 py-3 font-semibold text-(--sw-ink)">
                        <Link href={`/ordenes/${orden.id}`} className="hover:underline">
                          {orden.codigo}
                        </Link>
                      </td>
                      <td data-label="Fecha" className="px-5 py-3 whitespace-nowrap text-(--sw-ink-soft)">
                        {FECHA_LEGIBLE.format(new Date(orden.creado_en))}
                      </td>
                      <td data-label="Estado" className="px-5 py-3">
                        <ClayBadge color={COLOR_ESTADO[orden.estado] ?? "blue"}>{orden.estado}</ClayBadge>
                      </td>
                      <td data-label="Total" className="px-5 py-3 font-semibold text-(--sw-ink) tabular-nums">
                        {formatCOP(orden.valor_total)}
                      </td>
                      <td data-label="Pago" className="px-5 py-3 text-(--sw-ink-soft)">{orden.estado_pago}</td>
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
