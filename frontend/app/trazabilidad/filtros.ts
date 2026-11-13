import { elegido, fechaDesde, texto, type Lector } from "../components/lista/url";
import { TIPOS_USUARIO } from "./tipos";

export function leerFiltrosTrazabilidad(params: Lector) {
  return {
    buscar: texto(params.get("buscar")),
    rol: elegido(
      params.get("rol"),
      TIPOS_USUARIO.map((t) => t.valor),
    ),
    ...fechaDesde(params),
  };
}
