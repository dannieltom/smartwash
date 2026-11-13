"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";

import { AlertaErrores } from "@/app/catalogo/errores";
import { calificarOrden, leerErroresApi } from "@/lib/api";
import { Estrellas } from "../components/estrellas";
import { clayBtnClass, ClayButton, ClayField, ClayTextarea } from "../components/ui/clay";

const MAXIMO_COMENTARIO = 500;

function Gracias({ codigo, estrellas }: { codigo: string; estrellas: number }) {
  return (
    <div role="status" className="flex flex-col gap-2">
      <p className="text-sm font-bold text-(--sw-ink)">Gracias por tu opinión</p>
      <p className="text-lg">
        <Estrellas estrellas={estrellas} />
      </p>
      {estrellas <= 2 && (
        <div className="mt-1">
          <p className="text-sm text-(--sw-ink-soft)">Sentimos que no haya salido bien. Cuéntanos qué pasó.</p>
          <Link
            href={`/pqrs?tipo=queja&codigo=${encodeURIComponent(codigo)}`}
            className={`${clayBtnClass("coral")} mt-2`}
          >
            Presentar una queja
          </Link>
        </div>
      )}
    </div>
  );
}

export default function CalificarOrden({
  codigo,
  calificacion,
}: {
  codigo: string;
  calificacion: { estrellas: number } | null;
}) {
  const [enviada, setEnviada] = useState<number | null>(calificacion?.estrellas ?? null);
  const [elegidas, setElegidas] = useState(0);
  const [errores, setErrores] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (elegidas === 0) {
      setErrores(["Elige de 1 a 5 estrellas."]);
      return;
    }
    const comentario = String(new FormData(event.currentTarget).get("comentario") ?? "").trim();
    setPending(true);
    setErrores([]);
    const response = await calificarOrden(codigo, elegidas, comentario).catch(() => null);
    setPending(false);

    if (response?.ok) {
      setEnviada(elegidas);
    } else if (response?.status === 429) {
      setErrores(["Demasiados intentos. Inténtalo de nuevo más tarde."]);
    } else if (response && [400, 404].includes(response.status)) {
      setErrores(Object.values(await leerErroresApi(response)).flat());
    } else {
      setErrores(["No pudimos enviar tu calificación. Intenta de nuevo en unos minutos."]);
    }
  }

  return (
    <section aria-label="Calificación del servicio" className="clay-sm mt-5 p-4">
      {enviada !== null ? (
        <Gracias codigo={codigo} estrellas={enviada} />
      ) : (
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <fieldset>
            <legend className="text-sm font-bold text-(--sw-ink)">¿Qué tan satisfecho quedaste?</legend>
            <div className="mt-2 flex gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => setElegidas(n)}
                  aria-label={n === 1 ? "1 estrella" : `${n} estrellas`}
                  aria-pressed={elegidas === n}
                  className={`flex h-11 w-11 items-center justify-center rounded-full text-2xl leading-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--sw-ink) ${
                    n <= elegidas ? "text-(--sw-ink)" : "text-(--sw-ink-soft)"
                  } ${elegidas === n ? "bg-(--sw-sun)" : ""}`}
                >
                  <span aria-hidden="true">{n <= elegidas ? "★" : "☆"}</span>
                </button>
              ))}
            </div>
            <p className="mt-1 text-xs text-(--sw-ink-soft)" aria-live="polite">
              {elegidas === 0 ? "Elige de 1 a 5 estrellas." : `Elegiste ${elegidas} de 5.`}
            </p>
          </fieldset>
          <ClayField label="Comentario (opcional)">
            <ClayTextarea name="comentario" maxLength={MAXIMO_COMENTARIO} rows={3} />
          </ClayField>
          {errores.length > 0 && <AlertaErrores titulo="No se pudo enviar tu calificación" errores={errores} />}
          <div>
            <ClayButton type="submit" disabled={pending}>
              {pending ? "Enviando..." : "Enviar calificación"}
            </ClayButton>
          </div>
        </form>
      )}
    </section>
  );
}
