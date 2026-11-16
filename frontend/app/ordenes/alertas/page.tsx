import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { consultaDeLista, getCurrentUser, getPagina, type AlertaOrden } from "@/lib/api";
import { lectorDe, paginaDesde } from "../../components/lista/url";
import { Encabezado } from "../../components/ui/clay";
import AlertasPaginadas from "./alertas-paginadas";
import { leerFiltrosAlertas } from "./filtros";

export default async function AlertasPage({
  searchParams,
}: {
  searchParams: Promise<{ [clave: string]: string | string[] | undefined }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");

  const lector = lectorDe(await searchParams);
  const consulta = consultaDeLista(leerFiltrosAlertas(lector), paginaDesde(lector));
  const inicial = await getPagina<AlertaOrden>(cookieStore, "/ordenes/alertas", consulta);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Operacion · Alertas" titulo="Alertas de vencimiento">
        Ordenes retrasadas y proximas a su fecha estimada de entrega.
      </Encabezado>

      <AlertasPaginadas inicial={inicial} consultaInicial={consulta} />
    </main>
  );
}
