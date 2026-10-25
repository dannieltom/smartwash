"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { AlertaErrores } from "@/app/catalogo/errores";
import { registrarNovedad, type Orden, type User } from "@/lib/api";
import { ClayButton, ClayCard, ClayField, ClaySelect, ClayTextarea } from "../../components/ui/clay";
import CampoFoto from "../campo-foto";
import { mensajesDeOrden } from "../errores";
import type { FotoLista } from "../foto";

const ESTADOS_CON_PROCESO: Orden["estado"][] = ["En proceso", "Control de calidad"];

export default function RegistrarNovedad({ orden, usuario }: { orden: Orden; usuario: User }) {
  const router = useRouter();
  const [abierto, setAbierto] = useState(false);
  const [prenda, setPrenda] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [foto, setFoto] = useState<FotoLista | null>(null);
  const [errores, setErrores] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  const puede =
    ESTADOS_CON_PROCESO.includes(orden.estado) &&
    (usuario.rol === "administrador" || (usuario.rol === "operario" && orden.operario === usuario.id));
  if (!puede) return null;

  function cancelar() {
    setAbierto(false);
    setPrenda("");
    setDescripcion("");
    setFoto(null);
    setErrores([]);
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!foto) {
      setErrores(["La fotografia es obligatoria."]);
      return;
    }
    setPending(true);
    setErrores([]);
    const response = await registrarNovedad(orden.id, {
      prenda: Number(prenda),
      descripcion: descripcion.trim(),
      foto: foto.dataUrl,
    }).catch(() => null);
    setPending(false);

    if (response?.ok) {
      cancelar();
      router.refresh();
      return;
    }
    setErrores(await mensajesDeOrden(response, "No se pudo registrar la novedad"));
  }

  return (
    <ClayCard className="mb-6">
      <h2 className="text-sm font-bold text-(--sw-ink)">Novedad en una prenda</h2>
      {!abierto ? (
        <>
          <p className="mt-1 text-sm text-(--sw-ink-soft)">
            Si detectas algo relevante en una prenda (mancha, dano, faltante), registralo con una foto. La
            orden queda &quot;Con novedad&quot; hasta que el cliente decida.
          </p>
          <ClayButton type="button" variant="secundario" className="mt-3" onClick={() => setAbierto(true)}>
            Registrar novedad
          </ClayButton>
        </>
      ) : (
        <form onSubmit={onSubmit} className="mt-3 flex flex-col gap-4">
          <ClayField label="Prenda">
            <ClaySelect value={prenda} onChange={(e) => setPrenda(e.target.value)} required>
              <option value="">Selecciona la prenda...</option>
              {orden.detalle_prendas.map((p, indice) => (
                <option key={p.id} value={p.id}>
                  Prenda {indice + 1}: {p.cantidad} × {p.tipo_prenda_nombre}
                  {p.material_nombre ? ` · ${p.material_nombre}` : ""}
                </option>
              ))}
            </ClaySelect>
          </ClayField>
          <ClayField label="Descripcion (obligatoria)">
            <ClayTextarea
              value={descripcion}
              onChange={(e) => setDescripcion(e.target.value)}
              placeholder="Que se encontro y donde"
              className="min-h-20"
              required
            />
          </ClayField>
          <CampoFoto etiqueta="Foto de la novedad" foto={foto} onChange={setFoto} obligatoria />

          <AlertaErrores titulo="No se pudo registrar la novedad" errores={errores} />
          <div className="flex flex-wrap gap-3">
            <ClayButton type="submit" disabled={pending || !foto}>
              {pending ? "Registrando..." : "Registrar novedad"}
            </ClayButton>
            <ClayButton type="button" variant="secundario" onClick={cancelar} disabled={pending}>
              Cancelar
            </ClayButton>
          </div>
        </form>
      )}
    </ClayCard>
  );
}
