"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AlertaErrores, mensajesDeError } from "@/app/catalogo/errores";
import { actualizarConfiguracionDescuentos, type ConfiguracionDescuentos } from "@/lib/api";
import { ClayButton, ClayField, ClayInput } from "../../components/ui/clay";

type Campo = Exclude<keyof ConfiguracionDescuentos, "actualizado_en">;

const CAMPOS: { campo: Campo; etiqueta: string; porcentaje: boolean }[] = [
  { campo: "porcentaje_leve", etiqueta: "Gravedad leve (%)", porcentaje: true },
  { campo: "porcentaje_moderada", etiqueta: "Gravedad moderada (%)", porcentaje: true },
  { campo: "porcentaje_notoria", etiqueta: "Gravedad notoria (%)", porcentaje: true },
  { campo: "porcentaje_reproceso", etiqueta: "Reproceso, por prenda (%)", porcentaje: true },
  { campo: "monto_minimo", etiqueta: "Monto minimo por prenda ($)", porcentaje: false },
  { campo: "tope_porcentaje", etiqueta: "Tope acumulado por prenda (%)", porcentaje: true },
];

const ETIQUETAS = Object.fromEntries(CAMPOS.map((c) => [c.campo, c.etiqueta]));

export default function DescuentosForm({ configuracion }: { configuracion: ConfiguracionDescuentos }) {
  const router = useRouter();
  const [errores, setErrores] = useState<string[]>([]);
  const [guardada, setGuardada] = useState(false);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setErrores([]);
    setGuardada(false);
    const datos = Object.fromEntries(CAMPOS.map(({ campo }) => [campo, String(form.get(campo) ?? "")])) as Record<
      Campo,
      string
    >;
    const response = await actualizarConfiguracionDescuentos(datos).catch(() => null);
    setPending(false);

    if (response?.ok) {
      setGuardada(true);
      router.refresh();
      return;
    }
    setErrores(await mensajesDeError(response, ETIQUETAS, "No se pudo guardar la configuracion"));
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        {CAMPOS.map(({ campo, etiqueta, porcentaje }) => (
          <ClayField key={campo} label={etiqueta}>
            <ClayInput
              name={campo}
              type="number"
              min="0"
              max={porcentaje ? "100" : undefined}
              step={porcentaje ? "0.01" : "100"}
              defaultValue={Number(configuracion[campo])}
              required
            />
          </ClayField>
        ))}
      </div>
      <p className="text-xs text-(--sw-ink-soft)">
        Los porcentajes se aplican sobre el valor de la prenda. Si el porcentaje da menos que el minimo, se
        descuenta el minimo; lo acumulado en una prenda nunca pasa del tope.
      </p>
      <AlertaErrores titulo="No se pudo guardar la configuracion" errores={errores} />
      {guardada && (
        <p role="status" className="text-sm font-semibold text-(--sw-ink)">
          Configuracion guardada.
        </p>
      )}
      <div>
        <ClayButton type="submit" disabled={pending}>
          {pending ? "Guardando..." : "Guardar"}
        </ClayButton>
      </div>
    </form>
  );
}
