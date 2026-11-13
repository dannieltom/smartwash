"use client";

import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { getTurnoActual, RUTA_TURNO, terminarTurno } from "@/lib/api";
import { ClayButton } from "./ui/clay";

export default function TerminarTurno() {
  const router = useRouter();
  const ruta = usePathname();
  // null: sin confirmar todavia; un numero: las ordenes en curso que conserva.
  const [enCurso, setEnCurso] = useState<number | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState(false);

  async function preguntar() {
    setPending(true);
    setError(false);
    const actual = await getTurnoActual();
    setPending(false);
    setEnCurso(actual?.ordenes_en_curso ?? 0);
  }

  async function confirmar() {
    setPending(true);
    const response = await terminarTurno().catch(() => null);
    setPending(false);
    // Sin turno (400) tambien termina en /turno. Al refrescar, la pagina actual manda a /turno
    // y el servidor repinta la barra sin el boton.
    if (response && (response.ok || response.status === 400)) {
      router.refresh();
      return;
    }
    setError(true);
  }

  // Fuera de /turno el operario siempre tiene turno: si no, el servidor ya lo habria mandado ahi.
  if (ruta === RUTA_TURNO) return null;

  if (enCurso === null) {
    return (
      <ClayButton type="button" variant="coral" onClick={preguntar} disabled={pending}>
        Terminar turno
      </ClayButton>
    );
  }

  return (
    <div role="alertdialog" aria-label="Terminar turno" className="clay-sm flex flex-col gap-2 p-3 text-sm">
      <p className="font-semibold text-(--sw-ink)">
        {enCurso === 0
          ? "No tienes ordenes en curso."
          : `Conservas ${enCurso === 1 ? "1 orden en curso" : `${enCurso} ordenes en curso`}: siguen asignadas a ti.`}
      </p>
      {error && <p className="text-(--sw-ink)">No se pudo terminar el turno. Intenta de nuevo.</p>}
      <div className="flex flex-wrap gap-2">
        <ClayButton type="button" variant="coral" onClick={confirmar} disabled={pending}>
          {pending ? "Terminando..." : "Terminar turno"}
        </ClayButton>
        <ClayButton type="button" variant="secundario" onClick={() => setEnCurso(null)} disabled={pending}>
          Seguir trabajando
        </ClayButton>
      </div>
    </div>
  );
}
