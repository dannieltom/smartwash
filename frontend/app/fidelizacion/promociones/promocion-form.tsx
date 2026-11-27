"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import {
  SEGMENTOS_PROMOCION,
  crearPromocion,
  leerErroresApi,
  type ErroresApi,
  type Promocion,
  type PromocionFormulario,
} from "@/lib/api";
import { cx } from "@/lib/cx";
import { ClayButton, ClayField, ClayInput, ClaySelect, ClayTextarea } from "../../components/ui/clay";
import { estadoDeVigencia, hoyEnColombia } from "./vigencia";

// Topes del backend: el porcentaje no pasa de 100 y DecimalField(10, 2) admite 8 enteros.
const VALOR_MAXIMO: Record<Promocion["tipo"], number> = { porcentaje: 100, monto_fijo: 99999999.99 };

const CAMPOS_DEL_FORMULARIO = ["nombre", "descripcion", "tipo", "valor", "segmentos", "vigente_desde", "vigente_hasta"];

type Borrador = {
  nombre: string;
  descripcion: string;
  tipo: Promocion["tipo"];
  valor: string;
  segmentos: Promocion["segmentos"];
  vigente_desde: string;
  vigente_hasta: string;
};

const vacio = (): Borrador => ({
  nombre: "",
  descripcion: "",
  tipo: "porcentaje",
  valor: "",
  segmentos: [],
  vigente_desde: "",
  vigente_hasta: "",
});

function validar(b: Borrador): ErroresApi {
  const errores: ErroresApi = {};
  const agregar = (campo: string, mensaje: string) => (errores[campo] = [...(errores[campo] ?? []), mensaje]);
  const valor = Number(b.valor);

  if (b.nombre.trim() === "") agregar("nombre", "Escribe el nombre de la promocion.");
  if (b.valor === "" || Number.isNaN(valor) || valor <= 0) agregar("valor", "Ingresa un valor mayor que 0.");
  else if (valor > VALOR_MAXIMO[b.tipo]) {
    agregar("valor", b.tipo === "porcentaje" ? "Un porcentaje no puede superar el 100 %." : "El valor es demasiado grande.");
  }
  if (b.vigente_desde === "") agregar("vigente_desde", "Indica la fecha de inicio.");
  if (b.vigente_hasta === "") agregar("vigente_hasta", "Indica la fecha de fin.");
  if (b.vigente_desde && b.vigente_hasta && b.vigente_hasta < b.vigente_desde) {
    agregar("vigente_hasta", "La vigencia no puede terminar antes de la fecha de inicio.");
  }
  if (b.segmentos.length === 0) agregar("segmentos", "Asigna la promocion al menos a un segmento de clientes.");
  return errores;
}

function Errores({ lista }: { lista?: string[] }) {
  if (!lista?.length) return null;
  return (
    <span role="alert" className="text-xs font-semibold text-(--sw-coral)">
      {lista.join(" ")}
    </span>
  );
}

function Campo({ etiqueta, errores, children }: { etiqueta: string; errores?: string[]; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <ClayField label={etiqueta}>{children}</ClayField>
      <Errores lista={errores} />
    </div>
  );
}

export default function PromocionForm({ className }: { className?: string }) {
  const router = useRouter();
  const [borrador, setBorrador] = useState<Borrador>(vacio);
  const [errores, setErrores] = useState<ErroresApi>({});
  const [creada, setCreada] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const cambiar = (cambios: Partial<Borrador>) => {
    setBorrador((actual) => ({ ...actual, ...cambios }));
    setCreada(null);
  };

  const hoy = hoyEnColombia();
  const vigenciaCompleta = borrador.vigente_desde !== "" && borrador.vigente_hasta >= borrador.vigente_desde;
  const estadoPrevisto = vigenciaCompleta
    ? estadoDeVigencia(borrador.vigente_desde, borrador.vigente_hasta, hoy)
    : null;

  function alternarSegmento(segmento: Promocion["segmentos"][number]) {
    const elegidos = borrador.segmentos.includes(segmento)
      ? borrador.segmentos.filter((s) => s !== segmento)
      : [...borrador.segmentos, segmento];
    cambiar({ segmentos: elegidos });
  }

  function cancelar() {
    setBorrador(vacio());
    setErrores({});
    setCreada(null);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const locales = validar(borrador);
    setErrores(locales);
    if (Object.keys(locales).length > 0) return;

    setPending(true);
    const datos: PromocionFormulario = {
      nombre: borrador.nombre.trim(),
      descripcion: borrador.descripcion.trim(),
      tipo: borrador.tipo,
      valor: borrador.valor,
      segmentos: borrador.segmentos,
      activa: true,
      vigente_desde: borrador.vigente_desde,
      vigente_hasta: borrador.vigente_hasta,
    };
    const response = await crearPromocion(datos).catch(() => null);
    setPending(false);

    if (response?.ok) {
      setBorrador(vacio());
      setErrores({});
      setCreada(datos.nombre);
      router.refresh();
      return;
    }
    if (response?.status === 401) {
      router.push("/login");
      return;
    }
    if (!response) {
      setErrores({ general: ["No se pudo conectar con el servidor. Intenta de nuevo."] });
      return;
    }
    const delServidor = await leerErroresApi(response);
    if (response.status === 403) {
      setErrores({ general: ["No tienes permiso para crear promociones."] });
    } else if (Object.keys(delServidor).length === 0) {
      setErrores({ general: [`No se pudo crear la promocion (error ${response.status}).`] });
    } else {
      setErrores(delServidor);
    }
  }

  const sueltos = Object.entries(errores)
    .filter(([campo]) => !CAMPOS_DEL_FORMULARIO.includes(campo))
    .flatMap(([, lista]) => lista);

  return (
    <form onSubmit={onSubmit} noValidate className={cx("grid grid-cols-1 gap-4 sm:grid-cols-2", className)}>
      <Campo etiqueta="Nombre de la campaña" errores={errores.nombre}>
        <ClayInput
          value={borrador.nombre}
          onChange={(e) => cambiar({ nombre: e.target.value })}
          maxLength={120}
          placeholder="Descuento Lavado en Seco Noviembre"
          aria-invalid={Boolean(errores.nombre)}
        />
      </Campo>
      <Campo etiqueta="Descripcion o condiciones (opcional)" errores={errores.descripcion}>
        <ClayTextarea
          value={borrador.descripcion}
          onChange={(e) => cambiar({ descripcion: e.target.value })}
          maxLength={255}
          className="min-h-11"
        />
      </Campo>
      <Campo etiqueta="Tipo de beneficio" errores={errores.tipo}>
        <ClaySelect value={borrador.tipo} onChange={(e) => cambiar({ tipo: e.target.value as Promocion["tipo"] })}>
          <option value="porcentaje">Porcentaje</option>
          <option value="monto_fijo">Monto fijo</option>
        </ClaySelect>
      </Campo>
      <Campo etiqueta={borrador.tipo === "porcentaje" ? "Valor (%)" : "Valor (COP)"} errores={errores.valor}>
        <ClayInput
          type="number"
          min="0"
          max={VALOR_MAXIMO[borrador.tipo]}
          step="0.01"
          value={borrador.valor}
          onChange={(e) => cambiar({ valor: e.target.value })}
          aria-invalid={Boolean(errores.valor)}
        />
      </Campo>
      <Campo etiqueta="Fecha de inicio" errores={errores.vigente_desde}>
        <ClayInput
          type="date"
          value={borrador.vigente_desde}
          onChange={(e) => cambiar({ vigente_desde: e.target.value })}
          aria-invalid={Boolean(errores.vigente_desde)}
        />
      </Campo>
      <Campo etiqueta="Fecha de fin (inclusiva)" errores={errores.vigente_hasta}>
        <ClayInput
          type="date"
          min={borrador.vigente_desde || undefined}
          value={borrador.vigente_hasta}
          onChange={(e) => cambiar({ vigente_hasta: e.target.value })}
          aria-invalid={Boolean(errores.vigente_hasta)}
        />
      </Campo>

      {estadoPrevisto && (
        <p className="text-sm text-(--sw-ink-soft) sm:col-span-2">
          {estadoPrevisto === "Programada" && "Empieza mas adelante: quedara Programada hasta su fecha de inicio."}
          {estadoPrevisto === "Activa" && "Vigente desde hoy: quedara Activa apenas se cree."}
          {estadoPrevisto === "Vencida" && "Ya termino: la promocion se guardaria como Vencida y no aplicara a ninguna orden."}
        </p>
      )}

      <fieldset className="sm:col-span-2">
        <legend className="text-sm font-bold text-(--sw-ink-soft)">Segmentos de clientes</legend>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-2 accent-(--sw-accent)">
          {SEGMENTOS_PROMOCION.map((segmento) => (
            <label key={segmento} className="flex min-h-11 items-center gap-2 text-sm font-semibold text-(--sw-ink)">
              <input
                type="checkbox"
                className="size-4"
                checked={borrador.segmentos.includes(segmento)}
                onChange={() => alternarSegmento(segmento)}
              />
              {segmento}
            </label>
          ))}
          <ClayButton
            type="button"
            variant="secundario"
            onClick={() => cambiar({ segmentos: [...SEGMENTOS_PROMOCION] })}
          >
            Todos los clientes
          </ClayButton>
        </div>
        <Errores lista={errores.segmentos} />
      </fieldset>

      {sueltos.length > 0 && (
        <div role="alert" className="clay-sm border-l-8 border-l-(--sw-coral) p-4 text-sm sm:col-span-2">
          <p className="font-semibold text-(--sw-ink)">No se pudo crear la promocion</p>
          <ul className="mt-1 list-inside list-disc text-(--sw-ink-soft)">
            {sueltos.map((mensaje) => (
              <li key={mensaje}>{mensaje}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
        <ClayButton type="submit" disabled={pending}>
          {pending ? "Guardando..." : "Crear promocion"}
        </ClayButton>
        <ClayButton type="button" variant="secundario" onClick={cancelar} disabled={pending}>
          Cancelar
        </ClayButton>
        {creada && (
          <p role="status" className="text-sm font-semibold text-(--sw-ink)">
            Promocion &quot;{creada}&quot; creada.
          </p>
        )}
      </div>
    </form>
  );
}
