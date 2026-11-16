"use client";

import { useEffect, useRef, useState } from "react";

import { ClayField, ClayInput } from "../ui/clay";

const RETRASO_MS = 300;

/** Busca un momento despues de dejar de escribir, sin recargar la pagina. */
export default function Buscador({
  etiqueta,
  placeholder,
  valor,
  onBuscar,
}: {
  etiqueta: string;
  placeholder: string;
  /** El texto que trae la URL. */
  valor: string;
  onBuscar: (texto: string) => void;
}) {
  const [texto, setTexto] = useState(valor);
  const [valorPrevio, setValorPrevio] = useState(valor);
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Al volver atras o limpiar, la URL trae otro texto: el campo lo adopta.
  if (valor !== valorPrevio) {
    setValorPrevio(valor);
    setTexto(valor);
  }

  useEffect(
    () => () => {
      if (temporizador.current) clearTimeout(temporizador.current);
    },
    [],
  );

  function escribir(nuevo: string) {
    setTexto(nuevo);
    if (temporizador.current) clearTimeout(temporizador.current);
    temporizador.current = setTimeout(() => {
      setValorPrevio(nuevo);
      onBuscar(nuevo);
    }, RETRASO_MS);
  }

  return (
    <ClayField label={etiqueta}>
      <ClayInput
        type="search"
        value={texto}
        onChange={(e) => escribir(e.target.value)}
        placeholder={placeholder}
        autoComplete="off"
      />
    </ClayField>
  );
}
