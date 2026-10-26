import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";

import { getCurrentUser, getDanos, type DanoPrenda } from "@/lib/api";
import { FECHA_LEGIBLE } from "@/lib/auditoria";
import { formatCOP } from "@/lib/format";
import { ClayBadge, ClayCard, Encabezado, clayBtnClass } from "../components/ui/clay";
import PagarDano from "./pagar-dano";

const FILTROS: { estado?: DanoPrenda["estado"]; etiqueta: string }[] = [
  { estado: "pendiente", etiqueta: "Pendientes" },
  { estado: "pagado", etiqueta: "Pagados" },
  { etiqueta: "Todos" },
];

export default async function DanosPage({
  searchParams,
}: {
  searchParams: Promise<{ estado?: string }>;
}) {
  const cookieStore = await cookies();
  const user = await getCurrentUser(cookieStore);
  if (!user) redirect("/login");
  if (user.rol === "operario") redirect("/");

  const { estado: param } = await searchParams;
  const estado = param === "pagado" || param === "todos" ? param : "pendiente";
  const danos = await getDanos(cookieStore, estado === "todos" ? undefined : estado);
  const esAdmin = user.rol === "administrador";

  return (
    <main className="mx-auto max-w-5xl px-4 py-8 sm:px-8 sm:py-12">
      <Encabezado eyebrow="Entregas · HU19" titulo="Danos y perdidas">
        Prendas que la lavanderia dano o perdio. El valor declarado se le debe al cliente;
        {esAdmin ? " al pagarlo, registra como se pago." : " solo el administrador registra el pago."}
      </Encabezado>

      <nav aria-label="Filtrar por estado" className="mb-6 flex flex-wrap gap-3">
        {FILTROS.map((f) => {
          const valor = f.estado ?? "todos";
          return (
            <Link
              key={valor}
              href={`/danos?estado=${valor}`}
              aria-current={estado === valor ? "page" : undefined}
              className={clayBtnClass(estado === valor ? "primario" : "secundario")}
            >
              {f.etiqueta}
            </Link>
          );
        })}
      </nav>

      {danos === null ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">
            No se pudieron cargar los danos. Verifica que el backend este en ejecucion.
          </p>
        </ClayCard>
      ) : danos.length === 0 ? (
        <ClayCard>
          <p className="text-sm text-(--sw-ink-soft)">No hay danos ni perdidas en este estado.</p>
        </ClayCard>
      ) : (
        <ul className="flex flex-col gap-4">
          {danos.map((d) => (
            <li key={d.id}>
              <ClayCard>
                <div className="flex flex-wrap gap-4">
                  {d.foto_url ? (
                    <a href={d.foto_url} target="_blank" rel="noreferrer" title="Ver la foto completa">
                      {/* eslint-disable-next-line @next/next/no-img-element -- la foto la sirve el backend con la sesion */}
                      <img
                        src={d.foto_url}
                        alt={`Foto del dano en ${d.prenda_nombre}`}
                        className="h-24 w-24 rounded-xl object-cover"
                        loading="lazy"
                      />
                    </a>
                  ) : (
                    <div className="flex h-24 w-24 items-center justify-center rounded-xl bg-(--sw-surface) text-xs text-(--sw-ink-soft)">
                      Sin foto
                    </div>
                  )}
                  <div className="min-w-0 flex-1 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-semibold text-(--sw-ink)">{d.prenda_nombre}</p>
                      <ClayBadge color={d.tipo === "perdida" ? "lavender" : "peach"}>{d.tipo_nombre}</ClayBadge>
                      <ClayBadge color={d.estado === "pagado" ? "mint" : "blue"}>{d.estado_nombre}</ClayBadge>
                    </div>
                    <p className="mt-1 text-(--sw-ink-soft)">
                      <Link href={`/ordenes/${d.orden}`} className="font-semibold underline">
                        {d.orden_codigo}
                      </Link>{" "}
                      · {d.cliente_nombre}
                    </p>
                    <p className="mt-1 text-(--sw-ink)">{d.descripcion}</p>
                    <p className="mt-2 text-(--sw-ink)">
                      Se le debe al cliente: <strong>{formatCOP(d.valor_declarado)}</strong>
                      <span className="text-(--sw-ink-soft)">
                        {" "}
                        · servicio no cobrado {formatCOP(d.valor_servicio)}
                      </span>
                    </p>
                    <p className="mt-1 text-xs text-(--sw-ink-soft)">
                      Operario: {d.operario_nombre ?? "Sin asignar"} · Registro {d.registrado_por_nombre ?? "Sistema"}{" "}
                      · {FECHA_LEGIBLE.format(new Date(d.creado_en))}
                    </p>
                    {d.estado === "pagado" && d.pagado_en && (
                      <p className="mt-1 text-xs text-(--sw-ink-soft)">
                        Pagado por {d.pagado_por_nombre ?? "Sistema"} · {FECHA_LEGIBLE.format(new Date(d.pagado_en))}
                        {d.observacion_pago && ` · ${d.observacion_pago}`}
                      </p>
                    )}
                  </div>
                </div>
                {esAdmin && d.estado === "pendiente" && <PagarDano dano={d} />}
              </ClayCard>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
