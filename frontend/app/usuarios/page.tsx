import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { consultaDeLista, getCurrentUser, getPagina, type UsuarioAdmin } from "@/lib/api";
import { lectorDe, paginaDesde } from "../components/lista/url";
import { ClayCard, Encabezado } from "../components/ui/clay";
import { leerFiltrosUsuarios } from "./filtros";
import ListaUsuarios from "./lista-usuarios";
import UsuarioForm from "./usuario-form";

export default async function UsuariosPage({
  searchParams,
}: {
  searchParams: Promise<{ [clave: string]: string | string[] | undefined }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol !== "administrador") redirect("/");

  const lector = lectorDe(await searchParams);
  const consulta = consultaDeLista(leerFiltrosUsuarios(lector), paginaDesde(lector));
  const inicial = await getPagina<UsuarioAdmin>(cookieStore, "/usuarios", consulta);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Administracion · EP01" titulo="Usuarios internos">
        Crea, edita y desactiva usuarios asignandoles un rol. El historial de cada usuario
        esta en su fila.
      </Encabezado>

      <ClayCard className="mb-6">
        <h2 className="sw-eyebrow">Nuevo usuario</h2>
        <UsuarioForm className="mt-4" />
      </ClayCard>

      <ListaUsuarios inicial={inicial} consultaInicial={consulta} />
    </main>
  );
}
