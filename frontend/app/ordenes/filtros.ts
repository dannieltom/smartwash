import type { EstadoOrden } from "@/lib/api";
import { elegido, fechaDesde, texto, type Lector } from "../components/lista/url";

export const ESTADOS: EstadoOrden[] = [
  "En espera",
  "Recibida",
  "Clasificada",
  "En proceso",
  "Control de calidad",
  "Con novedad",
  "Lista para entrega",
  "Entregada",
  "Cancelada",
];

/** Lee los filtros de la URL descartando lo invalido, para no pedirle al backend algo que rechaza con 400. */
export function leerFiltrosOrdenes(params: Lector) {
  return { buscar: texto(params.get("buscar")), estado: elegido(params.get("estado"), ESTADOS), ...fechaDesde(params) };
}
