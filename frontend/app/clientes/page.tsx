import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { consultaDeLista, getCurrentUser, getPagina, type Cliente } from "@/lib/api";
import { lectorDe, paginaDesde } from "../components/lista/url";
import { ClayCard, Encabezado } from "../components/ui/clay";
import ClienteForm from "./cliente-form";
import { leerFiltrosClientes } from "./filtros";
import ListaClientes from "./lista-clientes";

export default async function ClientesPage({
  searchParams,
}: {
  searchParams: Promise<{ [clave: string]: string | string[] | undefined }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol === "operario") redirect("/");

  const lector = lectorDe(await searchParams);
  const consulta = consultaDeLista(leerFiltrosClientes(lector), paginaDesde(lector));
  const inicial = await getPagina<Cliente>(cookieStore, "/clientes", consulta);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Administracion · EP02" titulo="Clientes">
        Registra y edita los datos de tus clientes.
      </Encabezado>

      <ClayCard className="mb-6">
        <h2 className="sw-eyebrow">Nuevo cliente</h2>
        <ClienteForm className="mt-4" />
      </ClayCard>

      <ListaClientes inicial={inicial} consultaInicial={consulta} />
    </main>
  );
}
