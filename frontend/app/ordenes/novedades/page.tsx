import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { getCurrentUser, getOrdenesConNovedad } from "@/lib/api";
import { ClayCard, Encabezado } from "../../components/ui/clay";
import ListaNovedades from "./lista-novedades";

function Mensaje({ titulo, children }: { titulo?: string; children: string }) {
  return (
    <ClayCard>
      {titulo && <h2 className="text-lg font-bold text-(--sw-ink)">{titulo}</h2>}
      <p className="text-sm text-(--sw-ink-soft)">{children}</p>
    </ClayCard>
  );
}

export default async function NovedadesPage() {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");

  const autorizado = user.rol === "administrador" || user.rol === "recepcionista";
  const ordenes = autorizado ? await getOrdenesConNovedad(cookieStore) : null;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Operacion · Novedades" titulo="Ordenes con novedad">
        Registra la decision del cliente sobre las novedades pendientes.
      </Encabezado>

      {!autorizado ? (
        <Mensaje titulo="Acceso denegado">
          Solo el administrador y la recepcion pueden ver las ordenes con novedad.
        </Mensaje>
      ) : ordenes === null ? (
        <Mensaje>No se pudieron cargar las novedades. Verifica que el backend este en ejecucion.</Mensaje>
      ) : (
        <ListaNovedades ordenes={ordenes} />
      )}
    </main>
  );
}
