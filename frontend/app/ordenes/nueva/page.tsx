import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import {
  getCurrentUser,
  getMateriales,
  getPagina,
  getServicios,
  getTarifas,
  getTiposPrenda,
  type Cliente,
} from "@/lib/api";
import { ClayCard, Encabezado } from "../../components/ui/clay";
import { tarifasDeHoy } from "../cotizacion";
import OrdenForm from "./orden-form";

export default async function NuevaOrdenPage() {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol === "operario") redirect("/ordenes");

  const [clientes, tiposPrenda, materiales, servicios, tarifas] = await Promise.all([
    // Solo para saber si ya hay clientes: el selector los busca mientras se escribe.
    getPagina<Cliente>(cookieStore, "/clientes", "pagina=1&tamano=1"),
    getTiposPrenda(cookieStore),
    getMateriales(cookieStore),
    getServicios(cookieStore),
    getTarifas(cookieStore, true),
  ]);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-8 sm:py-12">
      <Link href="/ordenes" className="text-sm text-(--sw-ink-soft) hover:underline">
        ← Ordenes
      </Link>
      <Encabezado eyebrow="Operacion · EP04" titulo="Nueva orden">
        Registra las prendas que entrega el cliente y los servicios que pide.
      </Encabezado>

      {clientes === null || tiposPrenda === null || materiales === null || servicios === null || tarifas === null ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">
            No se pudieron cargar los clientes o el catalogo. Verifica que el backend este en ejecucion.
          </p>
        </ClayCard>
      ) : clientes.total === 0 ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">
            Todavia no hay clientes.{" "}
            <Link href="/clientes" className="font-semibold underline">
              Registra el primero
            </Link>{" "}
            para poder crear una orden.
          </p>
        </ClayCard>
      ) : (
        <OrdenForm
          tiposPrenda={tiposPrenda}
          materiales={materiales}
          servicios={servicios}
          tarifas={tarifasDeHoy(tarifas)}
        />
      )}
    </main>
  );
}
