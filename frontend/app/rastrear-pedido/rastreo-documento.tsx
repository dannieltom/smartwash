"use client";

import { useState, type FormEvent } from "react";

import { AlertaErrores } from "@/app/catalogo/errores";
import {
  consultarPorDocumento,
  leerErroresApi,
  rastrearOrden,
  type OrdenDeCliente,
  type OrdenesDeCliente,
  type SeguimientoOrden,
} from "@/lib/api";
import { formatCOP } from "@/lib/format";
import { ClayBadge, ClayButton, ClayCard, ClayField, ClayInput } from "../components/ui/clay";
import { COLOR_ESTADO } from "../ordenes/tabla-ordenes";
import CalificarOrden from "./calificacion";
import { Detalle, leerSeguimiento } from "./rastreo-form";

type Fallo = { titulo: string; mensaje: string };
type Seguimiento = SeguimientoOrden | "cargando" | "error";

function prendasEnTexto(prendas: OrdenDeCliente["prendas"]) {
  return prendas
    .map((p) => `${p.cantidad} × ${p.tipo_prenda}${p.servicios.length ? ` (${p.servicios.join(", ")})` : ""}`)
    .join(" · ");
}

function TarjetaOrden({ orden }: { orden: OrdenDeCliente }) {
  const [abierto, setAbierto] = useState(false);
  const [seguimiento, setSeguimiento] = useState<Seguimiento | null>(null);
  const idPanel = `seguimiento-${orden.codigo}`;

  async function alternar() {
    const abrir = !abierto;
    setAbierto(abrir);
    if (!abrir || (seguimiento !== null && seguimiento !== "error")) return;
    setSeguimiento("cargando");
    const response = await rastrearOrden(orden.codigo).catch(() => null);
    setSeguimiento(response?.ok ? await leerSeguimiento(response) : "error");
  }

  return (
    <li>
      <ClayCard>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs font-extrabold tracking-[0.08em] text-(--sw-ink-soft) uppercase">
            Pedido {orden.codigo}
          </p>
          <ClayBadge color={COLOR_ESTADO[orden.estado]}>{orden.estado}</ClayBadge>
        </div>
        <p className="mt-2 text-sm font-bold text-(--sw-ink)">{formatCOP(orden.total)}</p>
        {orden.prendas.length > 0 && <p className="mt-1 text-sm text-(--sw-ink-soft)">{prendasEnTexto(orden.prendas)}</p>}
        <div className="mt-3">
          <ClayButton type="button" variant="secundario" onClick={alternar} aria-expanded={abierto} aria-controls={idPanel}>
            {abierto ? "Ocultar seguimiento" : "Ver seguimiento"}
          </ClayButton>
        </div>
        {abierto && (
          <div id={idPanel}>
            {seguimiento === "cargando" && <p className="mt-3 text-sm text-(--sw-ink-soft)">Cargando seguimiento...</p>}
            {seguimiento === "error" && (
              <p className="mt-3 text-sm text-(--sw-ink)">No pudimos cargar el seguimiento. Intenta de nuevo.</p>
            )}
            {typeof seguimiento === "object" && seguimiento !== null && (
              <Detalle orden={seguimiento} conCalificacion={false} />
            )}
          </div>
        )}
        {orden.estado === "Entregada" && <CalificarOrden codigo={orden.codigo} calificacion={orden.calificacion} />}
      </ClayCard>
    </li>
  );
}

function ListaOrdenes({ ordenes, vacio }: { ordenes: OrdenDeCliente[]; vacio: string }) {
  if (ordenes.length === 0) return <p className="text-sm text-(--sw-ink-soft)">{vacio}</p>;
  return (
    <ul className="flex flex-col gap-4">
      {ordenes.map((orden) => (
        <TarjetaOrden key={orden.codigo} orden={orden} />
      ))}
    </ul>
  );
}

export default function RastreoDocumento() {
  const [resultado, setResultado] = useState<OrdenesDeCliente | null>(null);
  const [verHistorial, setVerHistorial] = useState(false);
  const [fallo, setFallo] = useState<Fallo | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const documento = String(form.get("documento") ?? "").trim();
    const correo = String(form.get("correo") ?? "").trim();
    if (!documento || !correo) return;
    setPending(true);
    setFallo(null);
    setResultado(null);
    setVerHistorial(false);

    const response = await consultarPorDocumento(documento, correo).catch(() => null);
    setPending(false);

    if (response?.ok) {
      setResultado((await response.json()) as OrdenesDeCliente);
    } else if (response?.status === 404) {
      const { detail } = await leerErroresApi(response);
      setFallo({
        titulo: "No encontramos pedidos",
        mensaje: detail?.[0] ?? "No encontramos pedidos con esos datos. Revisa tu cédula y el correo que registraste.",
      });
    } else if (response?.status === 429) {
      setFallo({ titulo: "Demasiados intentos", mensaje: "Demasiados intentos. Inténtalo de nuevo más tarde." });
    } else if (response?.status === 400) {
      const errores = await leerErroresApi(response);
      setFallo({ titulo: "Revisa los datos", mensaje: Object.values(errores).flat()[0] ?? "Revisa tu cédula y tu correo." });
    } else {
      setFallo({
        titulo: "No se pudo consultar",
        mensaje: "No pudimos consultar tus pedidos en este momento. Intenta de nuevo en unos minutos.",
      });
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <form onSubmit={onSubmit} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <ClayField label="Cédula">
          <ClayInput name="documento" inputMode="numeric" autoComplete="off" required />
        </ClayField>
        <ClayField label="Correo electrónico (el que registraste con nosotros)">
          <ClayInput name="correo" type="email" autoComplete="email" required />
        </ClayField>
        <div className="sm:col-span-2">
          <ClayButton type="submit" disabled={pending}>
            {pending ? "Consultando..." : "Consultar"}
          </ClayButton>
        </div>
      </form>

      {fallo && <AlertaErrores titulo={fallo.titulo} errores={[fallo.mensaje]} />}

      {resultado && (
        <section aria-label="Tus pedidos" className="flex flex-col gap-4">
          <h2 className="text-sm font-extrabold text-(--sw-ink)">Pedidos activos</h2>
          <ListaOrdenes ordenes={resultado.activas} vacio="No tienes pedidos activos." />
          <div>
            <ClayButton
              type="button"
              variant="secundario"
              onClick={() => setVerHistorial(!verHistorial)}
              aria-expanded={verHistorial}
              aria-controls="historial-ordenes"
            >
              Historial de órdenes
            </ClayButton>
          </div>
          {verHistorial && (
            <div id="historial-ordenes">
              <ListaOrdenes ordenes={resultado.historial} vacio="Aún no tienes órdenes entregadas." />
            </div>
          )}
        </section>
      )}
    </div>
  );
}
