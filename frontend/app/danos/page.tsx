import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { consultaDeLista, getCurrentUser, getPagina, type DanoPrenda } from "@/lib/api";
import { lectorDe, paginaDesde } from "../components/lista/url";
import { Encabezado } from "../components/ui/clay";
import { leerFiltrosDanos } from "./filtros";
import ListaDanos from "./lista-danos";

export default async function DanosPage({
  searchParams,
}: {
  searchParams: Promise<{ [clave: string]: string | string[] | undefined }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol === "operario") redirect("/");

  const lector = lectorDe(await searchParams);
  const consulta = consultaDeLista(leerFiltrosDanos(lector), paginaDesde(lector));
  const inicial = await getPagina<DanoPrenda>(cookieStore, "/danos", consulta);
  const esAdmin = user.rol === "administrador";

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Entregas · HU19" titulo="Danos y perdidas">
        Prendas que la lavanderia dano o perdio. El valor declarado se le debe al cliente;
        {esAdmin ? " al pagarlo, registra como se pago." : " solo el administrador registra el pago."}
      </Encabezado>

      <ListaDanos inicial={inicial} consultaInicial={consulta} esAdmin={esAdmin} />
    </main>
  );
}
