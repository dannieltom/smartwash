"use client";

import { useState, type FormEvent } from "react";

import { rastrearOrden, type SeguimientoOrden } from "@/lib/api";
import { ClayBadge, ClayButton, ClayCard, ClayField, ClayInput } from "../components/ui/clay";

const MENSAJES_ERROR = {
  no_encontrada: "No encontramos una orden con ese código. Revisa el comprobante.",
  error: "No pudimos consultar tu pedido. Revisa tu conexión e inténtalo de nuevo en unos minutos.",
} as const;

export default function RastreoForm() {
  const [resultado, setResultado] = useState<SeguimientoOrden | null>(null);
  const [error, setError] = useState<keyof typeof MENSAJES_ERROR | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setResultado(null);

    const form = new FormData(event.currentTarget);
    const codigo = String(form.get("codigo") ?? "").trim();
    if (!codigo) {
      setError("no_encontrada");
      return;
    }

    setPending(true);
    const respuesta = await rastrearOrden(codigo);
    setPending(false);

    if (respuesta.tipo === "encontrada") {
      setResultado(respuesta.orden);
    } else {
      setError(respuesta.tipo);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={onSubmit} className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="flex-1">
          <ClayField label="Codigo de tu pedido">
            <ClayInput name="codigo" placeholder="Ej. SW-ABCD2345" required />
          </ClayField>
        </div>
        <ClayButton type="submit" disabled={pending}>
          {pending ? "Buscando..." : "Rastrear"}
        </ClayButton>
      </form>

      {resultado && (
        <ClayCard>
          <p className="text-xs font-extrabold tracking-[0.08em] text-(--sw-ink-soft) uppercase">
            Pedido {resultado.codigo}
          </p>
          <div className="mt-2">
            <ClayBadge>{resultado.estado}</ClayBadge>
          </div>
          {resultado.fecha_estimada_entrega && (
            <p className="mt-3 text-sm text-(--sw-ink-soft)">
              Entrega estimada: {new Date(resultado.fecha_estimada_entrega).toLocaleString("es-CO")}
            </p>
          )}
        </ClayCard>
      )}

      {error && (
        <div role="alert" className="clay-sm border-l-8 border-l-(--sw-coral) p-4 text-sm text-(--sw-ink)">
          {MENSAJES_ERROR[error]}
        </div>
      )}
    </div>
  );
}
