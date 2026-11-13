import { cookies } from "next/headers";
import Link from "next/link";

import { getCurrentUser } from "@/lib/api";
import { clayBtnClass } from "./ui/clay";
import ActuarComoSelector from "./actuar-como";
import { modulosDe } from "./modulos";
import NavMenu, { type Enlace } from "./nav-menu";
import TerminarTurno from "./terminar-turno";

// Sin sesion: nav de cara al cliente que entra a la lavanderia, no al panel
// interno. Con sesion: cada rol ve solo sus modulos (T8/SCRUM-57 hace esto
// exigible tambien en el backend; aqui es solo lo que se muestra).
const PUBLICOS: Enlace[] = [
  { href: "/#servicios", label: "Servicios" },
  { href: "/#como-funciona", label: "Como funciona" },
  { href: "/rastrear-pedido", label: "Rastrear pedido" },
  { href: "/pqrs", label: "PQRS" },
];

export default async function NavBar() {
  // La barra se pinta tambien en /turno: no puede mandar ahi al operario sin turno. Como el
  // layout no se repinta al navegar, lo que depende del turno lo decide NavMenu con la ruta.
  const user = await getCurrentUser(await cookies(), { permitirSinTurno: true });
  const enlaces = user ? modulosDe(user.rol).map(({ href, etiqueta }) => ({ href, label: etiqueta })) : PUBLICOS;

  return (
    <NavMenu enlaces={enlaces}>
      {user ? (
        <>
          {user.rol === "operario" && <TerminarTurno />}
          <ActuarComoSelector />
        </>
      ) : (
        <Link href="/login" className={clayBtnClass("coral")}>
          Iniciar sesion
        </Link>
      )}
    </NavMenu>
  );
}
