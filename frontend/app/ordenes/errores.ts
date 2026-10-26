const ETIQUETAS: Record<string, string> = {
  cliente: "Cliente",
  prendas: "Prendas",
  tipo_prenda: "Tipo de prenda",
  cantidad: "Cantidad",
  peso: "Peso",
  talla: "Talla",
  genero: "Genero",
  color: "Color",
  estado_inicial: "Estado al recibir",
  servicios: "Servicios",
  servicio: "Servicio",
  observacion: "Observacion",
  estado: "Estado",
  monto: "Monto",
  metodo: "Metodo de pago",
  operario: "Operario",
  resultado: "Resultado",
  foto: "Foto",
  valor_declarado: "Valor de la prenda",
  decision: "Decision",
  gravedades: "Gravedad",
};

const SIN_ETIQUETA = new Set(["non_field_errors", "detail"]);

function prenda(indice: number, ruta: string[], nombres: string[]): string[] {
  return [...ruta.filter((r) => r !== ETIQUETAS.prendas), nombres[indice] ?? `Prenda ${indice + 1}`];
}

// DRF anida los errores de cada prenda por su posicion, como lista o como
// objeto con indices: {"prendas": {"0": {"peso": ["..."]}}}. leerErroresApi
// solo aplana un nivel, por eso aqui se recorre todo el arbol.
function aplanar(valor: unknown, ruta: string[], nombres: string[]): string[] {
  if (typeof valor === "string") {
    const prefijo = ruta.filter(Boolean).join(" · ");
    return [prefijo ? `${prefijo}: ${valor}` : valor];
  }
  if (Array.isArray(valor)) {
    return valor.flatMap((item, indice) =>
      item && typeof item === "object" && !Array.isArray(item)
        ? aplanar(item, prenda(indice, ruta, nombres), nombres)
        : aplanar(item, ruta, nombres),
    );
  }
  if (valor && typeof valor === "object") {
    return Object.entries(valor).flatMap(([campo, hijo]) => {
      if (/^\d+$/.test(campo)) return aplanar(hijo, prenda(Number(campo), ruta, nombres), nombres);
      return aplanar(hijo, [...ruta, SIN_ETIQUETA.has(campo) ? "" : (ETIQUETAS[campo] ?? campo)], nombres);
    });
  }
  return [];
}

export async function mensajesDeOrden(response: Response | null, porDefecto: string, nombres: string[] = []): Promise<string[]> {
  if (!response) return ["No se pudo conectar con el servidor. Intenta de nuevo."];
  const data: unknown = await response.json().catch(() => null);
  const mensajes = aplanar(data, [], nombres);
  return mensajes.length ? mensajes : [`${porDefecto} (error ${response.status}).`];
}
