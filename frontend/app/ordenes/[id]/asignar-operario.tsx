"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { AlertaErrores } from "@/app/catalogo/errores";
import {
  asignarOperario,
  getOrdenesDeOperario,
  type EstadoOrden,
  type Operario,
  type Orden,
  type OrdenDeOperario,
  type User,
} from "@/lib/api";
import { FECHA_LEGIBLE } from "@/lib/auditoria";
import { formatCOP } from "@/lib/format";
import { ClayBadge, ClayButton, ClayCard } from "../../components/ui/clay";
import { mensajesDeOrden } from "../errores";

// Las mismas reglas que asignar_operario() en el backend, que es quien decide.
const REASIGNABLES: EstadoOrden[] = ["Recibida", "Clasificada"];
const TRABAJO_EN_CURSO: EstadoOrden[] = ["En proceso", "Control de calidad"];

function carga(o: Operario) {
  return `${o.ordenes_activas} ${o.ordenes_activas === 1 ? "orden" : "órdenes"} · ${o.prendas_activas} ${
    o.prendas_activas === 1 ? "prenda" : "prendas"
  }`;
}

// En turno primero y de menor a mayor carga; los de fuera de turno al final.
function porCarga(a: Operario, b: Operario) {
  return (
    Number(b.en_turno) - Number(a.en_turno) ||
    a.prendas_activas - b.prendas_activas ||
    a.ordenes_activas - b.ordenes_activas ||
    a.nombre.localeCompare(b.nombre)
  );
}

type OrdenesCargadas = OrdenDeOperario[] | "cargando" | "error";

function OrdenesDelOperario({ ordenes }: { ordenes: OrdenesCargadas }) {
  if (ordenes === "cargando") return <p className="text-xs text-(--sw-ink-soft)">Cargando ordenes...</p>;
  if (ordenes === "error") return <p className="text-xs text-(--sw-ink)">No se pudieron cargar sus ordenes.</p>;
  if (ordenes.length === 0) return <p className="text-xs text-(--sw-ink-soft)">No tiene ordenes en curso.</p>;
  return (
    <ul className="flex flex-col gap-2">
      {ordenes.map((o) => (
        <li key={o.id} className="border-t border-(--sw-hairline) pt-2 text-xs first:border-t-0 first:pt-0">
          <p>
            <Link href={`/ordenes/${o.id}`} className="font-bold text-(--sw-ink) underline">
              {o.codigo}
            </Link>{" "}
            <span className="text-(--sw-ink-soft)">
              · {o.cliente_nombre} · {o.estado}
              {o.fecha_asignacion && ` · asignada ${FECHA_LEGIBLE.format(new Date(o.fecha_asignacion))}`}
            </span>
          </p>
          <p className="mt-0.5 text-(--sw-ink)">
            {o.prendas
              .map((p) => `${p.cantidad} × ${p.tipo_prenda}${p.servicios.length ? ` (${p.servicios.join(", ")})` : ""}`)
              .join(" · ")}
          </p>
        </li>
      ))}
    </ul>
  );
}

export default function AsignarOperario({
  orden,
  operarios,
  usuario,
}: {
  orden: Orden;
  operarios: Operario[] | null;
  usuario: User;
}) {
  const router = useRouter();
  const [editando, setEditando] = useState(false);
  const [elegido, setElegido] = useState<number | null>(null);
  const [verOrdenes, setVerOrdenes] = useState(false);
  const [ordenes, setOrdenes] = useState<Record<number, OrdenesCargadas>>({});
  const [errores, setErrores] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  // /operarios solo trae activos: si el asignado no aparece, fue desactivado.
  const actual = orden.operario === null ? null : operarios?.find((o) => o.id === orden.operario);
  const actualInactivo = orden.operario !== null && operarios !== null && !actual;
  const nombreActual =
    orden.operario === null
      ? "Sin asignar"
      : (actual?.nombre ?? `Operario #${orden.operario}${actualInactivo ? " (inactivo)" : ""}`);

  const excepcionAdmin =
    usuario.rol === "administrador" &&
    TRABAJO_EN_CURSO.includes(orden.estado) &&
    (orden.operario === null || actualInactivo);
  const puedeAsignar = REASIGNABLES.includes(orden.estado) || excepcionAdmin;
  const candidatos = (operarios ?? []).filter((o) => o.id !== orden.operario).sort(porCarga);

  function cancelar() {
    setEditando(false);
    setElegido(null);
    setVerOrdenes(false);
    setErrores([]);
  }

  function elegir(id: number) {
    setElegido(elegido === id ? null : id);
    setVerOrdenes(false);
    setErrores([]);
  }

  async function alternarOrdenes(id: number) {
    const abrir = !verOrdenes;
    setVerOrdenes(abrir);
    if (!abrir || Array.isArray(ordenes[id])) return;
    setOrdenes((actual) => ({ ...actual, [id]: "cargando" }));
    const cargadas = await getOrdenesDeOperario(id);
    setOrdenes((actual) => ({ ...actual, [id]: cargadas ?? "error" }));
  }

  async function asignar(id: number) {
    setPending(true);
    setErrores([]);
    const response = await asignarOperario(orden.id, id).catch(() => null);
    setPending(false);

    if (response?.ok) {
      cancelar();
      router.refresh();
      return;
    }
    setErrores(await mensajesDeOrden(response, "No se pudo asignar el operario"));
  }

  let aviso: string | null = null;
  if (orden.estado === "En espera") {
    const falta = Math.max(Number(orden.abono_requerido) - Number(orden.total_pagado), 0);
    aviso = `Para asignarla se requiere el abono minimo de ${formatCOP(orden.abono_requerido)} (faltan ${formatCOP(falta)}).`;
  } else if (TRABAJO_EN_CURSO.includes(orden.estado) && !excepcionAdmin) {
    aviso = `La orden esta "${orden.estado}" y queda fija con su operario. Solo el administrador puede reasignarla si el operario fue desactivado.`;
  } else if (puedeAsignar && operarios === null) {
    aviso = "No se pudo cargar la lista de operarios. Verifica que el backend este en ejecucion.";
  } else if (puedeAsignar && candidatos.length === 0) {
    aviso = "No hay otros operarios activos a quienes asignar la orden.";
  } else if (puedeAsignar && !candidatos.some((o) => o.en_turno)) {
    aviso = "Ningún operario está en turno.";
  }
  const ofrecerAsignar = puedeAsignar && aviso === null;

  return (
    <ClayCard className="mb-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-bold text-(--sw-ink)">Operario</h2>
          <p className="mt-1 text-sm text-(--sw-ink-soft)">{nombreActual}</p>
        </div>
        {ofrecerAsignar && !editando && (
          <ClayButton type="button" variant="secundario" onClick={() => setEditando(true)}>
            {orden.operario === null ? "Asignar operario" : "Reasignar"}
          </ClayButton>
        )}
      </div>

      {aviso && <p className="mt-3 text-sm text-(--sw-ink-soft)">{aviso}</p>}

      {editando && (
        <div className="mt-4 flex flex-col gap-3">
          <ul aria-label="Operarios" className="flex flex-col gap-2">
            {candidatos.map((o) => {
              const abierto = elegido === o.id;
              return (
                <li key={o.id} className={`clay-sm p-3 ${o.en_turno ? "" : "opacity-60"}`}>
                  <button
                    type="button"
                    onClick={() => elegir(o.id)}
                    disabled={!o.en_turno || pending}
                    aria-expanded={o.en_turno ? abierto : undefined}
                    className="flex w-full flex-wrap items-center justify-between gap-2 text-left disabled:cursor-not-allowed"
                  >
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-bold text-(--sw-ink)">{o.nombre}</span>
                      {o.recomendado && <ClayBadge color="mint">Recomendado</ClayBadge>}
                      {!o.en_turno && <ClayBadge color="lavender">Fuera de turno</ClayBadge>}
                    </span>
                    <span className="text-sm text-(--sw-ink-soft)">{carga(o)}</span>
                  </button>
                  {abierto && (
                    <div className="mt-3 flex flex-col gap-3 border-t border-(--sw-hairline) pt-3">
                      <p className="text-sm text-(--sw-ink)">{carga(o)} en total</p>
                      <div>
                        <button
                          type="button"
                          onClick={() => alternarOrdenes(o.id)}
                          aria-expanded={verOrdenes}
                          className="text-sm font-bold text-(--sw-accent-text) underline"
                        >
                          {verOrdenes ? "Ocultar órdenes" : "Ver órdenes"}
                        </button>
                        {verOrdenes && (
                          <div className="mt-2">
                            <OrdenesDelOperario ordenes={ordenes[o.id] ?? "cargando"} />
                          </div>
                        )}
                      </div>
                      <div>
                        <ClayButton type="button" onClick={() => asignar(o.id)} disabled={pending}>
                          {pending ? "Asignando..." : `Asignar a ${o.nombre}`}
                        </ClayButton>
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
          <AlertaErrores titulo="No se pudo asignar el operario" errores={errores} />
          <div>
            <ClayButton type="button" variant="secundario" onClick={cancelar} disabled={pending}>
              Cancelar
            </ClayButton>
          </div>
        </div>
      )}
    </ClayCard>
  );
}
