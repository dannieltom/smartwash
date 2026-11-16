import { ClayCard, Encabezado } from "../components/ui/clay";
import PestanasRastreo from "./pestanas";

export default function RastrearPedidoPage() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Seguimiento" titulo="Rastrea tu pedido">
        Ingresa el codigo que te dimos al recibir tus prendas. Si no lo recuerdas, consulta con tu cedula y el
        correo que registraste. No necesitas una cuenta.
      </Encabezado>

      <ClayCard>
        <PestanasRastreo />
      </ClayCard>
    </main>
  );
}
