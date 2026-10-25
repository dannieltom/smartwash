import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/api";
import { getAlertasOrdenes } from "@/lib/ordenes";
import { ClayCard, Encabezado } from "../../components/ui/clay";
import ListaAlertas from "./lista-alertas";

export default async function AlertasPage() {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");

  const alertas = await getAlertasOrdenes(cookieStore);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Operacion · Alertas" titulo="Alertas de vencimiento">
        Ordenes retrasadas y proximas a su fecha estimada de entrega.
      </Encabezado>

      {alertas === null ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">
            No se pudieron cargar las alertas. Verifica que el backend este en
            ejecucion.
          </p>
        </ClayCard>
      ) : (
        <ListaAlertas alertas={alertas} />
      )}
    </main>
  );
}
