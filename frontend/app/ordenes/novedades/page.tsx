import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import {
  consultaDeLista,
  getCurrentUser,
  getOrden,
  getOrdenesConNovedad,
  getPagina,
  getServicios,
  getTarifas,
  type NovedadHistorial,
} from "@/lib/api";
import { lectorDe, paginaDesde } from "../../components/lista/url";
import { ClayCard, Encabezado, clayBtnClass } from "../../components/ui/clay";
import DecisionProceso from "../[id]/decision-proceso";
import { tarifasDeHoy } from "../cotizacion";
import NovedadesOrden from "../[id]/novedades-orden";
import { leerFiltrosHistorial } from "./filtros";
import HistorialNovedades from "./historial";
import PestanasNovedades, { type Vista } from "./pestanas";

function Marco({ vista, children }: { vista: Vista; children: ReactNode }) {
  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Incidencias · HU19" titulo="Ordenes con novedad">
        Ordenes detenidas hasta que el cliente decida. Contactalo por el medio que ya usa y registra aqui lo que
        decidio. El historial reune todas las novedades, resueltas o no.
      </Encabezado>
      <PestanasNovedades activa={vista} />
      <div role="tabpanel" id={`panel-${vista}`} aria-labelledby={`pestana-${vista}`}>
        {children}
      </div>
    </main>
  );
}

export default async function OrdenesConNovedadPage({
  searchParams,
}: {
  searchParams: Promise<{ [clave: string]: string | string[] | undefined }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol === "operario") redirect("/");

  const lector = lectorDe(await searchParams);
  if (lector.get("vista") === "historial") {
    const consulta = consultaDeLista(leerFiltrosHistorial(lector), paginaDesde(lector));
    const inicial = await getPagina<NovedadHistorial>(cookieStore, "/novedades", consulta);
    return (
      <Marco vista="historial">
        <HistorialNovedades inicial={inicial} consultaInicial={consulta} />
      </Marco>
    );
  }

  const [ordenes, servicios, tarifas] = await Promise.all([
    getOrdenesConNovedad(cookieStore),
    getServicios(cookieStore),
    getTarifas(cookieStore, true),
  ]);
  // Para agregar servicios hacen falta las prendas con sus servicios actuales.
  const detalles = await Promise.all((ordenes ?? []).map((o) => getOrden(o.id, cookieStore)));
  const tarifasVigentes = tarifas ? tarifasDeHoy(tarifas) : null;

  return (
    <Marco vista="pendientes">
      {ordenes === null ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">
            No se pudieron cargar las ordenes con novedad. Verifica que el backend este en ejecucion.
          </p>
        </ClayCard>
      ) : ordenes.length === 0 ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">No hay ordenes con novedad pendiente.</p>
        </ClayCard>
      ) : (
        ordenes.map((orden, i) => (
          <section key={orden.id} className="mb-8">
            <NovedadesOrden
              novedades={orden.novedades}
              encabezado={
                <div>
                  <h2 className="text-lg font-bold text-(--sw-ink)">
                    <Link href={`/ordenes/${orden.id}`} className="hover:underline">
                      {orden.codigo}
                    </Link>
                  </h2>
                  <p className="text-sm text-(--sw-ink-soft)">
                    {orden.cliente_nombre} · Operario: {orden.operario_nombre ?? "Sin asignar"}
                  </p>
                </div>
              }
            >
              {orden.novedades.some((n) => n.origen === "entrega") && (
                <div className="mt-4 border-t border-(--sw-hairline) pt-4">
                  <p className="text-sm text-(--sw-ink-soft)">
                    Detectada en la entrega: el cliente decide si se la lleva con descuento o si se reprocesa.
                  </p>
                  <Link href={`/ordenes/${orden.id}`} className={`${clayBtnClass()} mt-3`}>
                    Registrar la decision
                  </Link>
                </div>
              )}
            </NovedadesOrden>
            {detalles[i] && (
              <DecisionProceso
                orden={detalles[i]}
                novedades={orden.novedades}
                servicios={servicios}
                tarifas={tarifasVigentes}
              />
            )}
          </section>
        ))
      )}
    </Marco>
  );
}
