import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { getCurrentUser } from "@/lib/api";
import LogoutButton from "../logout-button";
import { ClayCard, Encabezado } from "../components/ui/clay";
import IniciarTurno from "./iniciar-turno";

export default async function TurnoPage() {
  const user = await getCurrentUser(await cookies(), { permitirSinTurno: true });
  if (!user) redirect("/login");
  if (user.rol !== "operario") redirect("/");
  if (user.en_turno) redirect("/ordenes/bandeja");

  return (
    <main className="mx-auto max-w-xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Turno" titulo={`Hola, ${user.first_name || user.username}`}>
        Para ver tu bandeja y trabajar las ordenes, inicia tu turno.
      </Encabezado>
      <ClayCard className="py-10">
        <IniciarTurno />
      </ClayCard>
      <div className="mt-6 flex justify-center">
        <LogoutButton />
      </div>
    </main>
  );
}
