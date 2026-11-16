import { elegido, fechaDesde, texto, type Lector } from "../components/lista/url";

export const ESTADOS_DANO = [
  { valor: "pendiente", etiqueta: "Pendientes de pago" },
  { valor: "pagado", etiqueta: "Pagados" },
] as const;

export function leerFiltrosDanos(params: Lector) {
  return {
    buscar: texto(params.get("buscar")),
    estado: elegido(
      params.get("estado"),
      ESTADOS_DANO.map((e) => e.valor),
    ),
    ...fechaDesde(params),
  };
}
