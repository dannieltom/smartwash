"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { iniciarTurno } from "@/lib/api";
import { ClayButton } from "../components/ui/clay";

export default function IniciarTurno() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);

  async function iniciar() {
    setPending(true);
    setError(false);
    const response = await iniciarTurno().catch(() => null);
    // 400 = ya tenia un turno vigente (otra pestana): igual puede trabajar. Al refrescar,
    // /turno manda a la bandeja y el servidor repinta la barra (el layout no cambia al navegar).
    if (response && (response.ok || response.status === 400)) {
      router.refresh();
      return;
    }
    setPending(false);
    setError(true);
  }

  return (
    <div className="flex flex-col items-center gap-3">
      <ClayButton type="button" onClick={iniciar} disabled={pending} className="min-h-16 px-10 text-lg">
        {pending ? "Iniciando..." : "Iniciar turno"}
      </ClayButton>
      {error && (
        <p role="alert" className="text-sm font-semibold text-(--sw-ink)">
          No se pudo iniciar el turno. Intenta de nuevo.
        </p>
      )}
    </div>
  );
}
