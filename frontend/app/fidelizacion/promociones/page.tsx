import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getCurrentUser, getPromociones } from "@/lib/api";
import { ClayCard, Encabezado } from "../../components/ui/clay";
import PromocionForm from "./promocion-form";
import TablaPromociones from "./tabla-promociones";

export default async function PromocionesPage() {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol !== "administrador") redirect("/");

  const promociones = await getPromociones(cookieStore);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Link href="/fidelizacion" className="text-sm text-(--sw-ink-soft) hover:underline">
        ← Fidelizacion
      </Link>
      <Encabezado eyebrow="Administracion · EP08" titulo="Promociones">
        Campañas con fecha de inicio y de fin, asignadas a segmentos de clientes (HU28).
      </Encabezado>

      <ClayCard className="mb-6">
        <h2 className="sw-eyebrow">Nueva promocion</h2>
        <PromocionForm className="mt-4" />
      </ClayCard>

      {promociones === null ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">
            No se pudieron cargar las promociones. Verifica que el backend este en ejecucion.
          </p>
        </ClayCard>
      ) : (
        <TablaPromociones promociones={promociones} />
      )}
    </main>
  );
}
