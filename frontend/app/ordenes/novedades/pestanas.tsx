"use client";

import { useRouter } from "next/navigation";
import { useRef, type KeyboardEvent } from "react";

export const PESTANAS = [
  { id: "pendientes", etiqueta: "Pendientes", href: "/ordenes/novedades" },
  { id: "historial", etiqueta: "Historial", href: "/ordenes/novedades?vista=historial" },
] as const;

export type Vista = (typeof PESTANAS)[number]["id"];

/** Cada pestana es una URL (?vista=historial): refrescar o compartir conserva la vista. */
export default function PestanasNovedades({ activa }: { activa: Vista }) {
  const router = useRouter();
  const botones = useRef<Record<Vista, HTMLButtonElement | null>>({ pendientes: null, historial: null });

  function ir(id: Vista) {
    if (id !== activa) router.push(PESTANAS.find((p) => p.id === id)!.href);
  }

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const actual = PESTANAS.findIndex((p) => p.id === activa);
    const destino = {
      ArrowRight: (actual + 1) % PESTANAS.length,
      ArrowLeft: (actual - 1 + PESTANAS.length) % PESTANAS.length,
      Home: 0,
      End: PESTANAS.length - 1,
    }[event.key];
    if (destino === undefined) return;
    event.preventDefault();
    const id = PESTANAS[destino].id;
    botones.current[id]?.focus();
    ir(id);
  }

  return (
    <div role="tablist" aria-label="Novedades" onKeyDown={onKeyDown} className="mb-6 flex flex-wrap gap-2">
      {PESTANAS.map((p) => {
        const seleccionada = p.id === activa;
        return (
          <button
            key={p.id}
            ref={(boton) => {
              botones.current[p.id] = boton;
            }}
            type="button"
            role="tab"
            id={`pestana-${p.id}`}
            aria-selected={seleccionada}
            aria-controls={`panel-${p.id}`}
            tabIndex={seleccionada ? 0 : -1}
            onClick={() => ir(p.id)}
            className={`clay-press rounded-full px-4 py-2 text-sm font-bold text-(--sw-ink) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--sw-ink) ${
              seleccionada ? "bg-(--sw-accent)" : "bg-(--sw-surface) opacity-80"
            }`}
          >
            {p.etiqueta}
          </button>
        );
      })}
    </div>
  );
}
