import { cookies } from "next/headers";
import Link from "next/link";

import { getCurrentUser, type Rol } from "@/lib/api";
import { Landing } from "./components/landing";
import { ClayCard, Encabezado } from "./components/ui/clay";
import LogoutButton from "./logout-button";

const ACCESOS = [
  {
    href: "/clientes",
    titulo: "Clientes",
    texto: "Registra y edita los datos de tus clientes.",
    color: "blue" as const,
    roles: ["administrador", "recepcionista"] as Rol[],
  },
  {
    href: "/usuarios",
    titulo: "Usuarios",
    texto: "Crea, edita y desactiva cuentas internas.",
    color: "lavender" as const,
    roles: ["administrador"] as Rol[],
  },
  {
    href: "/catalogo",
    titulo: "Catalogo",
    texto: "Servicios y tarifas por tipo de prenda.",
    color: "mint" as const,
    roles: ["administrador", "recepcionista"] as Rol[],
  },
  {
    href: "/fidelizacion",
    titulo: "Fidelizacion",
    texto: "Reglas de descuento para tus clientes.",
    color: "peach" as const,
    roles: ["administrador"] as Rol[],
  },
  {
    href: "/ordenes",
    titulo: "Ordenes",
    texto: "Sigue el estado de las ordenes en curso.",
    color: "blue" as const,
    roles: ["administrador", "recepcionista", "operario"] as Rol[],
  },
  {
    href: "/ordenes/bandeja",
    titulo: "Mi bandeja",
    texto: "Las ordenes que tienes asignadas y aun no se entregan.",
    color: "mint" as const,
    roles: ["operario"] as Rol[],
  },
  {
    href: "/trazabilidad",
    titulo: "Trazabilidad",
    texto: "Seguimiento a las acciones de todos los usuarios, por tipo.",
    color: "lavender" as const,
    roles: ["administrador"] as Rol[],
  },
  {
    href: "/trazabilidad/actividad",
    titulo: "Actividad de operarios",
    texto: "Que orden trabajaba cada operario en un rango de horas, y sus turnos.",
    color: "blue" as const,
    roles: ["administrador"] as Rol[],
  },
];

const FONDO_TARJETA = {
  blue: "bg-(--sw-blue-pastel)",
  mint: "bg-(--sw-mint)",
  lavender: "bg-(--sw-lavender)",
  peach: "bg-(--sw-peach)",
};

export default async function HomePage() {
  const user = await getCurrentUser(await cookies());
  if (!user) return <Landing />;

  const accesos = ACCESOS.filter((acceso) => acceso.roles.includes(user.rol));

  return (
    <main className="mx-auto max-w-6xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado
        eyebrow={`Panel · ${user.rol}`}
        titulo={`Hola, ${user.first_name || user.username}`}
        acciones={<LogoutButton />}
      >
        Sesion iniciada como <strong className="text-(--sw-ink)">{user.username}</strong>
      </Encabezado>

      {accesos.length === 0 ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">
            Tu rol ({user.rol}) todavia no tiene modulos asignados en el panel.
          </p>
        </ClayCard>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {accesos.map((acceso, indice) => (
            <Link
              key={acceso.href}
              href={acceso.href}
              className={`${FONDO_TARJETA[acceso.color]} group relative flex min-h-44 flex-col justify-between overflow-hidden rounded-3xl border-2 border-(--sw-line) p-5 text-(--sw-ink) transition-transform hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[6px_6px_0_0_var(--sw-hard-color)] ${indice === 0 ? "sm:col-span-2" : ""}`}
            >
              <span
                className="pointer-events-none absolute -top-4 right-3 font-sans text-8xl leading-none font-black text-(--sw-ink)/[0.07] select-none"
                aria-hidden="true"
              >
                {String(indice + 1).padStart(2, "0")}
              </span>
              <p className="sw-eyebrow relative text-(--sw-ink)">
                {String(indice + 1).padStart(2, "0")} / {acceso.titulo}
              </p>
              <div className="relative mt-10 flex items-end justify-between gap-4">
                <p className="max-w-56 text-sm font-medium">{acceso.texto}</p>
                <span
                  className="grid size-10 shrink-0 place-items-center rounded-full border-2 border-(--sw-line) bg-(--sw-surface) text-lg transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                  aria-hidden="true"
                >
                  ↗
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
