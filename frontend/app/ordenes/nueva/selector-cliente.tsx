"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";

import { buscarPagina, consultaDeLista, type Cliente, type Pagina } from "@/lib/api";
import { ClayField, ClayInput } from "../../components/ui/clay";

const RETRASO_MS = 300;
const SUGERENCIAS = 10;

type Resultados = Cliente[] | "cargando" | "error";

function etiqueta(cliente: Cliente) {
  return `${cliente.nombre_completo} · ${cliente.documento}`;
}

/** Combobox: busca en el servidor mientras se escribe, en vez de descargar todos los clientes. */
export default function SelectorCliente({ onElegir }: { onElegir: (cliente: Cliente | null) => void }) {
  const id = useId();
  const idLista = `${id}-clientes`;
  const [texto, setTexto] = useState("");
  const [abierto, setAbierto] = useState(false);
  const [resultados, setResultados] = useState<Resultados>([]);
  const [activo, setActivo] = useState(-1);
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);
  const ultimaBusqueda = useRef(0);

  useEffect(
    () => () => {
      if (temporizador.current) clearTimeout(temporizador.current);
    },
    [],
  );

  async function buscar(valor: string) {
    const numero = ++ultimaBusqueda.current;
    setResultados("cargando");
    const response = await buscarPagina("/clientes", consultaDeLista({ buscar: valor }, 1, SUGERENCIAS)).catch(() => null);
    const datos = response?.ok ? ((await response.json()) as Pagina<Cliente>) : null;
    // Una respuesta lenta de una busqueda anterior no pisa la ultima.
    if (numero !== ultimaBusqueda.current) return;
    setResultados(datos ? datos.resultados : "error");
    setActivo(datos?.resultados.length ? 0 : -1);
  }

  function escribir(valor: string) {
    setTexto(valor);
    setAbierto(true);
    onElegir(null);
    if (temporizador.current) clearTimeout(temporizador.current);
    temporizador.current = setTimeout(() => buscar(valor), RETRASO_MS);
  }

  function elegir(cliente: Cliente) {
    setTexto(etiqueta(cliente));
    setAbierto(false);
    setActivo(-1);
    onElegir(cliente);
  }

  function abrir() {
    if (abierto) return;
    setAbierto(true);
    buscar(texto.includes(" · ") ? "" : texto);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    const lista = Array.isArray(resultados) ? resultados : [];
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      if (!abierto) return abrir();
      if (lista.length === 0) return;
      const paso = event.key === "ArrowDown" ? 1 : -1;
      setActivo((actual) => (actual + paso + lista.length) % lista.length);
    } else if (event.key === "Enter" && abierto) {
      // Enter elige el cliente resaltado en vez de enviar la orden.
      event.preventDefault();
      if (lista[activo]) elegir(lista[activo]);
    } else if (event.key === "Escape" && abierto) {
      event.preventDefault();
      setAbierto(false);
    }
  }

  const lista = Array.isArray(resultados) ? resultados : [];
  const opcionActiva = abierto && lista[activo] ? `${id}-opcion-${lista[activo].id}` : undefined;

  return (
    <div className="relative">
      <ClayField label="Cliente">
        <ClayInput
          role="combobox"
          aria-expanded={abierto}
          aria-controls={idLista}
          aria-autocomplete="list"
          aria-activedescendant={opcionActiva}
          value={texto}
          onChange={(e) => escribir(e.target.value)}
          onFocus={abrir}
          onClick={abrir}
          onBlur={() => setTimeout(() => setAbierto(false), 150)}
          onKeyDown={onKeyDown}
          placeholder="Busca por nombre, cédula o teléfono"
          autoComplete="off"
        />
      </ClayField>
      {abierto && (
        <ul
          id={idLista}
          role="listbox"
          aria-label="Clientes encontrados"
          className="clay-sm absolute z-20 mt-1 max-h-72 w-full overflow-y-auto bg-(--sw-surface) p-1 text-sm"
        >
          {resultados === "cargando" && <li className="px-3 py-2 text-(--sw-ink-soft)">Buscando...</li>}
          {resultados === "error" && <li className="px-3 py-2 text-(--sw-ink)">No se pudieron cargar los clientes.</li>}
          {Array.isArray(resultados) && resultados.length === 0 && (
            <li className="px-3 py-2 text-(--sw-ink-soft)">Sin resultados</li>
          )}
          {lista.map((cliente, i) => (
            <li
              key={cliente.id}
              id={`${id}-opcion-${cliente.id}`}
              role="option"
              aria-selected={i === activo}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => elegir(cliente)}
              onMouseEnter={() => setActivo(i)}
              className={`cursor-pointer rounded-xl px-3 py-2 ${i === activo ? "bg-(--sw-accent) text-(--sw-ink)" : "text-(--sw-ink)"}`}
            >
              <span className="font-semibold">{cliente.nombre_completo}</span>{" "}
              <span className="text-(--sw-ink-soft)">· {cliente.documento}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
