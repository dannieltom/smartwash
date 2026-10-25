"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { AlertaErrores } from "@/app/catalogo/errores";
import { cambiarEstadoOrden, type EstadoOrden, type Orden, type User } from "@/lib/api";
import { ClayButton, ClayCard } from "../../components/ui/clay";
import { mensajesDeOrden } from "../errores";

type Paso = {
  destino: EstadoOrden;
  accion: string;
  responsable: "recepcion" | "operario";
  reproceso?: boolean;
};

// Mismo flujo que Orden.TRANSICIONES en el backend, que es quien decide; aqui
// solo se ofrecen los pasos que tienen sentido para quien mira la orden.
const PASOS: Partial<Record<EstadoOrden, Paso[]>> = {
  Recibida: [{ destino: "Clasificada", accion: "Clasificar", responsable: "recepcion" }],
  Clasificada: [{ destino: "En proceso", accion: "Iniciar proceso", responsable: "operario" }],
  "En proceso": [
    { destino: "Control de calidad", accion: "Enviar a control de calidad", responsable: "operario" },
  ],
  "Control de calidad": [
    { destino: "Lista para entrega", accion: "Aprobar: lista para entrega", responsable: "operario" },
    { destino: "En proceso", accion: "No aprueba: reprocesar", responsable: "operario", reproceso: true },
  ],
};

function puedeHacer(paso: Paso, orden: Orden, usuario: User): boolean {
  if (usuario.rol === "administrador") return true;
  if (paso.responsable === "recepcion") return usuario.rol === "recepcionista";
  return usuario.rol === "operario" && orden.operario === usuario.id;
}

export default function CambiarEstado({ orden, usuario }: { orden: Orden; usuario: User }) {
  const router = useRouter();
  const [elegido, setElegido] = useState<Paso | null>(null);
  const [errores, setErrores] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  if (orden.estado === "Con novedad") {
    return (
      <ClayCard className="mb-6">
        <p className="text-sm text-(--sw-ink-soft)">
          La orden tiene una novedad registrada: no se puede avanzar hasta que se registre la decision del
          cliente.
        </p>
      </ClayCard>
    );
  }

  if (orden.estado === "En espera") {
    return (
      <ClayCard className="mb-6">
        <p className="text-sm text-(--sw-ink-soft)">
          La orden esta &quot;En espera&quot;: no se puede clasificar, asignar ni avanzar hasta que se
          registre el abono minimo.
        </p>
      </ClayCard>
    );
  }

  const pasos = PASOS[orden.estado] ?? [];
  const disponibles = pasos.filter((paso) => puedeHacer(paso, orden, usuario));
  if (pasos.length === 0) return null;

  if (disponibles.length === 0) {
    const ajena = usuario.rol === "operario" && orden.operario !== usuario.id;
    return (
      <ClayCard className="mb-6">
        <p className="text-sm text-(--sw-ink-soft)">
          {ajena
            ? "Esta orden no esta asignada a ti: solo su operario puede cambiar el estado."
            : `El siguiente paso de una orden "${orden.estado}" lo hace otro rol.`}
        </p>
      </ClayCard>
    );
  }

  function cancelar() {
    setElegido(null);
    setErrores([]);
  }

  async function confirmar() {
    if (!elegido) return;
    setPending(true);
    setErrores([]);
    const response = await cambiarEstadoOrden(orden.id, elegido.destino).catch(() => null);
    setPending(false);

    if (response?.ok) {
      setElegido(null);
      router.refresh();
      return;
    }
    setErrores(await mensajesDeOrden(response, "No se pudo cambiar el estado"));
  }

  return (
    <ClayCard className="mb-6">
      <h2 className="text-sm font-bold text-(--sw-ink)">Avanzar la orden</h2>

      {!elegido ? (
        <div className="mt-3 flex flex-wrap gap-3">
          {disponibles.map((paso) => (
            <ClayButton
              key={paso.destino}
              type="button"
              variant={paso.reproceso ? "secundario" : "primario"}
              onClick={() => setElegido(paso)}
            >
              {paso.accion}
            </ClayButton>
          ))}
        </div>
      ) : (
        <div className="mt-3 flex flex-col gap-3">
          <p className="text-sm text-(--sw-ink)">
            La orden pasara de <strong>{orden.estado}</strong> a <strong>{elegido.destino}</strong>.
            {elegido.reproceso && " El reproceso no tiene costo para el cliente."}
          </p>
          <div className="flex flex-wrap gap-3">
            <ClayButton type="button" onClick={confirmar} disabled={pending}>
              {pending ? "Guardando..." : "Confirmar"}
            </ClayButton>
            <ClayButton type="button" variant="secundario" onClick={cancelar} disabled={pending}>
              Cancelar
            </ClayButton>
          </div>
        </div>
      )}

      <div className="mt-3">
        <AlertaErrores titulo="No se pudo cambiar el estado" errores={errores} />
      </div>
    </ClayCard>
  );
}
