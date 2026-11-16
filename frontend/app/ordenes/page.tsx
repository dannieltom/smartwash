import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { consultaDeLista, getCurrentUser, getPagina, type Orden } from "@/lib/api";
import { Encabezado, clayBtnClass } from "../components/ui/clay";
import { lectorDe, paginaDesde } from "../components/lista/url";
import { leerFiltrosOrdenes } from "./filtros";
import ListaOrdenes from "./lista-ordenes";

export default async function OrdenesPage({
  searchParams,
}: {
  searchParams: Promise<{ [clave: string]: string | string[] | undefined }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");

  const lector = lectorDe(await searchParams);
  const consulta = consultaDeLista(leerFiltrosOrdenes(lector), paginaDesde(lector));
  const inicial = await getPagina<Orden>(cookieStore, "/ordenes", consulta);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado
        eyebrow="Operacion · EP04"
        titulo="Ordenes"
        acciones={
          user.rol !== "operario" && (
            <Link href="/ordenes/nueva" className={clayBtnClass()}>
              Nueva orden
            </Link>
          )
        }
      >
        Sigue el estado de las ordenes en curso (EP04/EP05).
      </Encabezado>

      <ListaOrdenes inicial={inicial} consultaInicial={consulta} />
    </main>
  );
}
