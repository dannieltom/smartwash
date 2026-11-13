"use client";

import { useState, type FormEvent, type ReactNode } from "react";

import { AlertaErrores } from "@/app/catalogo/errores";
import { crearPqrs, leerErroresApi, type ErroresApi, type PqrsFormulario, type TipoPqrs } from "@/lib/api";
import { ClayButton, ClayField, ClayInput, ClaySelect, ClayTextarea } from "../components/ui/clay";

const TIPOS: { valor: TipoPqrs; etiqueta: string }[] = [
  { valor: "peticion", etiqueta: "Peticion" },
  { valor: "queja", etiqueta: "Queja" },
  { valor: "reclamo", etiqueta: "Reclamo" },
  { valor: "sugerencia", etiqueta: "Sugerencia" },
];

const CAMPOS = ["tipo", "codigo_orden", "nombre", "documento", "correo", "telefono", "mensaje"] as const;
type Campo = (typeof CAMPOS)[number];

function ErrorDeCampo({ campo, errores }: { campo: Campo; errores: ErroresApi }) {
  const mensajes = errores[campo];
  if (!mensajes?.length) return null;
  return (
    <span id={`error-${campo}`} role="alert" className="text-xs font-semibold tracking-normal text-(--sw-danger) normal-case">
      {mensajes.join(" ")}
    </span>
  );
}

function ConError({ campo, errores, children }: { campo: Campo; errores: ErroresApi; children: ReactNode }) {
  return (
    <>
      {children}
      <ErrorDeCampo campo={campo} errores={errores} />
    </>
  );
}

export default function PqrsForm({ tipoInicial, codigoInicial }: { tipoInicial: TipoPqrs; codigoInicial: string }) {
  const [tipo, setTipo] = useState<TipoPqrs>(tipoInicial);
  const [enviado, setEnviado] = useState(false);
  const [errores, setErrores] = useState<ErroresApi>({});
  const [general, setGeneral] = useState<string[]>([]);
  const [pending, setPending] = useState(false);
  const codigoObligatorio = tipo !== "sugerencia";

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setErrores({});
    setGeneral([]);

    const form = new FormData(event.currentTarget);
    const datos: PqrsFormulario = {
      tipo,
      nombre: String(form.get("nombre") ?? ""),
      documento: String(form.get("documento") ?? ""),
      correo: String(form.get("correo") ?? ""),
      telefono: String(form.get("telefono") ?? ""),
      codigo_orden: String(form.get("codigo_orden") ?? "").replace(/\s+/g, "").toUpperCase(),
      mensaje: String(form.get("mensaje") ?? ""),
    };

    const response = await crearPqrs(datos).catch(() => null);
    setPending(false);

    if (response?.ok) {
      setEnviado(true);
    } else if (response?.status === 429) {
      setGeneral(["Demasiados envíos. Inténtalo más tarde."]);
    } else if (response?.status === 400) {
      const recibidos = await leerErroresApi(response);
      const porCampo = Object.fromEntries(Object.entries(recibidos).filter(([c]) => (CAMPOS as readonly string[]).includes(c)));
      const otros = Object.entries(recibidos)
        .filter(([c]) => !(CAMPOS as readonly string[]).includes(c))
        .flatMap(([, mensajes]) => mensajes);
      setErrores(porCampo);
      setGeneral(otros);
    } else {
      setGeneral(["No pudimos enviar tu solicitud en este momento. Intenta de nuevo en unos minutos."]);
    }
  }

  if (enviado) {
    return (
      <p role="status" className="text-sm text-(--sw-ink)">
        Recibimos tu solicitud. Te respondemos por el correo o telefono que nos dejaste.
      </p>
    );
  }

  const describe = (campo: Campo) => (errores[campo]?.length ? `error-${campo}` : undefined);

  return (
    <form onSubmit={onSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <ClayField label="Tipo de solicitud">
        <ConError campo="tipo" errores={errores}>
          <ClaySelect
            name="tipo"
            value={tipo}
            onChange={(e) => setTipo(e.target.value as TipoPqrs)}
            aria-describedby={describe("tipo")}
            required
          >
            {TIPOS.map((t) => (
              <option key={t.valor} value={t.valor}>
                {t.etiqueta}
              </option>
            ))}
          </ClaySelect>
        </ConError>
      </ClayField>
      <ClayField label={codigoObligatorio ? "Código de tu pedido *" : "Código de tu pedido (opcional)"}>
        <ConError campo="codigo_orden" errores={errores}>
          <ClayInput
            name="codigo_orden"
            defaultValue={codigoInicial}
            placeholder="Ej. SW-ABCD2345"
            autoCapitalize="characters"
            autoComplete="off"
            required={codigoObligatorio}
            aria-invalid={Boolean(errores.codigo_orden?.length)}
            aria-describedby={describe("codigo_orden")}
          />
        </ConError>
      </ClayField>
      <ClayField label="Nombre completo">
        <ConError campo="nombre" errores={errores}>
          <ClayInput name="nombre" required aria-describedby={describe("nombre")} />
        </ConError>
      </ClayField>
      <ClayField label="Documento">
        <ConError campo="documento" errores={errores}>
          <ClayInput name="documento" required aria-describedby={describe("documento")} />
        </ConError>
      </ClayField>
      <ClayField label="Correo">
        <ConError campo="correo" errores={errores}>
          <ClayInput name="correo" type="email" required aria-describedby={describe("correo")} />
        </ConError>
      </ClayField>
      <ClayField label="Telefono">
        <ConError campo="telefono" errores={errores}>
          <ClayInput name="telefono" aria-describedby={describe("telefono")} />
        </ConError>
      </ClayField>

      <div className="sm:col-span-2">
        <ClayField label="Cuentanos que paso">
          <ConError campo="mensaje" errores={errores}>
            <ClayTextarea name="mensaje" required aria-describedby={describe("mensaje")} />
          </ConError>
        </ClayField>
      </div>

      {general.length > 0 && (
        <div className="sm:col-span-2">
          <AlertaErrores titulo="No se pudo enviar tu solicitud" errores={general} />
        </div>
      )}

      <div className="sm:col-span-2">
        <ClayButton type="submit" disabled={pending}>
          {pending ? "Enviando..." : "Enviar solicitud"}
        </ClayButton>
      </div>
    </form>
  );
}
