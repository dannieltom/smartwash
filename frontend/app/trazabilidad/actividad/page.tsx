import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getActividad, getCurrentUser, getOperarios } from "@/lib/api";
import { DIA_ISO } from "@/lib/auditoria";
import { ClayButton, ClayCard, ClayField, ClayInput, ClaySelect, Encabezado } from "../../components/ui/clay";

const HORA_MINUTO = new Intl.DateTimeFormat("en-GB", {
  timeZone: "America/Bogota",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const FECHA_HORA = new Intl.DateTimeFormat("en-GB", {
  timeZone: "America/Bogota",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** dd/mm/aaaa hh:mm en hora de Bogota. */
function fechaHora(iso: string) {
  return FECHA_HORA.format(new Date(iso)).replace(",", "");
}

const ES_FECHA = /^\d{4}-\d{2}-\d{2}$/;
const ES_HORA = /^\d{2}:\d{2}$/;

export default async function ActividadPage({
  searchParams,
}: {
  searchParams: Promise<{ fecha?: string; desde?: string; hasta?: string; operario?: string }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol !== "administrador") redirect("/");

  const params = await searchParams;
  const ahora = new Date();
  const hoy = DIA_ISO.format(ahora);
  const fecha = params.fecha && ES_FECHA.test(params.fecha) ? params.fecha : hoy;
  const desde = params.desde && ES_HORA.test(params.desde) ? params.desde : "00:00";
  const hastaPorDefecto = fecha === hoy ? HORA_MINUTO.format(ahora) : "23:59";
  const hasta = params.hasta && ES_HORA.test(params.hasta) ? params.hasta : hastaPorDefecto;
  const operario = params.operario && /^\d+$/.test(params.operario) ? params.operario : "";

  const [actividad, operarios] = await Promise.all([
    getActividad(cookieStore, {
      desde: `${fecha}T${desde}:00-05:00`,
      hasta: `${fecha}T${hasta}:59-05:00`,
      operario,
    }),
    getOperarios(cookieStore),
  ]);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Link href="/trazabilidad" className="text-sm text-(--sw-ink-soft) hover:underline">
        ← Trazabilidad
      </Link>
      <Encabezado eyebrow="Administracion · HU10" titulo="Actividad de operarios">
        Que orden trabajaba cada operario y en que etapa, y los turnos del rango. Por ejemplo: hoy entre las 4 y
        las 6 de la tarde.
      </Encabezado>

      <ClayCard className="mb-6">
        <form method="get" className="grid gap-4 sm:grid-cols-5 sm:items-end">
          <ClayField label="Fecha">
            <ClayInput type="date" name="fecha" defaultValue={fecha} required />
          </ClayField>
          <ClayField label="Hora desde">
            <ClayInput type="time" name="desde" defaultValue={desde} required />
          </ClayField>
          <ClayField label="Hora hasta">
            <ClayInput type="time" name="hasta" defaultValue={hasta} required />
          </ClayField>
          <ClayField label="Operario">
            <ClaySelect name="operario" defaultValue={operario}>
              <option value="">Todos</option>
              {(operarios ?? []).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.nombre}
                </option>
              ))}
            </ClaySelect>
          </ClayField>
          <ClayButton type="submit">Ver actividad</ClayButton>
        </form>
      </ClayCard>

      {actividad === null ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">
            No se pudo cargar la actividad. Revisa que la hora hasta sea posterior a la hora desde.
          </p>
        </ClayCard>
      ) : (
        <>
          <h2 className="mb-3 text-lg font-bold text-(--sw-ink)">Etapas de trabajo</h2>
          {actividad.etapas.length === 0 ? (
            <ClayCard className="mb-6">
              <p className="text-sm text-(--sw-ink-soft)">Ningun operario trabajo ordenes en este rango.</p>
            </ClayCard>
          ) : (
            <ClayCard className="mb-6 overflow-x-auto p-0">
              <table className="sw-tabla w-full text-left text-sm">
                <thead>
                  <tr className="text-xs font-bold tracking-wide text-(--sw-ink-soft) uppercase">
                    <th className="px-5 py-3">Operario</th>
                    <th className="px-5 py-3">Orden</th>
                    <th className="px-5 py-3">Etapa</th>
                    <th className="px-5 py-3">Inicio</th>
                    <th className="px-5 py-3">Fin</th>
                  </tr>
                </thead>
                <tbody>
                  {actividad.etapas.map((e) => (
                    <tr key={`${e.orden}-${e.inicio}`} className="border-t border-(--sw-hairline)">
                      <td data-label="Operario" className="px-5 py-3 font-semibold text-(--sw-ink)">
                        {e.operario_nombre}
                      </td>
                      <td data-label="Orden" className="px-5 py-3">
                        <Link href={`/ordenes/${e.orden}`} className="font-semibold text-(--sw-ink) hover:underline">
                          {e.orden_codigo}
                        </Link>
                        <span className="block text-xs text-(--sw-ink-soft)">{e.cliente_nombre}</span>
                      </td>
                      <td data-label="Etapa" className="px-5 py-3 text-(--sw-ink)">{e.estado}</td>
                      <td data-label="Inicio" className="px-5 py-3 whitespace-nowrap text-(--sw-ink-soft)">
                        {fechaHora(e.inicio)}
                      </td>
                      <td data-label="Fin" className="px-5 py-3 whitespace-nowrap text-(--sw-ink-soft)">
                        {e.fin ? fechaHora(e.fin) : <strong className="text-(--sw-ink)">En curso</strong>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </ClayCard>
          )}

          <h2 className="mb-3 text-lg font-bold text-(--sw-ink)">Turnos</h2>
          {actividad.turnos.length === 0 ? (
            <ClayCard>
              <p className="text-sm text-(--sw-ink-soft)">No hubo turnos en este rango.</p>
            </ClayCard>
          ) : (
            <ClayCard className="p-0">
              <ul>
                {actividad.turnos.map((t) => (
                  <li
                    key={`${t.operario}-${t.inicio}`}
                    className="border-t border-(--sw-hairline) px-5 py-3 text-sm first:border-t-0"
                  >
                    <span className="font-semibold text-(--sw-ink)">{t.operario_nombre}</span>
                    <span className="text-(--sw-ink-soft)">
                      {" "}
                      · {fechaHora(t.inicio)} → {t.fin ? fechaHora(t.fin) : "en turno"}
                      {t.cierre === "automatico" && " (cerrado automaticamente)"}
                    </span>
                  </li>
                ))}
              </ul>
            </ClayCard>
          )}
        </>
      )}
    </main>
  );
}
