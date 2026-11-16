import { elegido, texto, type Lector } from "../components/lista/url";

const ES_FECHA = /^\d{4}-\d{2}-\d{2}$/;

function fecha(valor: string | null) {
  return valor && ES_FECHA.test(valor) ? valor : "";
}

export function leerFiltrosCalificaciones(params: Lector) {
  return {
    buscar: texto(params.get("buscar")),
    estrellas: elegido(params.get("estrellas"), ["1", "2", "3", "4", "5"]),
    desde: fecha(params.get("desde")),
    hasta: fecha(params.get("hasta")),
  };
}
