import type { DecisionNovedad, Gravedad } from "@/lib/api";
import { elegido, fechaDesde, texto, type Lector } from "../../components/lista/url";
import { DECISION } from "../[id]/novedades-orden";

export const ORIGENES = [
  { valor: "proceso", etiqueta: "Durante el proceso" },
  { valor: "entrega", etiqueta: "En la entrega" },
] as const;

export const GRAVEDADES: { valor: Gravedad; etiqueta: string }[] = [
  { valor: "leve", etiqueta: "Leve" },
  { valor: "moderada", etiqueta: "Moderada" },
  { valor: "notoria", etiqueta: "Notoria" },
];

export const DECISIONES = Object.entries(DECISION) as [DecisionNovedad, string][];

/** `vista` viaja con los filtros para que la URL conserve la pestana; el backend la ignora. */
export function leerFiltrosHistorial(params: Lector) {
  return {
    vista: "historial",
    buscar: texto(params.get("buscar")),
    estado: elegido(params.get("estado"), ["pendiente", "resuelta"]),
    origen: elegido(
      params.get("origen"),
      ORIGENES.map((o) => o.valor),
    ),
    decision: elegido(
      params.get("decision"),
      DECISIONES.map(([valor]) => valor),
    ),
    gravedad: elegido(
      params.get("gravedad"),
      GRAVEDADES.map((g) => g.valor),
    ),
    ...fechaDesde(params),
  };
}
