import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { consultaDeLista, getCurrentUser, getPagina, type CalificacionRegistrada, type PaginaCalificaciones } from "@/lib/api";
import { lectorDe, paginaDesde } from "../components/lista/url";
import { Encabezado } from "../components/ui/clay";
import { leerFiltrosCalificaciones } from "./filtros";
import ListaCalificaciones from "./lista-calificaciones";

export default async function CalificacionesPage({
  searchParams,
}: {
  searchParams: Promise<{ [clave: string]: string | string[] | undefined }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol !== "administrador" && user.rol !== "recepcionista") redirect("/");

  const lector = lectorDe(await searchParams);
  const consulta = consultaDeLista(leerFiltrosCalificaciones(lector), paginaDesde(lector));
  const inicial = await getPagina<CalificacionRegistrada, PaginaCalificaciones>(cookieStore, "/calificaciones", consulta);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Postventa · EP06" titulo="Calificaciones">
        Lo que opinan los clientes de sus ordenes entregadas, desde el rastreo de pedidos.
      </Encabezado>

      <ListaCalificaciones inicial={inicial} consultaInicial={consulta} />
    </main>
  );
}
