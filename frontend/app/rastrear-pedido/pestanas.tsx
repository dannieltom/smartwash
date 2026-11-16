"use client";

import { useRef, useState, type KeyboardEvent } from "react";

import RastreoDocumento from "./rastreo-documento";
import RastreoForm from "./rastreo-form";

const PESTANAS = [
  { id: "codigo", etiqueta: "Con código" },
  { id: "cedula", etiqueta: "Con cédula" },
] as const;

type Pestana = (typeof PESTANAS)[number]["id"];

export default function PestanasRastreo() {
  const [activa, setActiva] = useState<Pestana>("codigo");
  const botones = useRef<Record<Pestana, HTMLButtonElement | null>>({ codigo: null, cedula: null });

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
    setActiva(id);
    botones.current[id]?.focus();
  }

  return (
    <div className="flex flex-col gap-6">
      <div role="tablist" aria-label="Forma de consultar" onKeyDown={onKeyDown} className="flex flex-wrap gap-2">
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
              onClick={() => setActiva(p.id)}
              className={`clay-press rounded-full px-4 py-2 text-sm font-bold text-(--sw-ink) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--sw-ink) ${
                seleccionada ? "bg-(--sw-accent)" : "bg-(--sw-surface) opacity-80"
              }`}
            >
              {p.etiqueta}
            </button>
          );
        })}
      </div>
      {/* Solo se monta el panel activo: al cambiar de pestana se descarta el resultado anterior. */}
      <div role="tabpanel" id={`panel-${activa}`} aria-labelledby={`pestana-${activa}`}>
        {activa === "codigo" ? <RastreoForm /> : <RastreoDocumento />}
      </div>
    </div>
  );
}
