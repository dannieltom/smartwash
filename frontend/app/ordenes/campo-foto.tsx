"use client";

import { useId, useState, type ChangeEvent } from "react";

import { ClayButton } from "../components/ui/clay";
import { formatKB, prepararFoto, type FotoLista } from "./foto";

export default function CampoFoto({
  etiqueta,
  foto,
  onChange,
  obligatoria = false,
}: {
  etiqueta: string;
  foto: FotoLista | null;
  onChange: (foto: FotoLista | null) => void;
  obligatoria?: boolean;
}) {
  const id = useId();
  const [error, setError] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);

  async function onArchivo(event: ChangeEvent<HTMLInputElement>) {
    const input = event.currentTarget;
    const archivo = input.files?.[0];
    if (!archivo) return;
    setError(null);
    setProcesando(true);
    try {
      onChange(await prepararFoto(archivo));
    } catch (motivo) {
      onChange(null);
      setError(motivo instanceof Error ? motivo.message : "No se pudo procesar la foto.");
    } finally {
      setProcesando(false);
      // Permite volver a elegir el mismo archivo despues de quitarlo.
      input.value = "";
    }
  }

  return (
    <div className="flex flex-col gap-2 text-sm">
      <label htmlFor={id} className="font-medium text-(--sw-ink-soft)">
        {etiqueta}
        {obligatoria ? " (obligatoria)" : " (opcional)"}
      </label>
      <input
        id={id}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture="environment"
        onChange={onArchivo}
        disabled={procesando}
        className="text-sm text-(--sw-ink-soft) file:mr-3 file:rounded-xl file:border-0 file:bg-(--sw-surface) file:px-3 file:py-2 file:font-semibold file:text-(--sw-ink)"
      />
      {procesando && <p className="text-(--sw-ink-soft)">Preparando la foto...</p>}
      {error && (
        <p role="alert" className="font-semibold text-(--sw-ink)">
          {error}
        </p>
      )}
      {foto && (
        <div className="flex flex-wrap items-end gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element -- data URL local, next/image no aplica */}
          <img src={foto.dataUrl} alt="Vista previa de la foto" className="h-28 w-auto rounded-xl object-cover" />
          <div className="flex flex-col gap-1">
            <p className="text-xs text-(--sw-ink-soft)">
              {foto.bytes < foto.bytesOriginales
                ? `Reducida de ${formatKB(foto.bytesOriginales)} a ${formatKB(foto.bytes)}`
                : formatKB(foto.bytes)}
            </p>
            <ClayButton type="button" variant="secundario" onClick={() => onChange(null)} className="h-8 text-xs">
              Quitar foto
            </ClayButton>
          </div>
        </div>
      )}
    </div>
  );
}
