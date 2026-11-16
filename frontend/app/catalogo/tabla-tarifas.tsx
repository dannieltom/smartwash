"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { actualizarTarifa, type Tarifa } from "@/lib/api";
import { formatCOP, formatFecha } from "@/lib/format";
import { ClayBadge, ClayButton, ClayCard, ClayInput } from "../components/ui/clay";
import { AlertaErrores, mensajesDeError } from "./errores";
import { ETIQUETAS_TARIFA } from "./tarifa-form";

export default function TablaTarifas({
  tarifas,
  editable,
  conTipo,
}: {
  tarifas: Tarifa[];
  editable: boolean;
  conTipo: boolean;
}) {
  const router = useRouter();
  const [editando, setEditando] = useState<Tarifa | null>(null);
  const [valorBase, setValorBase] = useState("");
  const [precioKilo, setPrecioKilo] = useState("");
  const [plazo, setPlazo] = useState("");
  const [hasta, setHasta] = useState("");
  const [errores, setErrores] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  if (tarifas.length === 0) {
    return (
      <ClayCard>
        <p className="text-sm text-(--sw-ink-soft)">No hay tarifas para mostrar.</p>
      </ClayCard>
    );
  }

  function empezarEdicion(tarifa: Tarifa) {
    setEditando(tarifa);
    setValorBase(tarifa.valor_base);
    setPrecioKilo(tarifa.precio_por_kilo);
    setPlazo(String(tarifa.plazo_entrega_dias));
    setHasta(tarifa.vigente_hasta ?? "");
    setErrores([]);
  }

  function cancelar() {
    setEditando(null);
    setErrores([]);
  }

  async function guardar() {
    if (!editando) return;
    setPending(true);
    setErrores([]);
    const response = await actualizarTarifa(editando.id, {
      valor_base: valorBase,
      precio_por_kilo: precioKilo,
      plazo_entrega_dias: Number(plazo),
      vigente_hasta: hasta === "" ? null : hasta,
    }).catch(() => null);
    setPending(false);

    if (response?.ok) {
      setEditando(null);
      router.refresh();
      return;
    }
    setErrores(await mensajesDeError(response, ETIQUETAS_TARIFA, "No se pudo actualizar la tarifa"));
  }

  return (
    <ClayCard className="overflow-x-auto p-0">
      <table className="sw-tabla w-full text-left text-sm">
        <thead>
          <tr className="text-xs font-bold tracking-wide text-(--sw-ink-soft) uppercase">
            <th className="px-5 py-3">Servicio</th>
            {conTipo && <th className="px-5 py-3">Tipo de prenda</th>}
            <th className="px-5 py-3">Valor base por prenda</th>
            <th className="px-5 py-3">Precio por kilo</th>
            <th className="px-5 py-3">Plazo</th>
            <th className="px-5 py-3">Vigencia</th>
            {editable && (
              <th className="px-5 py-3">
                <span className="sr-only">Acciones</span>
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {tarifas.map((tarifa) => {
            const enEdicion = editando?.id === tarifa.id;
            return (
              <FilaTarifa
                key={tarifa.id}
                tarifa={tarifa}
                conTipo={conTipo}
                enEdicion={enEdicion}
                editable={editable}
                deshabilitado={editando !== null && !enEdicion}
                valorBase={valorBase}
                precioKilo={precioKilo}
                plazo={plazo}
                hasta={hasta}
                pending={pending}
                errores={enEdicion ? errores : []}
                onValorBase={setValorBase}
                onPrecioKilo={setPrecioKilo}
                onPlazo={setPlazo}
                onHasta={setHasta}
                onEditar={() => empezarEdicion(tarifa)}
                onGuardar={guardar}
                onCancelar={cancelar}
              />
            );
          })}
        </tbody>
      </table>
    </ClayCard>
  );
}

function FilaTarifa({
  tarifa,
  conTipo,
  enEdicion,
  editable,
  deshabilitado,
  valorBase,
  precioKilo,
  plazo,
  hasta,
  pending,
  errores,
  onValorBase,
  onPrecioKilo,
  onPlazo,
  onHasta,
  onEditar,
  onGuardar,
  onCancelar,
}: {
  tarifa: Tarifa;
  conTipo: boolean;
  enEdicion: boolean;
  editable: boolean;
  deshabilitado: boolean;
  valorBase: string;
  precioKilo: string;
  plazo: string;
  hasta: string;
  pending: boolean;
  errores: string[];
  onValorBase: (valor: string) => void;
  onPrecioKilo: (valor: string) => void;
  onPlazo: (plazo: string) => void;
  onHasta: (hasta: string) => void;
  onEditar: () => void;
  onGuardar: () => void;
  onCancelar: () => void;
}) {
  return (
    <>
      <tr className="border-t border-(--sw-hairline)">
        <td data-label="Servicio" className="px-5 py-3 font-semibold text-(--sw-ink)">{tarifa.servicio_nombre}</td>
        {conTipo && (
          <td data-label="Tipo de prenda" className="px-5 py-3 text-(--sw-ink-soft)">{tarifa.tipo_prenda_nombre ?? "General"}</td>
        )}
        {enEdicion ? (
          <>
            <td data-label="Valor base por prenda" className="px-5 py-3">
              <ClayInput
                aria-label="Valor base por prenda (COP)"
                type="number"
                min="0"
                step="0.01"
                value={valorBase}
                onChange={(event) => onValorBase(event.target.value)}
                className="min-w-24"
                required
              />
            </td>
            <td data-label="Precio por kilo" className="px-5 py-3">
              <ClayInput
                aria-label="Precio por kilo (COP)"
                type="number"
                min="0"
                step="0.01"
                value={precioKilo}
                onChange={(event) => onPrecioKilo(event.target.value)}
                className="min-w-24"
                required
              />
            </td>
            <td data-label="Plazo" className="px-5 py-3">
              <ClayInput
                aria-label="Plazo de entrega (dias)"
                type="number"
                min="1"
                value={plazo}
                onChange={(event) => onPlazo(event.target.value)}
                className="min-w-16"
                required
              />
            </td>
            <td data-label="Vigencia" className="px-5 py-3">
              <ClayInput
                aria-label="Vigente hasta"
                type="date"
                value={hasta}
                onChange={(event) => onHasta(event.target.value)}
                className="min-w-36"
              />
            </td>
            <td className="px-5 py-3">
              <div className="flex flex-wrap gap-2">
                <ClayButton type="button" onClick={onGuardar} disabled={pending}>
                  {pending ? "Guardando..." : "Guardar"}
                </ClayButton>
                <ClayButton type="button" variant="secundario" onClick={onCancelar} disabled={pending}>
                  Cancelar
                </ClayButton>
              </div>
            </td>
          </>
        ) : (
          <>
            <td data-label="Valor base por prenda" className="px-5 py-3 font-semibold text-(--sw-ink) tabular-nums">
              {formatCOP(tarifa.valor_base)}
            </td>
            <td data-label="Precio por kilo" className="px-5 py-3 font-semibold text-(--sw-ink) tabular-nums">
              {formatCOP(tarifa.precio_por_kilo)}
            </td>
            <td data-label="Plazo" className="px-5 py-3 text-(--sw-ink-soft)">{tarifa.plazo_entrega_dias} dias</td>
            <td data-label="Vigencia" className="px-5 py-3">
              <ClayBadge color={tarifa.vigente_hasta ? "peach" : "mint"}>
                {tarifa.vigente_hasta ? `Hasta ${formatFecha(tarifa.vigente_hasta)}` : "Vigente"}
              </ClayBadge>
            </td>
            {editable && (
              <td className="px-5 py-3">
                <ClayButton type="button" variant="secundario" onClick={onEditar} disabled={deshabilitado}>
                  Editar
                </ClayButton>
              </td>
            )}
          </>
        )}
      </tr>
      {errores.length > 0 && (
        <tr>
          <td colSpan={7} className="px-5 pb-3">
            <AlertaErrores titulo="No se pudo actualizar la tarifa" errores={errores} />
          </td>
        </tr>
      )}
    </>
  );
}
