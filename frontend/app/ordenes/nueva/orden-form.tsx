"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AlertaErrores } from "@/app/catalogo/errores";
import { crearOrden, type Cliente, type Material, type Orden, type Servicio, type Tarifa, type TipoPrenda } from "@/lib/api";
import { formatCOP } from "@/lib/format";
import { ClayButton, ClayCard } from "../../components/ui/clay";
import { aFormularios, erroresDeServicios, lineaVacia, nombresDeUnidades, subtotalEstimado, type LineaEditable } from "../cotizacion";
import { mensajesDeOrden } from "../errores";
import LineaPrenda from "../linea-prenda";
import SelectorCliente from "./selector-cliente";

export default function OrdenForm({
  tiposPrenda,
  materiales,
  servicios,
  tarifas,
}: {
  tiposPrenda: TipoPrenda[];
  materiales: Material[];
  servicios: Servicio[];
  tarifas: Tarifa[];
}) {
  const router = useRouter();
  const [cliente, setCliente] = useState<Cliente | null>(null);
  const [lineas, setLineas] = useState<LineaEditable[]>(() => [lineaVacia()]);
  const [errores, setErrores] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  const subtotal = lineas.reduce((total, linea) => total + subtotalEstimado(linea, tarifas, materiales), 0);

  function actualizarLinea(clave: number, linea: LineaEditable) {
    setLineas((actuales) => actuales.map((l) => (l.clave === clave ? linea : l)));
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (cliente === null) {
      setErrores(["Elige el cliente de la lista."]);
      return;
    }
    const faltantes = erroresDeServicios(lineas, tiposPrenda);
    if (faltantes.length > 0) {
      setErrores(faltantes);
      return;
    }
    setPending(true);
    setErrores([]);

    const response = await crearOrden(cliente.id, lineas.flatMap(aFormularios)).catch(() => null);

    if (response?.ok) {
      const orden = (await response.json()) as Orden;
      router.push(`/ordenes/${orden.id}?registrada=1`);
      return;
    }
    setPending(false);
    setErrores(await mensajesDeOrden(response, "No se pudo registrar la orden", nombresDeUnidades(lineas, tiposPrenda)));
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-6">
      <ClayCard>
        <SelectorCliente onElegir={setCliente} />
        <p className="mt-2 text-xs text-(--sw-ink-soft)">
          Si el cliente no aparece, registralo primero en Clientes.
        </p>
      </ClayCard>

      {lineas.length === 0 ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">La orden no tiene prendas.</p>
        </ClayCard>
      ) : (
        lineas.map((linea, indice) => (
          <LineaPrenda
            key={linea.clave}
            titulo={`Prenda ${indice + 1}`}
            linea={linea}
            tiposPrenda={tiposPrenda}
            materiales={materiales}
            servicios={servicios}
            tarifas={tarifas}
            onChange={(nueva) => actualizarLinea(linea.clave, nueva)}
            onQuitar={() => setLineas((actuales) => actuales.filter((l) => l.clave !== linea.clave))}
          />
        ))
      )}

      <div>
        <ClayButton type="button" variant="secundario" onClick={() => setLineas((a) => [...a, lineaVacia()])}>
          + Agregar otra prenda
        </ClayButton>
      </div>

      <ClayCard>
        <p className="text-sm text-(--sw-ink-soft)">
          Total estimado:{" "}
          <span className="text-lg font-bold text-(--sw-ink) tabular-nums">{formatCOP(subtotal)}</span>
        </p>
        <p className="mt-1 text-xs text-(--sw-ink-soft)">
          El precio de cada servicio depende del peso y del material de la prenda. Al registrar, el sistema aplica el descuento de fidelizacion que corresponda y calcula el
          total, el abono requerido (30 %) y la duracion estimada. La orden queda &quot;En espera&quot;
          hasta que se registre el abono.
        </p>
      </ClayCard>

      <AlertaErrores titulo="No se pudo registrar la orden" errores={errores} />

      <div className="flex flex-wrap gap-3">
        <ClayButton type="submit" disabled={pending}>
          {pending ? "Registrando..." : "Registrar orden"}
        </ClayButton>
        <ClayButton type="button" variant="secundario" disabled={pending} onClick={() => router.push("/ordenes")}>
          Cancelar
        </ClayButton>
      </div>
    </form>
  );
}
