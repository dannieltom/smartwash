import { cookies } from "next/headers";
import Link from "next/link";

import { getCurrentUser, type Rol } from "@/lib/api";
import { clayBtnClass } from "./ui/clay";
import ActuarComoSelector from "./actuar-como";
import NavMenu, { type Enlace } from "./nav-menu";

// Sin sesion: nav de cara al cliente que entra a la lavanderia, no al panel
// interno. Con sesion: cada rol ve solo sus modulos (T8/SCRUM-57 hace esto
// exigible tambien en el backend; aqui es solo lo que se muestra).
const PUBLICOS: Enlace[] = [
  { href: "/#servicios", label: "Servicios" },
  { href: "/#como-funciona", label: "Como funciona" },
  { href: "/rastrear-pedido", label: "Rastrear pedido" },
  { href: "/pqrs", label: "PQRS" },
];

const POR_ROL: Record<Rol, Enlace[]> = {
  administrador: [
    { href: "/clientes", label: "Clientes" },
    { href: "/usuarios", label: "Usuarios" },
    { href: "/catalogo", label: "Catalogo" },
    { href: "/fidelizacion", label: "Fidelizacion" },
    { href: "/ordenes", label: "Ordenes" },
    { href: "/ordenes/alertas", label: "Alertas" },
    { href: "/trazabilidad", label: "Trazabilidad" },
  ],
  recepcionista: [
    { href: "/clientes", label: "Clientes" },
    { href: "/catalogo", label: "Catalogo" },
    { href: "/ordenes", label: "Ordenes" },
    { href: "/ordenes/alertas", label: "Alertas" },
  ],
  operario: [
    { href: "/ordenes/bandeja", label: "Mi bandeja" },
    { href: "/ordenes", label: "Ordenes" },
    { href: "/ordenes/alertas", label: "Alertas" },
  ],
};

export default async function NavBar() {
  const user = await getCurrentUser(await cookies());
  const enlaces = user ? POR_ROL[user.rol] : PUBLICOS;

  return (
    <NavMenu enlaces={enlaces}>
      {user ? (
        <ActuarComoSelector />
      ) : (
        <Link href="/login" className={clayBtnClass("coral")}>
          Iniciar sesion
        </Link>
      )}
    </NavMenu>
  );
}
