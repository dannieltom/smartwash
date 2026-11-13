"use client";

import { useState } from "react";

import { ClayField, ClayInput } from "../ui/clay";

function normalizar(texto: string) {
  return texto
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

/** Para listas pequenas que ya estan cargadas: filtra en el navegador, sin paginar. Cada palabra
 * escrita debe aparecer en alguno de los textos de la fila. */
export function useFiltroLocal<T>(filas: T[], textos: (fila: T) => string[]) {
  const [texto, setTexto] = useState("");
  const palabras = normalizar(texto).split(/\s+/).filter(Boolean);
  const filtradas = palabras.length
    ? filas.filter((fila) => {
        const contenido = normalizar(textos(fila).join(" "));
        return palabras.every((p) => contenido.includes(p));
      })
    : filas;
  return { texto, setTexto, filtradas, filtrando: palabras.length > 0 };
}

export function BuscadorLocal({
  etiqueta,
  texto,
  onCambiar,
}: {
  etiqueta: string;
  texto: string;
  onCambiar: (texto: string) => void;
}) {
  return (
    <div className="mb-3 max-w-sm">
      <ClayField label={etiqueta}>
        <ClayInput type="search" value={texto} onChange={(e) => onCambiar(e.target.value)} autoComplete="off" />
      </ClayField>
    </div>
  );
}
