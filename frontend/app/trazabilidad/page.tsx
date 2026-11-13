import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getCurrentUser, getTrazabilidad, type TipoUsuarioAuditoria } from "@/lib/api";
import { ClayCard, Encabezado } from "../components/ui/clay";
import FiltroTipo from "./filtro-tipo";
import TablaTrazabilidad from "./tabla-trazabilidad";
import { TIPOS_USUARIO } from "./tipos";

export default async function TrazabilidadPage({
  searchParams,
}: {
  searchParams: Promise<{ rol?: string }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol !== "administrador") redirect("/");

  const { rol } = await searchParams;
  const rolValido = TIPOS_USUARIO.some((t) => t.valor === rol)
    ? (rol as TipoUsuarioAuditoria)
    : undefined;

  const acciones = await getTrazabilidad(cookieStore, rolValido);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado
        eyebrow="Administracion · EP05"
        titulo="Trazabilidad"
        acciones={<FiltroTipo tipoActual={rolValido} />}
      >
        Seguimiento a las acciones de cada tipo de usuario: administrador, recepcionista,
        operario y cliente.
      </Encabezado>
      <p className="-mt-4 mb-6 text-sm">
        <Link href="/trazabilidad/actividad" className="font-bold text-(--sw-accent-text) underline">
          Ver la actividad de los operarios por etapa y turno
        </Link>
      </p>

      {acciones === null ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">
            No se pudo cargar la trazabilidad. Verifica que el backend este en ejecucion.
          </p>
        </ClayCard>
      ) : (
        <TablaTrazabilidad acciones={acciones} />
      )}
    </main>
  );
}
