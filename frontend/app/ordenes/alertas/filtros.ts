import { texto, type Lector } from "../../components/lista/url";

export function leerFiltrosAlertas(params: Lector) {
  return { buscar: texto(params.get("buscar")) };
}
