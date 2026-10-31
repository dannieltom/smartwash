"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AlertaErrores } from "@/app/catalogo/errores";
import { getClienteById, registrarEntrega, type Cliente, type Orden, type ResultadoVerificacion } from "@/lib/api";
import { formatCOP } from "@/lib/format";
import { ClayButton, ClayCard, ClayInput, ClayTextarea } from "../../components/ui/clay";
import CampoFoto from "../campo-foto";
import { valorDePrenda } from "../descuentos";
import { mensajesDeOrden } from "../errores";
import type { FotoLista } from "../foto";

// null mientras la recepcionista no ha revisado la prenda: no se asume que coincide.
type Revision = {
  resultado: ResultadoVerificacion | null;
  observacion: string;
  foto: FotoLista | null;
  valor: string;
};

const OPCIONES: { valor: ResultadoVerificacion; etiqueta: string }[] = [
  { valor: "coincide", etiqueta: "Coincide con lo solicitado" },
  { valor: "novedad", etiqueta: "Novedad (defecto menor)" },
  { valor: "dano", etiqueta: "Daño de la lavanderia" },
  { valor: "perdida", etiqueta: "Perdida" },
];

const PIDE_FOTO: ResultadoVerificacion[] = ["novedad", "dano"];
const PIDE_VALOR: ResultadoVerificacion[] = ["dano", "perdida"];

const vacia = (): Revision => ({ resultado: null, observacion: "", foto: null, valor: "" });

function estaCompleta(r: Revision) {
  if (r.resultado === null) return false;
  if (r.resultado === "coincide") return true;
  return (
    r.observacion.trim() !== "" &&
    (!PIDE_FOTO.includes(r.resultado) || r.foto !== null) &&
    (!PIDE_VALOR.includes(r.resultado) || Number(r.valor) > 0)
  );
}

export default function RegistrarEntrega({
  orden,
  clasificacionActual,
}: {
  orden: Orden;
  clasificacionActual: Cliente["clasificacion"] | null;
}) {
  const router = useRouter();
  // Las danadas o perdidas en una entrega anterior ya quedaron resueltas.
  const prendas = orden.detalle_prendas.filter((p) => p.dano === null);
  const revisionesVacias = () => Object.fromEntries(prendas.map((p) => [p.id, vacia()]));
  const [abierto, setAbierto] = useState(false);
  const [revisiones, setRevisiones] = useState<Record<number, Revision>>(revisionesVacias);
  const [errores, setErrores] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  const completa = prendas.every((p) => estaCompleta(revisiones[p.id]));
  const hayNovedades = prendas.some((p) => revisiones[p.id].resultado === "novedad");
  const sinCobrar = prendas
    .filter((p) => PIDE_VALOR.includes(revisiones[p.id].resultado ?? "coincide"))
    .reduce((suma, p) => suma + valorDePrenda(p), 0);

  function revisar(prenda: number, cambios: Partial<Revision>) {
    setRevisiones((actual) => ({ ...actual, [prenda]: { ...actual[prenda], ...cambios } }));
  }

  function marcarTodas() {
    setRevisiones(Object.fromEntries(prendas.map((p) => [p.id, { ...vacia(), resultado: "coincide" }])));
  }

  function cancelar() {
    setAbierto(false);
    setRevisiones(revisionesVacias());
    setErrores([]);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setErrores([]);
    const verificaciones = prendas.map((p) => {
      const r = revisiones[p.id];
      const resultado = r.resultado ?? "coincide";
      return {
        prenda: p.id,
        resultado,
        observacion: resultado === "coincide" ? "" : r.observacion.trim(),
        foto: PIDE_FOTO.includes(resultado) ? (r.foto?.dataUrl ?? null) : null,
        valor_declarado: PIDE_VALOR.includes(resultado) ? r.valor : null,
      };
    });
    const response = await registrarEntrega(orden.id, verificaciones).catch(() => null);
    setPending(false);

    if (response?.ok) {
      setAbierto(false);
      // Un 503 no llega aqui: sin entrega confirmada no se vuelve a pedir el cliente.
      const cliente = await getClienteById(orden.cliente);
      if (cliente && cliente.clasificacion !== clasificacionActual) {
        router.replace(`/ordenes/${orden.id}?clasificacion=${encodeURIComponent(cliente.clasificacion)}`);
      }
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
        {prendas.map((prenda, indice) => {
          const revision = revisiones[prenda.id];
          const resultado = revision.resultado;
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
              <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-(--sw-ink)">
                {OPCIONES.map((opcion, i) => (
                  <label key={opcion.valor} className="flex items-center gap-2">
                    <input
                      type="radio"
                      name={nombre}
                      checked={resultado === opcion.valor}
                      onChange={() =>
                        revisar(prenda.id, opcion.valor === "coincide" ? vacia() : { resultado: opcion.valor })
                      }
                      required={i === 0}
                    />
                    {opcion.etiqueta}
                  </label>
                ))}
              </div>
              {resultado !== null && resultado !== "coincide" && (
                <ClayTextarea
                  aria-label={`Observacion de la prenda ${indice + 1}`}
                  placeholder={
                    resultado === "perdida"
                      ? "Describe que paso con la prenda (obligatorio)"
                      : "Describe lo que encontraste (obligatorio)"
                  }
                  value={revision.observacion}
                  onChange={(e) => revisar(prenda.id, { observacion: e.target.value })}
                  className="min-h-20"
                  required
                />
              )}
              {resultado !== null && PIDE_FOTO.includes(resultado) && (
                <CampoFoto
                  etiqueta={resultado === "dano" ? "Foto del daño" : "Foto de la novedad"}
                  foto={revision.foto}
                  onChange={(foto) => revisar(prenda.id, { foto })}
                  obligatoria
                />
              )}
              {resultado !== null && PIDE_VALOR.includes(resultado) && (
                <label className="flex flex-col gap-1 text-sm">
                  <span className="font-medium text-(--sw-ink-soft)">
                    Valor de la prenda que declara el cliente (obligatorio)
                  </span>
                  <ClayInput
                    type="number"
                    min="1"
                    step="100"
                    inputMode="numeric"
                    value={revision.valor}
                    onChange={(e) => revisar(prenda.id, { valor: e.target.value })}
                    required
                  />
                  <span className="text-xs text-(--sw-ink-soft)">
                    La lavanderia le debe este valor al cliente. Ademas, no se cobra el servicio de esta
                    prenda ({formatCOP(valorDePrenda(prenda))}).
                  </span>
                </label>
              )}
            </fieldset>
          );
        })}

        {sinCobrar > 0 && (
          <p className="text-sm text-(--sw-ink-soft)">
            Por daños o perdidas no se cobran {formatCOP(sinCobrar)}: el total baja a{" "}
            {formatCOP(Math.max(Number(orden.valor_total) - sinCobrar, 0))}. Si el cliente pago de mas, la
            diferencia se le devuelve y queda en el historial.
          </p>
        )}
        {hayNovedades && (
          <p className="text-sm text-(--sw-ink-soft)">
            Con alguna novedad la orden no se entrega: queda &quot;Con novedad&quot; y el cliente decide si se
            la lleva con descuento o si se reprocesa.
          </p>
        )}
        <AlertaErrores titulo="No se pudo registrar la entrega" errores={errores} />
        <div className="flex flex-wrap gap-3">
          <ClayButton type="submit" disabled={pending || !completa}>
            {pending ? "Registrando..." : hayNovedades ? "Registrar novedad" : "Confirmar entrega"}
          </ClayButton>
          <ClayButton type="button" variant="secundario" onClick={cancelar} disabled={pending}>
            Cancelar
          </ClayButton>
        </div>
      </form>
    </ClayCard>
  );
}
