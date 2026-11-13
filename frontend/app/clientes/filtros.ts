import type { Cliente } from "@/lib/api";
import { elegido, texto, type Lector } from "../components/lista/url";

export const CLASIFICACIONES: Cliente["clasificacion"][] = ["Ocasional", "Frecuente", "VIP"];

export function leerFiltrosClientes(params: Lector) {
  return { buscar: texto(params.get("buscar")), clasificacion: elegido(params.get("clasificacion"), CLASIFICACIONES) };
}
