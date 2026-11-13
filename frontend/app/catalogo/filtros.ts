import { elegido, texto, type Lector } from "../components/lista/url";

export function leerFiltrosTarifas(params: Lector) {
  return { buscar: texto(params.get("buscar")), vigentes: elegido(params.get("vigentes"), ["1"]) };
}
