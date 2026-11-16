import type { Rol } from "@/lib/api";
import { elegido, texto, type Lector } from "../components/lista/url";

export const ROLES: { valor: Rol; etiqueta: string }[] = [
  { valor: "administrador", etiqueta: "Administrador" },
  { valor: "recepcionista", etiqueta: "Recepcionista" },
  { valor: "operario", etiqueta: "Operario" },
];

export function leerFiltrosUsuarios(params: Lector) {
  return {
    buscar: texto(params.get("buscar")),
    rol: elegido(
      params.get("rol"),
      ROLES.map((r) => r.valor),
    ),
    activo: elegido(params.get("activo"), ["true", "false"]),
  };
}
