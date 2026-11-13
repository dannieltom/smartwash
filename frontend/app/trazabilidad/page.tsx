import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { consultaDeLista, getCurrentUser, getPagina, type AccionAuditoria } from "@/lib/api";
import { lectorDe, paginaDesde } from "../components/lista/url";
import { Encabezado } from "../components/ui/clay";
import { leerFiltrosTrazabilidad } from "./filtros";
import ListaTrazabilidad from "./lista-trazabilidad";

export default async function TrazabilidadPage({
  searchParams,
}: {
  searchParams: Promise<{ [clave: string]: string | string[] | undefined }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol !== "administrador") redirect("/");

  const lector = lectorDe(await searchParams);
  const consulta = consultaDeLista(leerFiltrosTrazabilidad(lector), paginaDesde(lector));
  const inicial = await getPagina<AccionAuditoria>(cookieStore, "/usuarios/trazabilidad", consulta);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Administracion · EP05" titulo="Trazabilidad">
        Seguimiento a las acciones de cada tipo de usuario: administrador, recepcionista,
        operario y cliente.
      </Encabezado>
      <p className="-mt-4 mb-6 text-sm">
        <Link href="/trazabilidad/actividad" className="font-bold text-(--sw-accent-text) underline">
          Ver la actividad de los operarios por etapa y turno
        </Link>
      </p>

      <ListaTrazabilidad inicial={inicial} consultaInicial={consulta} />
    </main>
  );
}
