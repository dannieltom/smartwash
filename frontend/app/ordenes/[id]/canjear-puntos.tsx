"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AlertaErrores } from "@/app/catalogo/errores";
import { canjearPuntos, type EstadoOrden, type Orden } from "@/lib/api";
import { formatCOP } from "@/lib/format";
import { ClayButton, ClayCard, ClayInput } from "../../components/ui/clay";
import { mensajesDeOrden } from "../errores";

// Mismo criterio que CanjearPuntosView en el backend, que es quien decide.
const ESTADOS_QUE_ADMITEN_CANJE: EstadoOrden[] = ["En espera", "Recibida", "Clasificada"];

function errorDePuntos(texto: string, saldo: number, maximo: number, pesosPorPunto: number) {
  if (texto === "") return null;
  if (!/^\d+$/.test(texto)) return "Ingresa un numero entero de puntos, sin decimales ni signos.";
  const puntos = Number(texto);
  if (puntos === 0) return "Canjea al menos un punto.";
  if (puntos > saldo) return `El cliente solo tiene ${saldo} puntos.`;
  if (puntos > maximo) {
    return `El descuento supera el total de la orden: canjea maximo ${maximo} puntos (${formatCOP(maximo * pesosPorPunto)}).`;
  }
  return null;
}

export default function CanjearPuntos({ orden, saldo }: { orden: Orden; saldo: number }) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const [errores, setErrores] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  if (!ESTADOS_QUE_ADMITEN_CANJE.includes(orden.estado)) return null;

  const pesosPorPunto = Number(orden.pesos_por_punto);
  const total = Number(orden.valor_total);
  const maximo = Math.min(saldo, Math.floor(total / pesosPorPunto));
  const error = errorDePuntos(texto, saldo, maximo, pesosPorPunto);
  const puntos = error === null && texto !== "" ? Number(texto) : 0;
  const descuento = puntos * pesosPorPunto;

  function descartar() {
    setAbierto(false);
    setTexto("");
    setErrores([]);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (puntos === 0 || pending) return;
    setPending(true);
    setErrores([]);
    const response = await canjearPuntos(orden.id, puntos).catch(() => null);
    setPending(false);

    if (response?.ok) {
      descartar();
      router.refresh();
      return;
    }
    setErrores(await mensajesDeOrden(response, "No se pudieron canjear los puntos"));
  }

  if (saldo <= 0) {
    return (
      <ClayCard className="mb-6">
        <h2 className="text-sm font-bold text-(--sw-ink)">Canjear puntos</h2>
        <p role="status" className="mt-1 text-sm text-(--sw-ink-soft)">
          El cliente no cuenta con puntos disponibles para canjear.
        </p>
        <ClayButton type="button" className="mt-3" disabled>
          Canjear puntos
        </ClayButton>
      </ClayCard>
    );
  }

  if (!abierto) {
    return (
      <ClayCard className="mb-6">
        <h2 className="text-sm font-bold text-(--sw-ink)">Canjear puntos</h2>
        <p className="mt-1 text-sm text-(--sw-ink-soft)">
          El cliente tiene {saldo} puntos disponibles. Cada punto equivale a {formatCOP(pesosPorPunto)} de descuento.
        </p>
        <ClayButton type="button" className="mt-3" onClick={() => setAbierto(true)}>
          Canjear puntos
        </ClayButton>
      </ClayCard>
    );
  }

  return (
    <ClayCard className="mb-6">
      <h2 className="text-sm font-bold text-(--sw-ink)">Canjear puntos</h2>
      <form onSubmit={onSubmit} className="mt-3 flex flex-col gap-4">
        <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-xs font-semibold tracking-wide text-(--sw-ink-soft) uppercase">Saldo de puntos</dt>
            <dd className="mt-1 font-semibold text-(--sw-ink) tabular-nums">{saldo}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold tracking-wide text-(--sw-ink-soft) uppercase">Valor de la orden</dt>
            <dd className="mt-1 font-semibold text-(--sw-ink) tabular-nums">{formatCOP(total)}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold tracking-wide text-(--sw-ink-soft) uppercase">Equivalencia</dt>
            <dd className="mt-1 font-semibold text-(--sw-ink) tabular-nums">1 punto = {formatCOP(pesosPorPunto)}</dd>
          </div>
        </dl>

        <label className="flex flex-col gap-1 text-sm">
          <span className="font-medium text-(--sw-ink-soft)">Puntos a canjear</span>
          <div className="flex flex-wrap gap-2">
            <ClayInput
              type="text"
              inputMode="numeric"
              autoComplete="off"
              value={texto}
              onChange={(e) => setTexto(e.target.value.trim())}
              aria-invalid={error !== null}
              className="w-40"
              disabled={pending}
            />
            <ClayButton
              type="button"
              variant="secundario"
              onClick={() => setTexto(String(maximo))}
              disabled={pending || maximo < 1}
            >
              Usar maximo disponible ({maximo})
            </ClayButton>
          </div>
          {error && (
            <span role="alert" className="text-xs font-semibold text-(--sw-coral)">
              {error}
            </span>
          )}
        </label>

        {puntos > 0 && (
          <ul className="list-inside list-disc text-sm text-(--sw-ink-soft)">
            <li>
              Se descuentan {puntos} puntos: el saldo del cliente pasa de {saldo} a {saldo - puntos}.
            </li>
            <li>
              Descuento aplicado: {formatCOP(descuento)}. El total a pagar pasa de {formatCOP(total)} a{" "}
              {formatCOP(total - descuento)}.
            </li>
          </ul>
        )}

        <AlertaErrores titulo="No se pudieron canjear los puntos" errores={errores} />
        <div className="flex flex-wrap gap-3">
          <ClayButton type="submit" disabled={pending || puntos === 0}>
            {pending ? "Canjeando..." : "Confirmar canje"}
          </ClayButton>
          <ClayButton type="button" variant="secundario" onClick={descartar} disabled={pending}>
            Cancelar
          </ClayButton>
        </div>
      </form>
    </ClayCard>
  );
}
