import { TIPOS_PQRS, type TipoPqrs } from "@/lib/api";
import { ClayCard, Encabezado } from "../components/ui/clay";
import PqrsForm from "./pqrs-form";

function texto(valor: string | string[] | undefined) {
  return typeof valor === "string" ? valor : "";
}

function esTipo(valor: string): valor is TipoPqrs {
  return (TIPOS_PQRS as readonly string[]).includes(valor);
}

export default async function PqrsPage({
  searchParams,
}: {
  searchParams: Promise<{ [clave: string]: string | string[] | undefined }>;
}) {
  const parametros = await searchParams;
  const tipo = texto(parametros.tipo);
  const codigo = texto(parametros.codigo).replace(/\s+/g, "").toUpperCase().slice(0, 20);

  return (
    <main className="mx-auto max-w-2xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Atencion al cliente" titulo="PQRS">
        Peticiones, quejas, reclamos y sugerencias. No necesitas iniciar sesion. Para una peticion, queja o
        reclamo indica el codigo de tu pedido.
      </Encabezado>

      <ClayCard>
        <PqrsForm tipoInicial={esTipo(tipo) ? tipo : "peticion"} codigoInicial={codigo} />
      </ClayCard>
    </main>
  );
}
