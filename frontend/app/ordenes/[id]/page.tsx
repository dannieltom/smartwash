import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import {
  getCurrentUser,
  getHistorialOrden,
  getMateriales,
  getNovedadesOrden,
  getOperarios,
  getOrden,
  getPagosOrden,
  getServicios,
  getTarifas,
  getTiposPrenda,
  type EstadoOrden,
} from "@/lib/api";
import { formatCOP, formatFecha } from "@/lib/format";
import { ClayBadge, ClayCard, Encabezado } from "../../components/ui/clay";
import EstadoAbono from "../abono";
import { tarifasDeHoy } from "../cotizacion";
import { COLOR_ESTADO } from "../tabla-ordenes";
import { agruparPrendas, detallesDe } from "../agrupar";
import AgregarPrenda from "./agregar-prenda";
import AgregarServicio from "./agregar-servicio";
import AsignarOperario from "./asignar-operario";
import AvisoCliente from "./aviso-cliente";
import CambiarEstado from "./cambiar-estado";
import NovedadesOrden from "./novedades-orden";
import PagosOrden from "./pagos-orden";
import RegistrarEntrega from "./registrar-entrega";
import RegistrarNovedad from "./registrar-novedad";

const ESTADOS_QUE_ADMITEN_LINEAS: EstadoOrden[] = ["En espera", "Recibida", "Clasificada"];

function Dato({ etiqueta, children }: { etiqueta: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-semibold tracking-wide text-(--sw-ink-soft) uppercase">{etiqueta}</dt>
      <dd className="mt-1 text-sm font-semibold text-(--sw-ink) tabular-nums">{children}</dd>
    </div>
  );
}

export default async function OrdenPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ registrada?: string }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");

  const id = Number((await params).id);
  const { registrada } = await searchParams;
  const puedeEditar = user.rol !== "operario";

  const [orden, tiposPrenda, materiales, servicios, tarifas, pagos, operarios, novedades, historial] = await Promise.all([
    getOrden(id, cookieStore),
    puedeEditar ? getTiposPrenda(cookieStore) : null,
    puedeEditar ? getMateriales(cookieStore) : null,
    puedeEditar ? getServicios(cookieStore) : null,
    puedeEditar ? getTarifas(cookieStore, true) : null,
    puedeEditar ? getPagosOrden(id, cookieStore) : null,
    puedeEditar ? getOperarios(cookieStore) : null,
    getNovedadesOrden(id, cookieStore),
    puedeEditar ? getHistorialOrden(id, cookieStore) : null,
  ]);

  if (orden === null) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-8 sm:py-12">
        <Link href="/ordenes" className="text-sm text-(--sw-ink-soft) hover:underline">
          ← Ordenes
        </Link>
        <ClayCard className="mt-6">
          <p className="text-sm text-(--sw-ink-soft)">
            No se encontro la orden o no se pudo cargar. Verifica que el backend este en ejecucion.
          </p>
        </ClayCard>
      </main>
    );
  }

  const tarifasVigentes = tarifas ? tarifasDeHoy(tarifas) : [];
  const admiteLineas = puedeEditar && ESTADOS_QUE_ADMITEN_LINEAS.includes(orden.estado);
  const conCatalogo = admiteLineas && tiposPrenda !== null && materiales !== null && servicios !== null;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-8 sm:py-12">
      <Link href="/ordenes" className="text-sm text-(--sw-ink-soft) hover:underline">
        ← Ordenes
      </Link>
      <Encabezado
        eyebrow="Orden"
        titulo={orden.codigo}
        acciones={
          <div className="flex flex-wrap items-center gap-2">
            <ClayBadge color={COLOR_ESTADO[orden.estado]}>{orden.estado}</ClayBadge>
            <ClayBadge color={orden.estado_pago === "Pagada" ? "mint" : "peach"}>
              Pago {orden.estado_pago.toLowerCase()}
            </ClayBadge>
            {puedeEditar && (
              <Link href={`/ordenes/${orden.id}/historial`} className="text-xs font-bold text-(--sw-ink-soft) hover:underline">
                Ver historial
              </Link>
            )}
          </div>
        }
      >
        {orden.cliente_nombre}
      </Encabezado>

      {registrada && (
        <div role="status" className="clay-sm mb-6 border-l-8 border-l-(--sw-mint) p-4 text-sm">
          <p className="font-semibold text-(--sw-ink)">Orden registrada</p>
          <p className="mt-1 text-(--sw-ink-soft)">
            Queda &quot;{orden.estado}&quot;. Pasa a &quot;Recibida&quot; cuando se registre el abono
            de {formatCOP(orden.abono_requerido)}.
          </p>
        </div>
      )}

      {historial && <AvisoCliente orden={orden} historial={historial} />}
      {puedeEditar && orden.estado === "Lista para entrega" && <RegistrarEntrega orden={orden} />}
      <CambiarEstado orden={orden} usuario={user} />
      <RegistrarNovedad orden={orden} usuario={user} />
      {novedades && <NovedadesOrden novedades={novedades} />}
      {puedeEditar && <AsignarOperario orden={orden} operarios={operarios} usuario={user} />}

      <ClayCard className="mb-6">
        <dl className="grid grid-cols-2 gap-5 sm:grid-cols-4">
          <Dato etiqueta="Subtotal">{formatCOP(orden.subtotal)}</Dato>
          <Dato etiqueta="Descuento fidelizacion">
            {Number(orden.descuento) > 0 ? `− ${formatCOP(orden.descuento)}` : formatCOP(0)}
          </Dato>
          <Dato etiqueta="Valor total">{formatCOP(orden.valor_total)}</Dato>
          <Dato etiqueta="Abono requerido (30 %)">
            <span className="block">{formatCOP(orden.abono_requerido)}</span>
            <span className="mt-1 inline-block">
              <EstadoAbono orden={orden} />
            </span>
          </Dato>
          <Dato etiqueta="Pagado">{formatCOP(orden.total_pagado)}</Dato>
          <Dato etiqueta="Saldo pendiente">{formatCOP(orden.saldo_pendiente)}</Dato>
          <Dato etiqueta="Duracion estimada">
            {orden.duracion_estimada_dias} {orden.duracion_estimada_dias === 1 ? "dia habil" : "dias habiles"}
          </Dato>
          <Dato etiqueta="Fecha estimada de entrega">
            {orden.fecha_estimada_entrega ? (
              formatFecha(orden.fecha_estimada_entrega)
            ) : (
              <span className="font-normal text-(--sw-ink-soft)">Se calcula al registrar el abono</span>
            )}
          </Dato>
        </dl>
        {orden.tiene_abono && admiteLineas && (
          <p className="mt-4 text-xs text-(--sw-ink-soft)">
            La orden ya alcanzo el abono minimo: si agregas prendas o servicios no se pide otro abono, la
            diferencia se paga al entregar.
          </p>
        )}
      </ClayCard>

      {puedeEditar && <PagosOrden orden={orden} pagos={pagos} />}

      <h2 className="mb-3 text-lg font-bold text-(--sw-ink)">Prendas</h2>
      <div className="flex flex-col gap-3">
        {agruparPrendas(orden.detalle_prendas, (p) =>
          p.servicios.map((x) => `${x.servicio}:${Number(x.valor_aplicado)}`).sort().join(","),
        ).map((grupo) => {
          const [prenda] = grupo.prendas;
          const detalles = detallesDe(grupo);
          return (
            <ClayCard key={prenda.id} className="p-4">
              <p className="font-semibold text-(--sw-ink)">
                {grupo.cantidad} × {prenda.tipo_prenda_nombre}
              </p>
              {detalles.length > 0 && (
                <p className="mt-0.5 text-xs text-(--sw-ink-soft)">{detalles.join(" · ")}</p>
              )}
              {prenda.estado_inicial && (
                <p className="mt-0.5 text-xs text-(--sw-ink-soft)">Al recibir: {prenda.estado_inicial}</p>
              )}
              <ul className="mt-3 flex flex-col gap-1 text-sm">
                {prenda.servicios.map((s, i) => (
                  <li key={s.id} className="flex justify-between gap-4">
                    <span className="text-(--sw-ink)">
                      {s.servicio_nombre}{" "}
                      {puedeEditar && s.valor_base !== null && s.precio_por_kilo !== null && (
                        <span className="text-xs text-(--sw-ink-soft)">
                          ({formatCOP(s.valor_base)} + {Number(s.peso)} kg × {formatCOP(s.precio_por_kilo)}
                          {s.nivel_dificultad ? ` · ${s.nivel_dificultad} ×${Number(s.factor)}` : ""}
                          {s.es_excepcion ? " · tarifa del tipo" : ""})
                        </span>
                      )}
                    </span>
                    <span className="font-semibold text-(--sw-ink) tabular-nums">
                      {formatCOP(
                        grupo.prendas.reduce((suma, p) => suma + Number(p.servicios[i].valor_aplicado), 0),
                      )}
                    </span>
                  </li>
                ))}
              </ul>
              {conCatalogo && servicios && (
                <AgregarServicio
                  ordenId={orden.id}
                  prendas={grupo.prendas}
                  servicios={servicios}
                  tarifas={tarifasVigentes}
                />
              )}
            </ClayCard>
          );
        })}
      </div>

      {conCatalogo && tiposPrenda && materiales && servicios && (
        <div className="mt-4">
          <AgregarPrenda
            ordenId={orden.id}
            tiposPrenda={tiposPrenda}
            materiales={materiales}
            servicios={servicios}
            tarifas={tarifasVigentes}
          />
        </div>
      )}
      {puedeEditar && !ESTADOS_QUE_ADMITEN_LINEAS.includes(orden.estado) && (
        <p className="mt-4 text-sm text-(--sw-ink-soft)">
          La orden esta &quot;{orden.estado}&quot;: ya no admite prendas ni servicios. Lo adicional va en otra
          orden.
        </p>
      )}
    </main>
  );
}
