"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AlertaErrores } from "@/app/catalogo/errores";
import { registrarEntrega, type Orden } from "@/lib/api";
import { formatCOP } from "@/lib/format";
import { ClayButton, ClayCard, ClayTextarea } from "../../components/ui/clay";
import CampoFoto from "../campo-foto";
import { mensajesDeOrden } from "../errores";
import type { FotoLista } from "../foto";

// null mientras la recepcionista no ha revisado la prenda: no se asume que coincide.
type Revision = { coincide: boolean | null; observacion: string; foto: FotoLista | null };

// El backend limita el cuerpo de la peticion a 2,5 MB: mas de 3 fotos de 500 KB
// en base64 lo superarian.
const MAXIMO_FOTOS = 3;

function revisionesVacias(orden: Orden): Record<number, Revision> {
  return Object.fromEntries(orden.detalle_prendas.map((p) => [p.id, { coincide: null, observacion: "", foto: null }]));
}

export default function RegistrarEntrega({ orden }: { orden: Orden }) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(false);
  const [revisiones, setRevisiones] = useState(() => revisionesVacias(orden));
  const [errores, setErrores] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  const completa = orden.detalle_prendas.every((p) => {
    const r = revisiones[p.id];
    return r.coincide === true || (r.coincide === false && r.observacion.trim() !== "");
  });

  const fotos = Object.values(revisiones).filter((r) => r.coincide === false && r.foto).length;
  const hayDiscrepancias = Object.values(revisiones).some((r) => r.coincide === false);

  function revisar(prenda: number, cambios: Partial<Revision>) {
    setRevisiones((actual) => ({ ...actual, [prenda]: { ...actual[prenda], ...cambios } }));
  }

  function marcarTodas() {
    setRevisiones(Object.fromEntries(orden.detalle_prendas.map((p) => [p.id, { coincide: true, observacion: "", foto: null }])));
  }

  function cancelar() {
    setAbierto(false);
    setRevisiones(revisionesVacias(orden));
    setErrores([]);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setErrores([]);
    const prendas = orden.detalle_prendas.map((p) => ({
      prenda: p.id,
      coincide: revisiones[p.id].coincide === true,
      observacion: revisiones[p.id].observacion.trim(),
      foto: revisiones[p.id].coincide === false ? (revisiones[p.id].foto?.dataUrl ?? null) : null,
    }));
    const response = await registrarEntrega(orden.id, prendas).catch(() => null);
    setPending(false);

    if (response?.ok) {
      setAbierto(false);
      router.refresh();
      return;
    }
    setErrores(await mensajesDeOrden(response, "No se pudo registrar la entrega"));
  }

  if (!abierto) {
    return (
      <ClayCard className="mb-6">
        <h2 className="text-sm font-bold text-(--sw-ink)">Entrega</h2>
        {orden.pago_completo ? (
          <p className="mt-1 text-sm text-(--sw-ink-soft)">
            La orden esta lista. Verifica cada prenda contra lo solicitado antes de entregarla.
          </p>
        ) : (
          <div role="status" className="clay-sm mt-3 border-l-8 border-l-(--sw-coral) p-4 text-sm">
            <p className="font-semibold text-(--sw-ink)">
              No se puede entregar: saldo pendiente de {formatCOP(orden.saldo_pendiente)}
            </p>
            <p className="mt-1 text-(--sw-ink-soft)">
              El pago debe estar completo antes de entregar, incluidas las prendas o servicios agregados
              despues del abono. Pagado {formatCOP(orden.total_pagado)} de {formatCOP(orden.valor_total)}.
            </p>
          </div>
        )}
        {/* El backend aplica la misma regla: esto solo evita un intento que va a fallar. */}
        <ClayButton
          type="button"
          className="mt-3"
          onClick={() => setAbierto(true)}
          disabled={!orden.pago_completo}
        >
          Registrar entrega
        </ClayButton>
      </ClayCard>
    );
  }

  return (
    <ClayCard className="mb-6">
      <h2 className="text-sm font-bold text-(--sw-ink)">Registrar entrega</h2>
      <form onSubmit={onSubmit} className="mt-3 flex flex-col gap-4">
        <div>
          <ClayButton type="button" variant="secundario" onClick={marcarTodas}>
            Marcar todas como coincide
          </ClayButton>
        </div>
        {orden.detalle_prendas.map((prenda, indice) => {
          const revision = revisiones[prenda.id];
          const nombre = `prenda-${prenda.id}`;
          return (
            <fieldset key={prenda.id} className="clay-sm flex flex-col gap-2 p-4">
              <legend className="sr-only">Prenda {indice + 1}</legend>
              <p className="text-sm font-semibold text-(--sw-ink)">
                Prenda {indice + 1}: {prenda.cantidad} × {prenda.tipo_prenda_nombre}
                {prenda.material_nombre && ` · ${prenda.material_nombre}`}
                <span className="font-normal text-(--sw-ink-soft)">
                  {" "}
                  · {prenda.servicios.map((s) => s.servicio_nombre).join(", ")}
                </span>
              </p>
              {prenda.estado_inicial && (
                <p className="text-xs text-(--sw-ink-soft)">Al recibir: {prenda.estado_inicial}</p>
              )}
              <div className="flex flex-wrap gap-4 text-sm text-(--sw-ink)">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name={nombre}
                    checked={revision.coincide === true}
                    onChange={() => revisar(prenda.id, { coincide: true, observacion: "", foto: null })}
                    required
                  />
                  Coincide con lo solicitado
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name={nombre}
                    checked={revision.coincide === false}
                    onChange={() => revisar(prenda.id, { coincide: false })}
                  />
                  No coincide
                </label>
              </div>
              {revision.coincide === false && (
                <ClayTextarea
                  aria-label={`Observacion de la prenda ${indice + 1}`}
                  placeholder="Describe la discrepancia (obligatorio)"
                  value={revision.observacion}
                  onChange={(e) => revisar(prenda.id, { observacion: e.target.value })}
                  className="min-h-20"
                  required
                />
              )}
              {revision.coincide === false && (
                <CampoFoto
                  etiqueta="Foto de la discrepancia"
                  foto={revision.foto}
                  onChange={(foto) => revisar(prenda.id, { foto })}
                />
              )}
            </fieldset>
          );
        })}

        {hayDiscrepancias && (
          <p className="text-sm text-(--sw-ink-soft)">
            Con alguna prenda que no coincide, la orden no se entrega: queda &quot;Con novedad&quot; hasta
            que el cliente decida.
          </p>
        )}
        {fotos > MAXIMO_FOTOS && (
          <p role="alert" className="text-sm font-semibold text-(--sw-ink)">
            Adjunta como maximo {MAXIMO_FOTOS} fotos por entrega ({fotos} seleccionadas).
          </p>
        )}
        <AlertaErrores titulo="No se pudo registrar la entrega" errores={errores} />
        <div className="flex flex-wrap gap-3">
          <ClayButton type="submit" disabled={pending || !completa || fotos > MAXIMO_FOTOS}>
            {pending ? "Registrando..." : hayDiscrepancias ? "Registrar novedad" : "Confirmar entrega"}
          </ClayButton>
          <ClayButton type="button" variant="secundario" onClick={cancelar} disabled={pending}>
            Cancelar
          </ClayButton>
        </div>
      </form>
    </ClayCard>
  );
}
