import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { getCambiosDescuentos, getConfiguracionDescuentos, getCurrentUser } from "@/lib/api";
import { FECHA_LEGIBLE } from "@/lib/auditoria";
import { ClayCard, Encabezado } from "../../components/ui/clay";
import DescuentosForm from "./descuentos-form";

export default async function DescuentosNovedadPage() {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol !== "administrador") redirect("/");

  const [configuracion, cambios] = await Promise.all([
    getConfiguracionDescuentos(cookieStore),
    getCambiosDescuentos(cookieStore),
  ]);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Administracion · HU19" titulo="Descuentos por novedad">
        Lo que se descuenta cuando una prenda sale con novedad en la entrega. Los cambios solo aplican a las
        decisiones nuevas: lo ya descontado conserva sus valores.
      </Encabezado>

      {configuracion === null ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">
            No se pudo cargar la configuracion. Verifica que el backend este en ejecucion.
          </p>
        </ClayCard>
      ) : (
        <ClayCard className="mb-6">
          <DescuentosForm configuracion={configuracion} />
        </ClayCard>
      )}

      <h2 className="mb-3 text-lg font-bold text-(--sw-ink)">Cambios</h2>
      {cambios === null || cambios.length === 0 ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">
            {cambios === null ? "No se pudieron cargar los cambios." : "Aun no se ha cambiado la configuracion."}
          </p>
        </ClayCard>
      ) : (
        <ClayCard className="p-0">
          <ul>
            {cambios.map((c) => (
              <li key={`${c.fecha}-${c.detalle}`} className="border-t border-(--sw-hairline) px-5 py-3 text-sm first:border-t-0">
                <p className="text-(--sw-ink)">{c.detalle}</p>
                <p className="mt-0.5 text-xs text-(--sw-ink-soft)">
                  {c.usuario_nombre} · {FECHA_LEGIBLE.format(new Date(c.fecha))}
                </p>
              </li>
            ))}
          </ul>
        </ClayCard>
      )}
    </main>
  );
}
