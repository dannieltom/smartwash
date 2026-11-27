import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getCurrentUser, getReglasDescuento } from "@/lib/api";
import { ClayCard, Encabezado } from "../components/ui/clay";
import EnviarComunicaciones from "./enviar-comunicaciones";
import ReglaDescuentoForm from "./regla-form";
import TablaReglas from "./tabla-reglas";

export default async function FidelizacionPage() {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol !== "administrador") redirect("/");

  const reglas = await getReglasDescuento(cookieStore);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Administracion · EP08" titulo="Fidelizacion">
        Configura reglas de descuento para tus clientes (HU08).{" "}
        <Link href="/fidelizacion/promociones" className="font-bold underline">
          Ver promociones
        </Link>
      </Encabezado>

      <ClayCard className="mb-6">
        <h2 className="sw-eyebrow">Comunicaciones a clientes</h2>
        <EnviarComunicaciones className="mt-4" />
      </ClayCard>

      <ClayCard className="mb-6">
        <h2 className="sw-eyebrow">Nueva regla de descuento</h2>
        <ReglaDescuentoForm className="mt-4" />
      </ClayCard>

      {reglas === null ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">
            No se pudieron cargar las reglas. Verifica que el backend este en ejecucion.
          </p>
        </ClayCard>
      ) : (
        <TablaReglas reglas={reglas} />
      )}
    </main>
  );
}
