"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { AlertaErrores } from "@/app/catalogo/errores";
import { registrarDecision, type DecisionNovedad, type OrdenConNovedad } from "@/lib/api";
import { ClayButton, ClayField, ClaySelect, ClayTextarea } from "../../components/ui/clay";
import { mensajesDeOrden } from "../errores";

type DecisionProceso = Extract<DecisionNovedad, "continuar" | "reprocesar" | "no_continuar">;

const OPCIONES: { valor: DecisionProceso; etiqueta: string }[] = [
  { valor: "continuar", etiqueta: "Continuar igual" },
  { valor: "reprocesar", etiqueta: "Reprocesar" },
  { valor: "no_continuar", etiqueta: "No continuar" },
];

async function mensajesDeDecision(response: Response | null): Promise<string[]> {
  if (response?.status === 403) return ["No tienes permiso para registrar esta decision."];
  if (response && response.status >= 500) return ["Error del servidor. Intenta de nuevo en unos minutos."];
  return mensajesDeOrden(response, "No se pudo registrar la decision");
}

export default function ModalDecisionProceso({
  orden,
  onCerrar,
}: {
  orden: OrdenConNovedad;
  onCerrar: () => void;
}) {
  const router = useRouter();
  const dialogo = useRef<HTMLDialogElement>(null);
  const [decision, setDecision] = useState<DecisionProceso | "">("");
  const [observacion, setObservacion] = useState("");
  const [errores, setErrores] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    dialogo.current?.showModal();
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!decision) return;
    setPending(true);
    setErrores([]);
    const response = await registrarDecision(orden.id, {
      decision,
      observacion: observacion.trim(),
    }).catch(() => null);
    setPending(false);

    if (response?.ok) {
      onCerrar();
      router.refresh();
      return;
    }
    setErrores(await mensajesDeDecision(response));
  }

  return (
    <dialog
      ref={dialogo}
      onClose={onCerrar}
      onCancel={(e) => pending && e.preventDefault()}
      aria-labelledby="titulo-decision"
      className="clay m-auto w-[calc(100%-2rem)] max-w-lg p-5 text-(--sw-ink) backdrop:bg-black/40 sm:p-6"
    >
      <h2 id="titulo-decision" className="text-lg font-bold">
        Decision del cliente · {orden.codigo}
      </h2>
      <p className="mt-1 text-sm text-(--sw-ink-soft)">
        {orden.novedades.length === 1
          ? "La decision aplica a la novedad pendiente de la orden."
          : `La decision aplica a las ${orden.novedades.length} novedades pendientes de la orden.`}
      </p>

      <form onSubmit={onSubmit} className="mt-4 flex flex-col gap-4">
        <ClayField label="Decision">
          <ClaySelect
            value={decision}
            onChange={(e) => setDecision(e.target.value as DecisionProceso)}
            required
          >
            <option value="" disabled>
              Elige la decision del cliente
            </option>
            {OPCIONES.map((o) => (
              <option key={o.valor} value={o.valor}>
                {o.etiqueta}
              </option>
            ))}
          </ClaySelect>
        </ClayField>
        <ClayTextarea
          aria-label="Observacion de la decision"
          placeholder="Con quien se hablo y que decidio (obligatorio)"
          value={observacion}
          onChange={(e) => setObservacion(e.target.value)}
          className="min-h-24"
          required
        />
        <AlertaErrores titulo="No se pudo registrar la decision" errores={errores} />
        <div className="flex flex-wrap gap-3">
          <ClayButton type="submit" disabled={pending || !decision || observacion.trim() === ""}>
            {pending ? "Registrando..." : "Registrar decision"}
          </ClayButton>
          <ClayButton type="button" variant="secundario" onClick={onCerrar} disabled={pending}>
            Cancelar
          </ClayButton>
        </div>
      </form>
    </dialog>
  );
}
