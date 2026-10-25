// El backend rechaza fotos de mas de 500 KB (512 000 bytes decodificados). Se
// apunta un poco por debajo para no quedar justo en el borde.
const LIMITE_BYTES = 500 * 1024;
const OBJETIVO_BYTES = 480 * 1000;
const TIPOS = ["image/jpeg", "image/png", "image/webp"];

export type FotoLista = { dataUrl: string; bytes: number; bytesOriginales: number };

/** Bytes de la imagen una vez decodificado el base64 de un data URL. */
export function bytesDeDataUrl(dataUrl: string): number {
  const base64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
  const relleno = base64.endsWith("==") ? 2 : base64.endsWith("=") ? 1 : 0;
  return Math.floor((base64.length * 3) / 4) - relleno;
}

function leerComoDataUrl(archivo: File): Promise<string> {
  return new Promise((resolver, rechazar) => {
    const lector = new FileReader();
    lector.onload = () => resolver(String(lector.result));
    lector.onerror = () => rechazar(new Error("No se pudo leer el archivo."));
    lector.readAsDataURL(archivo);
  });
}

function cargarImagen(src: string): Promise<HTMLImageElement> {
  return new Promise((resolver, rechazar) => {
    const imagen = new Image();
    imagen.onload = () => resolver(imagen);
    imagen.onerror = () => rechazar(new Error("El archivo no es una imagen valida."));
    imagen.src = src;
  });
}

/** Devuelve la foto lista para enviar: tal cual si ya pesa 500 KB o menos, o
 * reducida a JPEG (bajando calidad y luego tamano) hasta quedar por debajo. */
export async function prepararFoto(archivo: File): Promise<FotoLista> {
  if (!TIPOS.includes(archivo.type)) {
    throw new Error("El archivo no es una imagen JPEG, PNG o WebP.");
  }
  const original = await leerComoDataUrl(archivo);
  if (archivo.size <= LIMITE_BYTES) {
    return { dataUrl: original, bytes: archivo.size, bytesOriginales: archivo.size };
  }

  const imagen = await cargarImagen(original);
  const lienzo = document.createElement("canvas");
  const contexto = lienzo.getContext("2d");
  if (!contexto) throw new Error("El navegador no permite procesar la imagen.");

  let escala = Math.min(1, 1600 / Math.max(imagen.naturalWidth, imagen.naturalHeight));
  for (let intento = 0; intento < 8; intento += 1) {
    lienzo.width = Math.max(1, Math.round(imagen.naturalWidth * escala));
    lienzo.height = Math.max(1, Math.round(imagen.naturalHeight * escala));
    // Fondo blanco: un PNG transparente pasado a JPEG quedaria negro.
    contexto.fillStyle = "#fff";
    contexto.fillRect(0, 0, lienzo.width, lienzo.height);
    contexto.drawImage(imagen, 0, 0, lienzo.width, lienzo.height);
    for (const calidad of [0.85, 0.7, 0.55, 0.4]) {
      const dataUrl = lienzo.toDataURL("image/jpeg", calidad);
      const bytes = bytesDeDataUrl(dataUrl);
      if (bytes <= OBJETIVO_BYTES) return { dataUrl, bytes, bytesOriginales: archivo.size };
    }
    escala *= 0.75;
  }
  throw new Error("No se pudo reducir la foto a 500 KB. Intenta con otra imagen.");
}

export function formatKB(bytes: number): string {
  return `${Math.round(bytes / 1024)} KB`;
}
