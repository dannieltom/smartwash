"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AlertaErrores, mensajesDeError } from "@/app/catalogo/errores";
import { pagarDano, type DanoPrenda } from "@/lib/api";
import { formatCOP } from "@/lib/format";
import { ClayButton, ClayTextarea } from "../components/ui/clay";

export default function PagarDano({ dano }: { dano: DanoPrenda }) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(false);
  const [observacion, setObservacion] = useState("");
  const [errores, setErrores] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  function cancelar() {
    setAbierto(false);
    setObservacion("");
    setErrores([]);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setErrores([]);
    const response = await pagarDano(dano.id, observacion.trim()).catch(() => null);
    setPending(false);

    if (response?.ok) {
      cancelar();
      router.refresh();
      return;
    }
    setErrores(await mensajesDeError(response, { observacion: "Observacion" }, "No se pudo registrar el pago"));
  }

  if (!abierto) {
    return (
      <ClayButton type="button" className="mt-4" onClick={() => setAbierto(true)}>
        Marcar como pagado
      </ClayButton>
    );
  }

  return (
    <form onSubmit={onSubmit} className="mt-4 flex flex-col gap-3">
      <ClayTextarea
        aria-label={`Observacion del pago de ${dano.prenda_nombre}`}
        placeholder={`Como se pagaron los ${formatCOP(dano.valor_declarado)} (obligatorio)`}
        value={observacion}
        onChange={(e) => setObservacion(e.target.value)}
        className="min-h-20"
        required
      />
      <AlertaErrores titulo="No se pudo registrar el pago" errores={errores} />
      <div className="flex flex-wrap gap-3">
        <ClayButton type="submit" disabled={pending || observacion.trim() === ""}>
          {pending ? "Registrando..." : "Confirmar pago"}
        </ClayButton>
        <ClayButton type="button" variant="secundario" onClick={cancelar} disabled={pending}>
          Cancelar
        </ClayButton>
      </div>
    </form>
  );
}
