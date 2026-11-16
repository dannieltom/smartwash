import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import {
  consultaDeLista,
  getCurrentUser,
  getMateriales,
  getNivelesDificultad,
  getPagina,
  getServicios,
  getTiposPrenda,
  type Tarifa,
} from "@/lib/api";
import { lectorDe, paginaDesde } from "../components/lista/url";
import { ClayCard, Encabezado } from "../components/ui/clay";
import MaterialForm from "./material-form";
import NivelForm from "./nivel-form";
import ServicioForm from "./servicio-form";
import { leerFiltrosTarifas } from "./filtros";
import ListaTarifas from "./lista-tarifas";
import { TablaMateriales, TablaNiveles, TablaServicios, TablaTiposPrenda } from "./tabla-catalogo";
import TarifaForm from "./tarifa-form";
import TipoPrendaForm from "./tipo-prenda-form";

function ErrorDeCarga({ recurso }: { recurso: string }) {
  return (
    <ClayCard>
      <p className="text-sm text-(--sw-ink-soft)">
        No se pudieron cargar {recurso}. Verifica que el backend este en ejecucion.
      </p>
    </ClayCard>
  );
}

export default async function CatalogoPage({
  searchParams,
}: {
  searchParams: Promise<{ [clave: string]: string | string[] | undefined }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  const puedeEditar = user.rol === "administrador";

  const lector = lectorDe(await searchParams);
  const consultaTarifas = consultaDeLista(leerFiltrosTarifas(lector), paginaDesde(lector));
  const [tiposPrenda, niveles, materiales, servicios, tarifas] = await Promise.all([
    getTiposPrenda(cookieStore),
    getNivelesDificultad(cookieStore),
    getMateriales(cookieStore),
    getServicios(cookieStore),
    getPagina<Tarifa>(cookieStore, "/catalogo/tarifas", consultaTarifas),
  ]);

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Administracion · EP03" titulo="Catalogo">
        {puedeEditar
          ? "Administra tipos de prenda, materiales, servicios y las tarifas por servicio (HU07)."
          : "Consulta tipos de prenda, materiales, servicios y las tarifas por servicio (HU07)."}
      </Encabezado>

      {puedeEditar && (
        <ClayCard className="mb-4">
          <h2 className="sw-eyebrow">Nuevo tipo de prenda</h2>
          <TipoPrendaForm className="mt-4" />
        </ClayCard>
      )}
      <div className="mb-6">
        {tiposPrenda === null ? (
          <ErrorDeCarga recurso="los tipos de prenda" />
        ) : (
          <TablaTiposPrenda tiposPrenda={tiposPrenda} editable={puedeEditar} />
        )}
      </div>

      {puedeEditar && (
        <ClayCard className="mb-4">
          <h2 className="sw-eyebrow">Nuevo nivel de dificultad</h2>
          <p className="mt-2 text-sm text-(--sw-ink-soft)">
            El factor multiplica el precio de todos los servicios de las prendas cuyo material tenga ese nivel.
          </p>
          <NivelForm className="mt-4" />
        </ClayCard>
      )}
      <div className="mb-6">
        {niveles === null ? (
          <ErrorDeCarga recurso="los niveles de dificultad" />
        ) : (
          <TablaNiveles niveles={niveles} editable={puedeEditar} />
        )}
      </div>

      {puedeEditar && (
        <ClayCard className="mb-4">
          <h2 className="sw-eyebrow">Nuevo material</h2>
          <MaterialForm niveles={niveles ?? []} className="mt-4" />
        </ClayCard>
      )}
      <div className="mb-6">
        {materiales === null ? (
          <ErrorDeCarga recurso="los materiales" />
        ) : (
          <TablaMateriales materiales={materiales} niveles={niveles ?? []} editable={puedeEditar} />
        )}
      </div>

      {puedeEditar && (
        <ClayCard className="mb-4">
          <h2 className="sw-eyebrow">Nuevo servicio</h2>
          <ServicioForm className="mt-4" />
        </ClayCard>
      )}
      <div className="mb-6">
        {servicios === null ? (
          <ErrorDeCarga recurso="los servicios" />
        ) : (
          <TablaServicios servicios={servicios} editable={puedeEditar} />
        )}
      </div>

      <p className="mb-4 text-sm text-(--sw-ink-soft)">
        El precio de un servicio es (valor base por prenda + peso en kg x precio por kilo) x el factor del
        material, redondeado a la centena. Si hay una excepcion vigente para el tipo de prenda se usa esa;
        si no, la tarifa general del servicio.
      </p>
      {puedeEditar && (
        <ClayCard className="mb-4">
          <h2 className="sw-eyebrow">Nueva tarifa general por servicio</h2>
          <div className="mt-4">
            <TarifaForm tiposPrenda={[]} servicios={servicios ?? []} general />
          </div>
        </ClayCard>
      )}
      {puedeEditar && (
        <ClayCard className="mb-4">
          <h2 className="sw-eyebrow">Nueva excepcion por tipo de prenda (opcional)</h2>
          <div className="mt-4">
            <TarifaForm tiposPrenda={tiposPrenda ?? []} servicios={servicios ?? []} general={false} />
          </div>
        </ClayCard>
      )}
      <h2 className="sw-eyebrow mb-4">Tarifas</h2>
      <ListaTarifas inicial={tarifas} consultaInicial={consultaTarifas} editable={puedeEditar} />
    </main>
  );
}
