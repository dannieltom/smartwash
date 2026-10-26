"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AlertaErrores } from "@/app/catalogo/errores";
import {
  registrarDecision,
  type ConfiguracionDescuentos,
  type Gravedad,
  type Novedad,
  type Operario,
  type Orden,
} from "@/lib/api";
import { formatCOP } from "@/lib/format";
import { ClayButton, ClayCard, ClayField, ClaySelect, ClayTextarea } from "../../components/ui/clay";
import { GRAVEDADES, montoDescuento, porcentajePara, valorDePrenda } from "../descuentos";
import { mensajesDeOrden } from "../errores";

type Opcion = "entregar_con_descuento" | "reprocesar_con_descuento";

export default function DecisionEntrega({
  orden,
  novedades,
  operarios,
  configuracion,
}: {
  orden: Orden;
  novedades: Novedad[];
  operarios: Operario[] | null;
  configuracion: ConfiguracionDescuentos;
}) {
  const router = useRouter();
  const pendientes = novedades.filter((n) => n.origen === "entrega" && n.decision === null);
  const operarioActivo = operarios?.some((o) => o.id === orden.operario) ? orden.operario : null;
  const [opcion, setOpcion] = useState<Opcion | null>(null);
  const [gravedades, setGravedades] = useState<Record<number, Gravedad>>({});
  const [operario, setOperario] = useState<number | null>(operarioActivo);
  const [observacion, setObservacion] = useState("");
  const [errores, setErrores] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  if (pendientes.length === 0) return null;

  const descuentos = pendientes.map((n) => {
    const prenda = orden.detalle_prendas.find((p) => p.id === n.prenda);
    const valor = prenda ? valorDePrenda(prenda) : 0;
    const yaDescontado = novedades
      .filter((otra) => otra.prenda === n.prenda && otra.id !== n.id)
      .reduce((suma, otra) => suma + Number(otra.monto_descuento), 0);
    const gravedad = gravedades[n.id];
    const porcentaje =
      opcion === "reprocesar_con_descuento"
        ? Number(configuracion.porcentaje_reproceso)
        : gravedad
          ? porcentajePara(gravedad, configuracion)
          : null;
    return {
      novedad: n,
      porcentaje,
      monto: porcentaje === null ? 0 : montoDescuento(valor, porcentaje, yaDescontado, configuracion),
    };
  });
  const totalDescuento = descuentos.reduce((suma, d) => suma + d.monto, 0);
  const nuevoTotal = Math.max(Number(orden.valor_total) - totalDescuento, 0);
  const pagado = Number(orden.total_pagado);
  const faltaGravedad = opcion === "entregar_con_descuento" && pendientes.some((n) => !gravedades[n.id]);
  const listo =
    opcion !== null &&
    observacion.trim() !== "" &&
    !faltaGravedad &&
    (opcion === "entregar_con_descuento" || operario !== null);

  function cancelar() {
    setOpcion(null);
    setGravedades({});
    setOperario(operarioActivo);
    setObservacion("");
    setErrores([]);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!opcion) return;
    setPending(true);
    setErrores([]);
    const response = await registrarDecision(orden.id, {
      decision: opcion,
      observacion: observacion.trim(),
      ...(opcion === "entregar_con_descuento"
        ? { gravedades: pendientes.map((n) => ({ novedad: n.id, gravedad: gravedades[n.id] })) }
        : { operario }),
    }).catch(() => null);
    setPending(false);

    if (response?.ok) {
      cancelar();
      router.refresh();
      return;
    }
    setErrores(await mensajesDeOrden(response, "No se pudo registrar la decision"));
  }

  return (
    <ClayCard className="mb-6">
      <h2 className="text-sm font-bold text-(--sw-ink)">Decision del cliente</h2>
      <p className="mt-1 text-sm text-(--sw-ink-soft)">
        Hay {pendientes.length === 1 ? "una prenda" : `${pendientes.length} prendas`} con novedad en la entrega.
        El cliente decide si se la lleva con descuento o si se reprocesa; la decision aplica a toda la orden.
      </p>
      <form onSubmit={onSubmit} className="mt-3 flex flex-col gap-4">
        <div className="flex flex-wrap gap-4 text-sm text-(--sw-ink)">
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="decision"
              checked={opcion === "entregar_con_descuento"}
              onChange={() => setOpcion("entregar_con_descuento")}
              required
            />
            Entregar con descuento
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="decision"
              checked={opcion === "reprocesar_con_descuento"}
              onChange={() => setOpcion("reprocesar_con_descuento")}
            />
            Reprocesar con descuento ({Number(configuracion.porcentaje_reproceso)} % por prenda)
          </label>
        </div>

        {opcion && (
          <ul className="flex flex-col gap-3">
            {descuentos.map(({ novedad, porcentaje, monto }) => (
              <li key={novedad.id} className="clay-sm flex flex-col gap-2 p-4 text-sm">
                <p className="font-semibold text-(--sw-ink)">{novedad.prenda_nombre}</p>
                <p className="text-(--sw-ink-soft)">{novedad.descripcion}</p>
                {opcion === "entregar_con_descuento" && (
                  <ClayField label="Gravedad">
                    <ClaySelect
                      value={gravedades[novedad.id] ?? ""}
                      onChange={(e) =>
                        setGravedades((actual) => ({ ...actual, [novedad.id]: e.target.value as Gravedad }))
                      }
                      required
                    >
                      <option value="" disabled>
                        Elige la gravedad
                      </option>
                      {GRAVEDADES.map((g) => (
                        <option key={g.valor} value={g.valor}>
                          {g.etiqueta} ({Number(porcentajePara(g.valor, configuracion))} %)
                        </option>
                      ))}
                    </ClaySelect>
                  </ClayField>
                )}
                {porcentaje !== null && (
                  <p className="text-(--sw-ink)">
                    Descuento: {porcentaje} % → <strong>− {formatCOP(monto)}</strong>
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}

        {opcion === "reprocesar_con_descuento" && (
          <ClayField label="Operario que la reprocesa">
            <ClaySelect
              value={operario ?? ""}
              onChange={(e) => setOperario(e.target.value ? Number(e.target.value) : null)}
              required
            >
              <option value="" disabled>
                Elige un operario activo
              </option>
              {(operarios ?? []).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.nombre}
                  {o.id === orden.operario ? " (el que la proceso)" : ""}
                </option>
              ))}
            </ClaySelect>
          </ClayField>
        )}
        {opcion === "reprocesar_con_descuento" && operarioActivo === null && (
          <p role="status" className="text-sm font-semibold text-(--sw-ink)">
            El operario que proceso la orden ya no esta activo: elige otro.
          </p>
        )}

        {opcion && !faltaGravedad && (
          <div className="clay-sm p-4 text-sm">
            <p className="text-(--sw-ink)">
              Nuevo total: <strong>{formatCOP(nuevoTotal)}</strong>{" "}
              <span className="text-(--sw-ink-soft)">(antes {formatCOP(orden.valor_total)})</span>
            </p>
            {pagado > nuevoTotal && (
              <p className="mt-1 text-(--sw-ink-soft)">
                {opcion === "entregar_con_descuento"
                  ? `Se le devuelven ${formatCOP(pagado - nuevoTotal)} al cliente al entregar.`
                  : `Queda un saldo a favor de ${formatCOP(pagado - nuevoTotal)}; se devuelve en la entrega final.`}
              </p>
            )}
            {opcion === "entregar_con_descuento" && pagado < nuevoTotal && (
              <p className="mt-1 font-semibold text-(--sw-ink)">
                Falta pagar {formatCOP(nuevoTotal - pagado)} antes de entregar.
              </p>
            )}
          </div>
        )}

        <ClayTextarea
          aria-label="Observacion de la decision"
          placeholder="Con quien se hablo y que decidio (obligatorio)"
          value={observacion}
          onChange={(e) => setObservacion(e.target.value)}
          className="min-h-20"
          required
        />
        <AlertaErrores titulo="No se pudo registrar la decision" errores={errores} />
        <div className="flex flex-wrap gap-3">
          <ClayButton type="submit" disabled={pending || !listo}>
            {pending
              ? "Registrando..."
              : opcion === "reprocesar_con_descuento"
                ? "Enviar a reproceso"
                : "Entregar con descuento"}
          </ClayButton>
          <ClayButton type="button" variant="secundario" onClick={cancelar} disabled={pending}>
            Cancelar
          </ClayButton>
        </div>
      </form>
    </ClayCard>
  );
}
