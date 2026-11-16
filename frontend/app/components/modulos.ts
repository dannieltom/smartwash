import type { Rol } from "@/lib/api";

export type ColorModulo = "blue" | "mint" | "lavender" | "peach";

/** Un modulo del panel: un enlace de la barra y su tarjeta en el inicio. */
export type Modulo = {
  href: string;
  /** Texto corto de la barra. */
  etiqueta: string;
  titulo: string;
  texto: string;
  color: ColorModulo;
  roles: Rol[];
};

// La barra y las tarjetas del inicio salen de esta lista, en este orden: asi no se desfasan.
export const MODULOS: Modulo[] = [
  {
    href: "/clientes",
    etiqueta: "Clientes",
    titulo: "Clientes",
    texto: "Registra y edita los datos de tus clientes.",
    color: "blue",
    roles: ["administrador", "recepcionista"],
  },
  {
    href: "/usuarios",
    etiqueta: "Usuarios",
    titulo: "Usuarios",
    texto: "Crea, edita y desactiva cuentas internas.",
    color: "lavender",
    roles: ["administrador"],
  },
  {
    href: "/catalogo",
    etiqueta: "Catalogo",
    titulo: "Catalogo",
    texto: "Servicios y tarifas por tipo de prenda.",
    color: "mint",
    roles: ["administrador", "recepcionista"],
  },
  {
    href: "/fidelizacion",
    etiqueta: "Fidelizacion",
    titulo: "Fidelizacion",
    texto: "Reglas de descuento para tus clientes.",
    color: "peach",
    roles: ["administrador"],
  },
  {
    href: "/ordenes/bandeja",
    etiqueta: "Mi bandeja",
    titulo: "Mi bandeja",
    texto: "Las ordenes que tienes asignadas y aun no se entregan.",
    color: "mint",
    roles: ["operario"],
  },
  {
    href: "/ordenes",
    etiqueta: "Ordenes",
    titulo: "Ordenes",
    texto: "Sigue el estado de las ordenes en curso.",
    color: "blue",
    roles: ["administrador", "recepcionista", "operario"],
  },
  {
    href: "/ordenes/alertas",
    etiqueta: "Alertas",
    titulo: "Alertas",
    texto: "Ordenes retrasadas y proximas a su fecha estimada de entrega.",
    color: "peach",
    roles: ["administrador", "recepcionista", "operario"],
  },
  {
    href: "/ordenes/novedades",
    etiqueta: "Novedades",
    titulo: "Novedades",
    texto: "Ordenes detenidas hasta que el cliente decida que hacer con la novedad.",
    color: "lavender",
    roles: ["administrador", "recepcionista"],
  },
  {
    href: "/danos",
    etiqueta: "Danos",
    titulo: "Daños",
    texto: "Prendas que la lavanderia daño o perdio, y su pago al cliente.",
    color: "peach",
    roles: ["administrador", "recepcionista"],
  },
  {
    href: "/ordenes/descuentos",
    etiqueta: "Descuentos",
    titulo: "Descuentos",
    texto: "Lo que se descuenta cuando una prenda sale con novedad en la entrega.",
    color: "mint",
    roles: ["administrador"],
  },
  {
    href: "/trazabilidad",
    etiqueta: "Trazabilidad",
    titulo: "Trazabilidad",
    texto: "Seguimiento a las acciones de todos los usuarios, por tipo.",
    color: "lavender",
    roles: ["administrador"],
  },
  {
    href: "/trazabilidad/actividad",
    etiqueta: "Actividad",
    titulo: "Actividad de operarios",
    texto: "Que orden trabajaba cada operario en un rango de horas, y sus turnos.",
    color: "blue",
    roles: ["administrador"],
  },
  {
    href: "/calificaciones",
    etiqueta: "Calificaciones",
    titulo: "Calificaciones",
    texto: "Que tan satisfechos quedan los clientes: promedio y comentarios por orden.",
    color: "mint",
    roles: ["administrador", "recepcionista"],
  },
];

export function modulosDe(rol: Rol): Modulo[] {
  return MODULOS.filter((modulo) => modulo.roles.includes(rol));
}
