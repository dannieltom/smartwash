"use client";

import { useState } from "react";

import {
  enviarComunicaciones,
  leerErroresApi,
  type ResultadoComunicaciones,
  type ResumenEnvio,
} from "@/lib/api";
import { ClayButton } from "../components/ui/clay";

const ERROR_CONEXION = "No se pudo conectar con el servidor. Intenta de nuevo.";

class EnvioFallido extends Error {
  status: number | null;
  causa: unknown;

  constructor(message: string, status: number | null, causa?: unknown) {
    super(message);
    this.status = status;
    this.causa = causa;
  }
}

function esResultado(data: unknown): data is ResultadoComunicaciones {
  return typeof data === "object" && data !== null && "recordatorios" in data && "promociones" in data;
}

async function solicitarEnvio(): Promise<ResultadoComunicaciones> {
  let response: Response;
  try {
    response = await enviarComunicaciones();
  } catch (causa) {
    throw new EnvioFallido(ERROR_CONEXION, null, causa);
  }

  if (!response.ok) {
    const { detail } = await leerErroresApi(response);
    const mensaje = detail?.[0] ?? `No se pudo completar el envio (error ${response.status}).`;
    throw new EnvioFallido(mensaje, response.status);
  }

  const data: unknown = await response.json().catch(() => null);
  if (!esResultado(data)) {
    throw new EnvioFallido("El servidor respondio con un formato inesperado.", response.status);
  }
  return data;
}

function Resumen({ titulo, resumen }: { titulo: string; resumen: ResumenEnvio }) {
  return (
    <div className="clay-sm p-4">
      <h3 className="sw-eyebrow">{titulo}</h3>
      <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
        <div>
          <dt className="text-(--sw-ink-soft)">Enviados y registrados</dt>
          <dd className="text-lg font-bold text-(--sw-ink)">{resumen.enviados}</dd>
        </div>
        <div>
          <dt className="text-(--sw-ink-soft)">Sin correo</dt>
          <dd className="text-lg font-bold text-(--sw-ink)">{resumen.sin_correo}</dd>
        </div>
        <div>
          <dt className="text-(--sw-ink-soft)">Fallidos</dt>
          <dd className="text-lg font-bold text-(--sw-ink)">{resumen.fallidos}</dd>
        </div>
      </dl>
    </div>
  );
}

export default function EnviarComunicaciones({ className }: { className?: string }) {
  const [resultado, setResultado] = useState<ResultadoComunicaciones | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function enviar() {
    setPending(true);
    setError(null);
    try {
      setResultado(await solicitarEnvio());
    } catch (causa) {
      // El resultado anterior se conserva: si el envio fallo, en pantalla no
      // debe aparecer nada como enviado ni registrado.
      const fallo = causa instanceof EnvioFallido ? causa : new EnvioFallido(ERROR_CONEXION, null, causa);
      console.error("[comunicaciones] fallo el envio", {
        status: fallo.status,
        mensaje: fallo.message,
        causa: fallo.causa,
      });
      setError(fallo.message);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className={className}>
      <p className="text-sm text-(--sw-ink-soft)">
        Envia los recordatorios de ordenes no reclamadas y las promociones vigentes. Cada correo que
        sale queda registrado en el historial de comunicaciones del cliente.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <ClayButton type="button" onClick={enviar} disabled={pending}>
          {pending ? "Enviando..." : "Enviar comunicaciones"}
        </ClayButton>
      </div>

      {error && (
        <div role="alert" className="clay-sm mt-4 border-l-8 border-l-(--sw-coral) p-4 text-sm">
          <p className="font-semibold text-(--sw-ink)">No se enviaron las comunicaciones</p>
          <p className="mt-1 text-(--sw-ink-soft)">{error}</p>
        </div>
      )}

      {resultado && (
        <div role="status" className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Resumen titulo="Recordatorios" resumen={resultado.recordatorios} />
          <Resumen titulo="Promociones" resumen={resultado.promociones} />
        </div>
      )}
    </div>
  );
}
