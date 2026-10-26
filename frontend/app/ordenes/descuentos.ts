import type { ConfiguracionDescuentos, Gravedad, PrendaDeOrden } from "@/lib/api";

export const GRAVEDADES: { valor: Gravedad; etiqueta: string }[] = [
  { valor: "leve", etiqueta: "Leve" },
  { valor: "moderada", etiqueta: "Moderada" },
  { valor: "notoria", etiqueta: "Notoria" },
];

export function valorDePrenda(prenda: PrendaDeOrden): number {
  return prenda.servicios.reduce((suma, s) => suma + Number(s.valor_aplicado), 0);
}

export function porcentajePara(gravedad: Gravedad, configuracion: ConfiguracionDescuentos): number {
  return Number(configuracion[`porcentaje_${gravedad}`]);
}

const redondearA100 = (valor: number) => Math.round(valor / 100) * 100;

/** La misma cuenta que ConfiguracionDescuentoNovedad.monto_descuento en el
 * backend; aqui solo sirve de vista previa: el monto real lo fija el servidor. */
export function montoDescuento(
  valorPrenda: number,
  porcentaje: number,
  yaDescontado: number,
  configuracion: ConfiguracionDescuentos,
): number {
  const monto = Math.max(redondearA100((valorPrenda * porcentaje) / 100), Number(configuracion.monto_minimo));
  const tope = redondearA100((valorPrenda * Number(configuracion.tope_porcentaje)) / 100);
  return Math.max(Math.min(monto, tope - yaDescontado), 0);
}
