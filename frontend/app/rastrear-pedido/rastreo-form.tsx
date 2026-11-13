"use client";

import { useState, type FormEvent } from "react";

import { AlertaErrores } from "@/app/catalogo/errores";
import { leerErroresApi, rastrearOrden, type SeguimientoOrden } from "@/lib/api";
import { ClayBadge, ClayButton, ClayCard, ClayField, ClayInput } from "../components/ui/clay";
import { COLOR_ESTADO } from "../ordenes/tabla-ordenes";
import CalificarOrden from "./calificacion";
import LineaTiempo, { fechaLarga, fechaYHora } from "./linea-tiempo";

type Fallo = { titulo: string; mensaje: string };

// El codigo impreso es SW- y 8 caracteres en mayusculas; la busqueda del backend es exacta.
function normalizar(codigo: string) {
  return codigo.replace(/\s+/g, "").toUpperCase();
}

function Aviso({ orden }: { orden: SeguimientoOrden }) {
  let texto: string | null = null;
  if (orden.cancelada) {
    texto = orden.fecha_cancelacion
      ? `Esta orden fue cancelada el ${fechaYHora(orden.fecha_cancelacion)}`
      : "Esta orden fue cancelada.";
  } else if (orden.estado === "En espera") {
    texto = "Pendiente de abono: la fecha de entrega se asigna al abonar.";
  } else if (orden.con_novedad) {
    texto = "Tu pedido tiene una novedad. Te contactaremos.";
  } else if (orden.estado === "Lista para entrega") {
    texto = "Tu pedido esta listo: ya puedes recogerlo.";
  }
  if (!texto) return null;
  return (
    <p role="status" className="clay-sm mt-4 border-l-8 border-l-(--sw-accent) p-3 text-sm font-semibold text-(--sw-ink)">
      {texto}
    </p>
  );
}

export async function leerSeguimiento(response: Response): Promise<SeguimientoOrden> {
  // Un backend anterior a la linea de tiempo no manda etapas ni eventos: se muestra sin ella.
  const datos = (await response.json()) as Partial<SeguimientoOrden> & Pick<SeguimientoOrden, "codigo" | "estado">;
  return {
    fecha_estimada_entrega: null,
    etapa_actual: null,
    con_novedad: false,
    cancelada: datos.estado === "Cancelada",
    fecha_cancelacion: null,
    calificacion: null,
    ...datos,
    etapas: datos.etapas ?? [],
    eventos: datos.eventos ?? [],
  };
}

/** `conCalificacion` en false cuando quien la muestra ya pinta el bloque de calificacion. */
export function Detalle({ orden, conCalificacion = true }: { orden: SeguimientoOrden; conCalificacion?: boolean }) {
  const pendienteDeEntrega = !orden.cancelada && orden.estado !== "Entregada";
  return (
    <>
      <Aviso orden={orden} />
      {orden.etapas.length > 0 && (
        <div className="mt-5">
          <LineaTiempo orden={orden} />
        </div>
      )}
      {conCalificacion && orden.estado === "Entregada" && (
        <CalificarOrden codigo={orden.codigo} calificacion={orden.calificacion} />
      )}
      {pendienteDeEntrega && orden.fecha_estimada_entrega && (
        <p className="mt-5 text-sm text-(--sw-ink-soft)">
          Entrega estimada: <strong className="text-(--sw-ink)">{fechaLarga(orden.fecha_estimada_entrega)}</strong>
        </p>
      )}
      {orden.eventos.length > 0 && (
        <details className="mt-4 text-sm">
          <summary className="cursor-pointer font-semibold text-(--sw-ink)">Ver movimientos</summary>
          <ol className="mt-2 flex flex-col gap-1 text-(--sw-ink-soft)">
            {orden.eventos.map((e, i) => (
              <li key={`${e.fecha}-${i}`}>
                <span className="text-(--sw-ink)">{e.etiqueta}</span> · {fechaYHora(e.fecha)}
              </li>
            ))}
          </ol>
        </details>
      )}
    </>
  );
}

export default function RastreoForm() {
  const [resultado, setResultado] = useState<SeguimientoOrden | null>(null);
  const [fallo, setFallo] = useState<Fallo | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const codigo = normalizar(String(new FormData(event.currentTarget).get("codigo") ?? ""));
    if (!codigo) return;
    setPending(true);
    setFallo(null);
    setResultado(null);

    const response = await rastrearOrden(codigo).catch(() => null);
    setPending(false);

    if (response?.ok) {
      setResultado(await leerSeguimiento(response));
    } else if (response?.status === 404) {
      const { detail } = await leerErroresApi(response);
      setFallo({
        titulo: "Codigo no encontrado",
        mensaje: detail?.[0] ?? "No encontramos una orden con ese codigo. Revisa el comprobante.",
      });
    } else {
      setFallo({
        titulo: "No se pudo consultar",
        mensaje: "No pudimos consultar el estado en este momento. Intenta de nuevo en unos minutos.",
      });
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={onSubmit} className="flex flex-col gap-4 sm:flex-row sm:items-end">
        <div className="flex-1">
          <ClayField label="Codigo de tu pedido">
            <ClayInput name="codigo" placeholder="Ej. SW-ABCD2345" autoCapitalize="characters" autoComplete="off" required />
          </ClayField>
        </div>
        <ClayButton type="submit" disabled={pending}>
          {pending ? "Buscando..." : "Rastrear"}
        </ClayButton>
      </form>

      {resultado && (
        <ClayCard>
          <p className="text-xs font-extrabold tracking-[0.08em] text-(--sw-ink-soft) uppercase">
            Pedido {resultado.codigo}
          </p>
          <div className="mt-2">
            <ClayBadge color={COLOR_ESTADO[resultado.estado]}>{resultado.estado}</ClayBadge>
          </div>
          <Detalle orden={resultado} />
        </ClayCard>
      )}

      {fallo && <AlertaErrores titulo={fallo.titulo} errores={[fallo.mensaje]} />}
    </div>
  );
}
