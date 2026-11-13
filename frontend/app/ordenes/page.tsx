import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { consultaDeOrdenes, getCurrentUser, getOrdenesPagina } from "@/lib/api";
import { Encabezado, clayBtnClass } from "../components/ui/clay";
import { filtrosDesde } from "./filtros";
import ListaOrdenes from "./lista-ordenes";

export default async function OrdenesPage({
  searchParams,
}: {
  searchParams: Promise<{ [clave: string]: string | string[] | undefined }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");

  const params = await searchParams;
  const filtros = filtrosDesde({
    get: (clave) => {
      const valor = params[clave];
      return typeof valor === "string" ? valor : null;
    },
  });
  const pagina = await getOrdenesPagina(cookieStore, filtros);

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

      <ListaOrdenes inicial={pagina} consultaInicial={consultaDeOrdenes(filtros)} />
    </main>
  );
}
