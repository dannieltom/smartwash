// Cliente HTTP unico hacia la API de Django.
//
// En el navegador las rutas son relativas (/api/...) y Next.js las reenvia al
// backend con el rewrite de next.config.ts, asi que la cookie de sesion viaja
// sola. En el servidor hay que reenviar las cookies a mano.

import { redirect } from "next/navigation";

export type Rol = "administrador" | "recepcionista" | "operario";

/** Lo que devuelve UserSerializer en el backend. */
export type User = {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  rol: Rol;
  /** Solo para operarios: si tiene turno vigente (HU10). */
  en_turno?: boolean;
};

/** El backend responde 403 con este codigo a un operario que no ha iniciado turno. */
export const CODIGO_SIN_TURNO = "turno_no_iniciado";
export const RUTA_TURNO = "/turno";

async function esSinTurno(response: Response): Promise<boolean> {
  if (response.status !== 403) return false;
  const data: unknown = await response.clone().json().catch(() => null);
  return typeof data === "object" && data !== null && "codigo" in data && data.codigo === CODIGO_SIN_TURNO;
}

type Metodo = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

type OpcionesApi = {
  method?: Metodo;
  body?: unknown;
};

/** Cookies ya resueltas de `await cookies()`, lo unico que necesita el server. */
type CookieStore = { toString(): string };

const UNSAFE: ReadonlySet<Metodo> = new Set<Metodo>([
  "POST",
  "PUT",
  "PATCH",
  "DELETE",
]);

function readCookie(name: string): string | undefined {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith(`${name}=`))
    ?.split("=")[1];
}

/** Peticion desde el navegador. Adjunta el token CSRF en metodos de escritura. */
export async function api(
  path: string,
  { method = "GET", body }: OpcionesApi = {},
): Promise<Response> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  if (UNSAFE.has(method)) {
    // GET /api/auth/me lleva @ensure_csrf_cookie: siembra csrftoken si falta.
    if (!readCookie("csrftoken")) await fetch("/api/auth/me");
    headers["X-CSRFToken"] = readCookie("csrftoken") ?? "";
  }

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  // El turno pudo terminar (o cerrarse solo a medianoche) con la pantalla abierta.
  if (await esSinTurno(response)) {
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- fuera de un componente no hay router; la recarga descarta la pantalla que ya no se puede usar
    window.location.href = RUTA_TURNO;
  }
  return response;
}

/** Errores de validacion de DRF por campo. `detail` llega en 403/404 y similares;
 * una respuesta que no es JSON (p. ej. un 500 con HTML) devuelve un objeto vacio. */
export type ErroresApi = Record<string, string[]>;

export async function leerErroresApi(response: Response): Promise<ErroresApi> {
  const data: unknown = await response.json().catch(() => null);
  if (!data || typeof data !== "object" || Array.isArray(data)) return {};
  return Object.fromEntries(
    Object.entries(data).map(([campo, valor]) => [
      campo,
      Array.isArray(valor) ? valor.map(String) : [String(valor)],
    ]),
  );
}

/** Usuario autenticado leido desde un Server Component, o null si no hay sesion.
 *
 * Devuelve null tambien si el backend no responde. Sin esto, un Django caido
 * hace que fetch lance y la pagina entera falle con 500; asi el usuario cae en
 * /login, que al menos es una pantalla util.
 *
 * Un operario sin turno vigente va a /turno: es el unico punto que lo exige en
 * las paginas. Solo /turno y la barra de navegacion lo leen con `permitirSinTurno`.
 */
export async function getCurrentUser(
  cookieStore: CookieStore,
  { permitirSinTurno = false }: { permitirSinTurno?: boolean } = {},
): Promise<User | null> {
  const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
  let usuario: User | null = null;
  try {
    const response = await fetch(`${backend}/api/auth/me`, {
      headers: { cookie: cookieStore.toString() },
      cache: "no-store",
    });
    usuario = response.ok ? ((await response.json()) as User) : null;
  } catch {
    return null;
  }
  // redirect() lanza: va fuera del try para que el catch no se lo trague.
  if (usuario?.rol === "operario" && usuario.en_turno === false && !permitirSinTurno) redirect(RUTA_TURNO);
  return usuario;
}

/** Cuentas sembradas para el selector "actuar como". Null si no aplica (prod). */
export async function getCuentasDesarrollo(): Promise<User[] | null> {
  const response = await api("/auth/actuar-como");
  return response.ok ? ((await response.json()) as User[]) : null;
}

export async function actuarComo(username: string): Promise<User | null> {
  const response = await api("/auth/actuar-como", {
    method: "POST",
    body: { username },
  });
  return response.ok ? ((await response.json()) as User) : null;
}

/* Rastreo publico y PQRS todavia no tienen endpoints en Django: sus funciones
 * devuelven null o fallan sin romper la pantalla. */

/** GET server-side generico: reenvia cookies y nunca lanza. Un backend caido
 * y un endpoint que aun no existe (404) se ven igual desde la pagina: null. */
async function fetchBackend<T>(
  path: string,
  cookieStore: CookieStore,
): Promise<T | null> {
  const backend = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
  let response: Response;
  try {
    response = await fetch(`${backend}/api${path}`, {
      headers: { cookie: cookieStore.toString() },
      cache: "no-store",
    });
  } catch {
    return null;
  }
  if (await esSinTurno(response)) redirect(RUTA_TURNO);
  return response.ok ? ((await response.json().catch(() => null)) as T | null) : null;
}

/* ------------------------------- Clientes (HU05, app clientes) ------------------------------- */

export type Cliente = {
  id: number;
  nombre_completo: string;
  documento: string;
  telefono: string;
  correo: string;
  /** Solo lectura: la clasificacion la recalcula el backend al entregar (HU25)
   * y los puntos los suma la entrega de la orden (HU26). */
  clasificacion: "Ocasional" | "Frecuente" | "VIP";
  puntos: number;
};

export type ClienteFormulario = Omit<Cliente, "id" | "clasificacion" | "puntos">;

export async function getClientes(cookieStore: CookieStore): Promise<Cliente[] | null> {
  return fetchBackend<Cliente[]>("/clientes", cookieStore);
}

export async function getCliente(id: number, cookieStore: CookieStore): Promise<Cliente | null> {
  return fetchBackend<Cliente>(`/clientes/${id}`, cookieStore);
}

export async function crearCliente(datos: ClienteFormulario): Promise<Response> {
  return api("/clientes", { method: "POST", body: datos });
}

export async function actualizarCliente(
  id: number,
  datos: Partial<ClienteFormulario>,
): Promise<Response> {
  return api(`/clientes/${id}`, { method: "PATCH", body: datos });
}

/** GET /clientes/{id}/ordenes (HU06). Llega de la mas reciente a la mas antigua;
 * total_comprado excluye las canceladas, numero_ordenes las incluye. */
export type HistorialCliente = {
  cliente: { id: number; nombre_completo: string };
  numero_ordenes: number;
  total_comprado: string;
  ordenes: {
    id: number;
    codigo: string;
    creado_en: string;
    estado: EstadoOrden;
    valor_total: string;
    estado_pago: "Pendiente" | "Parcial" | "Pagada";
  }[];
};

export async function getHistorialCliente(
  id: number,
  cookieStore: CookieStore,
): Promise<HistorialCliente | null> {
  return fetchBackend<HistorialCliente>(`/clientes/${id}/ordenes`, cookieStore);
}

/* ------------------------- Usuarios internos (HU03, HU04) ------------------------- */

/** Forma prevista para /api/usuarios: agrega is_active, que el UserSerializer
 * de /auth/me no expone porque solo lo necesita esta pantalla de administracion. */
export type UsuarioAdmin = User & { is_active: boolean };

export type UsuarioFormulario = {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  rol: Rol;
  password?: string;
};

export async function getUsuarios(cookieStore: CookieStore): Promise<UsuarioAdmin[] | null> {
  return fetchBackend<UsuarioAdmin[]>("/usuarios", cookieStore);
}

export async function getUsuario(
  id: number,
  cookieStore: CookieStore,
): Promise<UsuarioAdmin | null> {
  return fetchBackend<UsuarioAdmin>(`/usuarios/${id}`, cookieStore);
}

export async function crearUsuario(datos: UsuarioFormulario): Promise<Response> {
  return api("/usuarios", { method: "POST", body: datos });
}

export async function actualizarUsuario(
  id: number,
  datos: Partial<UsuarioFormulario>,
): Promise<Response> {
  return api(`/usuarios/${id}`, { method: "PATCH", body: datos });
}

export async function desactivarUsuario(id: number): Promise<Response> {
  return api(`/usuarios/${id}/desactivar`, { method: "POST" });
}

export async function activarUsuario(id: number): Promise<Response> {
  return api(`/usuarios/${id}/activar`, { method: "POST" });
}

export type AccionUsuario = "creado" | "editado" | "activado" | "desactivado" | "inicio_sesion";

export type HistorialAccion = {
  id: number;
  accion: AccionUsuario;
  detalle: string;
  fecha: string;
};

export async function getHistorialUsuario(
  id: number,
  cookieStore: CookieStore,
): Promise<HistorialAccion[] | null> {
  return fetchBackend<HistorialAccion[]>(`/usuarios/${id}/historial`, cookieStore);
}

/** Trazabilidad global: lo mismo que el historial por usuario, pero cruzando
 * todos los usuarios y filtrable por tipo de usuario (rol). Modulo solo para
 * administrador. "cliente" no es un Rol de accounts.User (no inicia sesion,
 * ver rastrear-pedido/ y pqrs/): aqui agrupa las acciones publicas que deja
 * un visitante sin cuenta, por eso usuario_id puede ser null. */
export type TipoUsuarioAuditoria = Rol | "cliente";

export type AccionAuditoria = {
  id: number;
  usuario_id: number | null;
  usuario: string;
  tipo_usuario: TipoUsuarioAuditoria;
  accion: AccionUsuario;
  detalle: string;
  fecha: string;
};

export async function getTrazabilidad(
  cookieStore: CookieStore,
  tipoUsuario?: TipoUsuarioAuditoria,
): Promise<AccionAuditoria[] | null> {
  const query = tipoUsuario ? `?rol=${encodeURIComponent(tipoUsuario)}` : "";
  return fetchBackend<AccionAuditoria[]>(`/usuarios/trazabilidad${query}`, cookieStore);
}

/* --------------------------- Catalogo de servicios y tarifas (HU07) --------------------------- */

export type TipoPrenda = { id: number; nombre: string; peso_estandar: string | null };
export type NivelDificultad = { id: number; nombre: string; factor: string };
export type Material = {
  id: number;
  nombre: string;
  nivel_dificultad: number;
  nivel_dificultad_nombre: string;
  factor: string;
};
export type Servicio = { id: number; nombre: string; descripcion: string };
/** Sin tipo de prenda es la tarifa general del servicio; con tipo, una excepcion. */
export type Tarifa = {
  id: number;
  servicio: number;
  servicio_nombre: string;
  tipo_prenda: number | null;
  tipo_prenda_nombre: string | null;
  valor_base: string;
  precio_por_kilo: string;
  plazo_entrega_dias: number;
  vigente_desde: string;
  vigente_hasta: string | null;
};

export type TarifaFormulario = Omit<Tarifa, "id" | "tipo_prenda_nombre" | "servicio_nombre">;

export async function getTiposPrenda(cookieStore: CookieStore): Promise<TipoPrenda[] | null> {
  return fetchBackend<TipoPrenda[]>("/catalogo/tipos-prenda", cookieStore);
}

export async function getNivelesDificultad(
  cookieStore: CookieStore,
): Promise<NivelDificultad[] | null> {
  return fetchBackend<NivelDificultad[]>("/catalogo/niveles-dificultad", cookieStore);
}

export async function getMateriales(cookieStore: CookieStore): Promise<Material[] | null> {
  return fetchBackend<Material[]>("/catalogo/materiales", cookieStore);
}

export async function getServicios(cookieStore: CookieStore): Promise<Servicio[] | null> {
  return fetchBackend<Servicio[]>("/catalogo/servicios", cookieStore);
}

export async function getTarifas(
  cookieStore: CookieStore,
  soloVigentes = false,
): Promise<Tarifa[] | null> {
  return fetchBackend<Tarifa[]>(
    `/catalogo/tarifas${soloVigentes ? "?vigentes=1" : ""}`,
    cookieStore,
  );
}

export async function crearTipoPrenda(datos: Omit<TipoPrenda, "id">): Promise<Response> {
  return api("/catalogo/tipos-prenda", { method: "POST", body: datos });
}

export async function crearNivelDificultad(datos: Omit<NivelDificultad, "id">): Promise<Response> {
  return api("/catalogo/niveles-dificultad", { method: "POST", body: datos });
}

export async function actualizarNivelDificultad(
  id: number,
  datos: Partial<Omit<NivelDificultad, "id">>,
): Promise<Response> {
  return api(`/catalogo/niveles-dificultad/${id}`, { method: "PATCH", body: datos });
}

export type MaterialFormulario = { nombre: string; nivel_dificultad: number };

export async function crearMaterial(datos: MaterialFormulario): Promise<Response> {
  return api("/catalogo/materiales", { method: "POST", body: datos });
}

export async function actualizarMaterial(
  id: number,
  datos: Partial<MaterialFormulario>,
): Promise<Response> {
  return api(`/catalogo/materiales/${id}`, { method: "PATCH", body: datos });
}

export async function crearServicio(datos: Omit<Servicio, "id">): Promise<Response> {
  return api("/catalogo/servicios", { method: "POST", body: datos });
}

export async function actualizarTipoPrenda(
  id: number,
  datos: Partial<Omit<TipoPrenda, "id">>,
): Promise<Response> {
  return api(`/catalogo/tipos-prenda/${id}`, { method: "PATCH", body: datos });
}

export async function actualizarServicio(
  id: number,
  datos: Partial<Omit<Servicio, "id">>,
): Promise<Response> {
  return api(`/catalogo/servicios/${id}`, { method: "PATCH", body: datos });
}

export async function crearTarifa(datos: TarifaFormulario): Promise<Response> {
  return api("/catalogo/tarifas", { method: "POST", body: datos });
}

export async function actualizarTarifa(
  id: number,
  datos: Partial<TarifaFormulario>,
): Promise<Response> {
  return api(`/catalogo/tarifas/${id}`, { method: "PATCH", body: datos });
}

/* ------------------------- Fidelizacion: reglas de descuento (HU08) ------------------------- */

export type ReglaDescuento = {
  id: number;
  nombre: string;
  tipo: "porcentaje" | "monto_fijo";
  valor: string;
  clasificacion_cliente: Cliente["clasificacion"] | "";
  activa: boolean;
  vigente_desde: string;
  vigente_hasta: string | null;
};

export async function getReglasDescuento(
  cookieStore: CookieStore,
): Promise<ReglaDescuento[] | null> {
  return fetchBackend<ReglaDescuento[]>("/fidelizacion/reglas-descuento", cookieStore);
}

export async function crearReglaDescuento(
  datos: Omit<ReglaDescuento, "id">,
): Promise<Response> {
  return api("/fidelizacion/reglas-descuento", { method: "POST", body: datos });
}

export async function actualizarReglaDescuento(
  id: number,
  datos: Partial<Omit<ReglaDescuento, "id">>,
): Promise<Response> {
  return api(`/fidelizacion/reglas-descuento/${id}`, { method: "PATCH", body: datos });
}

/* --------------------------- Recuperacion de contrasena (HU02) --------------------------- */

export async function solicitarRecuperacionPassword(identificador: string): Promise<Response> {
  return api("/auth/recuperar-password", {
    method: "POST",
    body: { identificador },
  });
}

export async function confirmarRecuperacionPassword(
  uid: string,
  token: string,
  password: string,
): Promise<Response> {
  return api("/auth/confirmar-recuperacion", {
    method: "POST",
    body: { uid, token, password },
  });
}

/* --------------------------------- Ordenes (staff, EP04/EP05) --------------------------------- */

export type EstadoOrden =
  | "Recibida"
  | "Clasificada"
  | "En proceso"
  | "Control de calidad"
  | "Lista para entrega"
  | "Entregada"
  | "Cancelada"
  | "En espera"
  | "Con novedad";

export type ServicioDePrenda = {
  id: number;
  servicio: number;
  servicio_nombre: string;
  valor_aplicado: string;
  valor_base: string | null;
  precio_por_kilo: string | null;
  peso: string | null;
  nivel_dificultad: string;
  factor: string | null;
  es_excepcion: boolean | null;
};

export type PrendaDeOrden = {
  id: number;
  tipo_prenda: number;
  tipo_prenda_nombre: string;
  material: number | null;
  material_nombre: string | null;
  cantidad: number;
  peso: string | null;
  talla: string;
  genero: string;
  color: string;
  estado_inicial: string;
  servicios: ServicioDePrenda[];
  /** La lavanderia la dano o la perdio (HU19): ya no se cobra ni se vuelve a verificar. */
  dano: TipoDano | null;
  /** Unidades de la linea danadas o perdidas; las demas se entregaron y se cobraron. */
  dano_cantidad: number | null;
  dano_valor_unitario_declarado: string | null;
  /** Lo que se le debe al cliente por esas unidades. */
  dano_valor_declarado: string | null;
};

/** Lo que devuelve OrdenSerializer. Los montos llegan como texto decimal. */
export type Orden = {
  id: number;
  codigo: string;
  cliente: number;
  cliente_nombre: string;
  recepcionista: number;
  operario: number | null;
  estado: EstadoOrden;
  estado_pago: "Pendiente" | "Parcial" | "Pagada";
  subtotal: string;
  descuento: string;
  descuento_novedad: string;
  descuento_dano: string;
  valor_total: string;
  abono_requerido: string;
  fecha_estimada_entrega: string | null;
  fecha_entrega: string | null;
  creado_en: string;
  detalle_prendas: PrendaDeOrden[];
  total_pagado: string;
  saldo_pendiente: string;
  tiene_abono: boolean;
  pago_completo: boolean;
  /** Lo pagado de mas por los descuentos; se devuelve al entregar. */
  saldo_a_favor: string;
  motivo_cancelacion: string;
};

/** Una linea de prenda tal como la recibe POST /ordenes y POST /ordenes/{id}/prendas. */
export type PrendaFormulario = {
  tipo_prenda: number;
  material: number;
  cantidad: number;
  peso: string;
  talla: string;
  genero: string;
  color: string;
  estado_inicial: string;
  servicios: number[];
};

export async function getOrdenes(cookieStore: CookieStore): Promise<Orden[] | null> {
  return fetchBackend<Orden[]>("/ordenes", cookieStore);
}

export type TipoEventoOrden =
  | "creacion"
  | "pago"
  | "asignacion"
  | "reasignacion"
  | "cambio_estado"
  | "prenda_agregada"
  | "servicio_agregado"
  | "entrega"
  | "novedad"
  | "decision_novedad"
  | "notificacion"
  | "cancelacion"
  | "devolucion"
  | "dano_prenda"
  | "pago_dano";

/** Lo que devuelve HistorialOrdenSerializer. `usuario` es null cuando el
 * evento lo genero el sistema; `usuario_nombre` ya trae "Sistema" en ese caso. */
export type EventoOrden = {
  id: number;
  fecha: string;
  tipo_evento: TipoEventoOrden;
  tipo_evento_nombre: string;
  usuario: number | null;
  usuario_nombre: string;
  detalle: string;
};

/** Historial inmutable de la orden en orden cronologico (HU15). Solo lo
 * consultan el administrador y la recepcionista; el operario recibe 403. */
export async function getHistorialOrden(
  id: number,
  cookieStore: CookieStore,
): Promise<EventoOrden[] | null> {
  return fetchBackend<EventoOrden[]>(`/ordenes/${id}/historial`, cookieStore);
}

export async function getOrden(id: number, cookieStore: CookieStore): Promise<Orden | null> {
  return fetchBackend<Orden>(`/ordenes/${id}`, cookieStore);
}

/** Lo que devuelve OrdenBandejaSerializer: sin cliente ni valores, solo lo que
 * el operario necesita para trabajar. */
export type PrendaDeBandeja = Omit<PrendaDeOrden, "tipo_prenda" | "material" | "servicios"> & {
  servicios: string[];
};

export type OrdenDeBandeja = Pick<Orden, "id" | "codigo" | "estado" | "fecha_estimada_entrega"> & {
  prendas: PrendaDeBandeja[];
};

/** Ordenes asignadas al operario de la sesion que aun no se entregan (HU11).
 * El backend filtra por operario; otro rol recibe 403. */
export async function getBandeja(cookieStore: CookieStore): Promise<OrdenDeBandeja[] | null> {
  return fetchBackend<OrdenDeBandeja[]>("/ordenes/bandeja", cookieStore);
}

/** Lo que devuelve OrdenAlertaSerializer. `dias` es el retraso si la orden esta
 * retrasada y lo que falta si esta proxima (0 = vence hoy). */
export type AlertaOrden = {
  id: number;
  codigo: string;
  cliente_nombre: string;
  estado: EstadoOrden | "Con novedad";
  operario: number | null;
  fecha_estimada_entrega: string;
  tipo: "retrasada" | "proxima";
  dias: number;
};

/** Ordenes retrasadas o proximas a vencer (HU16). Al operario el backend le
 * devuelve solo las suyas. */
export async function getAlertasOrdenes(cookieStore: CookieStore): Promise<AlertaOrden[] | null> {
  return fetchBackend<AlertaOrden[]>("/ordenes/alertas", cookieStore);
}

export async function crearOrden(cliente: number, prendas: PrendaFormulario[]): Promise<Response> {
  return api("/ordenes", { method: "POST", body: { cliente, prendas } });
}

export async function agregarPrendaAOrden(id: number, prenda: PrendaFormulario): Promise<Response> {
  return api(`/ordenes/${id}/prendas`, { method: "POST", body: prenda });
}

export async function agregarServicioAPrenda(
  id: number,
  prendaId: number,
  servicio: number,
): Promise<Response> {
  return api(`/ordenes/${id}/prendas/${prendaId}/servicios`, {
    method: "POST",
    body: { servicio },
  });
}

export type TipoDano = "dano" | "perdida";
export type ResultadoVerificacion = "coincide" | "novedad" | TipoDano;

/** Novedad: observacion y foto. Dano: observacion, foto y valor de la prenda.
 * Perdida: observacion y valor, sin foto (HU18 y HU19). */
export type VerificacionPrenda = {
  prenda: number;
  resultado: ResultadoVerificacion;
  observacion: string;
  foto: string | null;
  /** Valor de UNA unidad; el total que se le debe al cliente lo calcula el backend. */
  valor_unitario_declarado: string | null;
  /** Solo con dano o perdida: unidades de la linea afectadas (1 a su cantidad). */
  cantidad_afectada: number | null;
};

/** Entrega la orden verificando cada prenda que sigue en ella (HU12). El backend
 * exige que este "Lista para entrega" y el pago completo del total ya descontado
 * (HU24). Con alguna novedad la orden queda "Con novedad" en vez de entregarse. */
export async function registrarEntrega(id: number, prendas: VerificacionPrenda[]): Promise<Response> {
  return api(`/ordenes/${id}/entrega`, { method: "POST", body: { prendas } });
}

/* ------------------------------- Novedades de una orden (HU18) ------------------------------- */

/** Lo que devuelve NovedadSerializer. La foto no viene aqui: `foto_url` apunta
 * a /api/novedades/{id}/foto, que responde la imagen y sirve directo en <img>. */
export type Novedad = {
  id: number;
  orden: number;
  prenda: number;
  prenda_nombre: string;
  descripcion: string;
  origen: "proceso" | "entrega";
  origen_nombre: string;
  estado_anterior: EstadoOrden;
  usuario_nombre: string | null;
  creado_en: string;
  foto_url: string | null;
  decision: DecisionNovedad | null;
  decision_observacion: string;
  gravedad: Gravedad | "";
  porcentaje_descuento: string | null;
  monto_descuento: string;
};

/** Las del proceso: continuar o agregar_servicio (reprocesar y no_continuar solo
 * aparecen en decisiones viejas). Las de la entrega: entregar_con_descuento o
 * reprocesar_con_descuento (HU19). */
export type DecisionNovedad =
  | "continuar"
  | "agregar_servicio"
  | "reprocesar"
  | "no_continuar"
  | "entregar_con_descuento"
  | "reprocesar_con_descuento";

export type Gravedad = "leve" | "moderada" | "notoria";

export type DecisionFormulario = {
  decision: DecisionNovedad;
  observacion: string;
  gravedades?: { novedad: number; gravedad: Gravedad }[];
  operario?: number | null;
  /** Solo con agregar_servicio, y solo para las prendas con novedad. */
  servicios?: { prenda: number; servicio: number }[];
};

/** Una sola decision resuelve todas las novedades pendientes de la orden.
 * "Entregar con descuento" tambien entrega la orden si el pago cubre el nuevo total. */
export async function registrarDecision(id: number, datos: DecisionFormulario): Promise<Response> {
  return api(`/ordenes/${id}/decision`, { method: "POST", body: datos });
}

/** Porcentajes de los descuentos por novedad. Cualquier sesion la lee; solo el
 * administrador la cambia, y lo ya descontado conserva sus valores. */
export type ConfiguracionDescuentos = {
  porcentaje_leve: string;
  porcentaje_moderada: string;
  porcentaje_notoria: string;
  porcentaje_reproceso: string;
  monto_minimo: string;
  tope_porcentaje: string;
  actualizado_en: string;
};

export type CambioDescuentos = { fecha: string; usuario_nombre: string; detalle: string };

export async function getConfiguracionDescuentos(
  cookieStore: CookieStore,
): Promise<ConfiguracionDescuentos | null> {
  return fetchBackend<ConfiguracionDescuentos>("/ordenes/descuentos-novedad", cookieStore);
}

export async function getCambiosDescuentos(cookieStore: CookieStore): Promise<CambioDescuentos[] | null> {
  return fetchBackend<CambioDescuentos[]>("/ordenes/descuentos-novedad/cambios", cookieStore);
}

export async function actualizarConfiguracionDescuentos(
  datos: Omit<ConfiguracionDescuentos, "actualizado_en">,
): Promise<Response> {
  return api("/ordenes/descuentos-novedad", { method: "PATCH", body: datos });
}

/** GET /ordenes/novedades: solo recepcionista y administrador. Cada orden trae
 * solo sus novedades pendientes, incluidas las que el cliente decidio no continuar. */
export type OrdenConNovedad = {
  id: number;
  codigo: string;
  cliente_nombre: string;
  estado: EstadoOrden;
  operario_nombre: string | null;
  novedades: Novedad[];
};

export async function getOrdenesConNovedad(cookieStore: CookieStore): Promise<OrdenConNovedad[] | null> {
  return fetchBackend<OrdenConNovedad[]>("/ordenes/novedades", cookieStore);
}

export async function getNovedadesOrden(id: number, cookieStore: CookieStore): Promise<Novedad[] | null> {
  return fetchBackend<Novedad[]>(`/ordenes/${id}/novedades`, cookieStore);
}

/** Novedad durante el proceso: solo el operario asignado o el administrador, con
 * la orden "En proceso" o "Control de calidad". Descripcion y foto obligatorias;
 * la foto es un data URL de 500 KB o menos. La orden queda "Con novedad". */
export async function registrarNovedad(
  id: number,
  datos: { prenda: number; descripcion: string; foto: string },
): Promise<Response> {
  return api(`/ordenes/${id}/novedades`, { method: "POST", body: datos });
}

/** Avanza la orden por el flujo (HU14). El backend valida la transicion, el
 * abono y que el operario sea el asignado; "Entregada" va por /entrega (HU12). */
export async function cambiarEstadoOrden(id: number, estado: EstadoOrden): Promise<Response> {
  return api(`/ordenes/${id}/estado`, { method: "POST", body: { estado } });
}

/** Lo que devuelve OperarioSerializer. /operarios lista solo los activos. */
/** Operario activo con su carga (HU10): las mismas ordenes y prendas que ve en su bandeja.
 * `recomendado` marca a lo sumo uno: el de menos prendas entre los que estan en turno. */
export type Operario = {
  id: number;
  username: string;
  nombre: string;
  en_turno: boolean;
  ordenes_activas: number;
  prendas_activas: number;
  recomendado: boolean;
};

export async function getOperarios(cookieStore: CookieStore): Promise<Operario[] | null> {
  return fetchBackend<Operario[]>("/operarios", cookieStore);
}

export type OrdenDeOperario = {
  id: number;
  codigo: string;
  /** Ultima asignacion de la orden; null en ordenes asignadas antes de registrarse. */
  fecha_asignacion: string | null;
  cliente_nombre: string;
  estado: EstadoOrden;
  total_prendas: number;
  prendas: { cantidad: number; tipo_prenda: string; servicios: string[] }[];
};

/** Las ordenes activas de un operario, para ver su carga antes de asignarle otra. */
export async function getOrdenesDeOperario(id: number): Promise<OrdenDeOperario[] | null> {
  const response = await api(`/operarios/${id}/ordenes`).catch(() => null);
  return response?.ok ? ((await response.json()) as OrdenDeOperario[]) : null;
}

/* ------------------------------- Turnos de operario (HU10) ------------------------------- */

export type EstadoTurno = { en_turno: boolean; inicio: string | null; ordenes_en_curso: number };

export async function getTurnoActual(): Promise<EstadoTurno | null> {
  const response = await api("/turnos/actual").catch(() => null);
  return response?.ok ? ((await response.json()) as EstadoTurno) : null;
}

export async function iniciarTurno(): Promise<Response> {
  return api("/turnos/iniciar", { method: "POST" });
}

export async function terminarTurno(): Promise<Response> {
  return api("/turnos/terminar", { method: "POST" });
}

export type TurnoRegistrado = {
  operario: number;
  operario_nombre: string;
  inicio: string;
  fin: string | null;
  cierre: "manual" | "automatico" | null;
};

export type EtapaDeTrabajo = {
  operario: number;
  operario_nombre: string;
  orden: number;
  orden_codigo: string;
  cliente_nombre: string;
  estado: "En proceso" | "Control de calidad";
  inicio: string;
  fin: string | null;
};

export type ActividadOperarios = { turnos: TurnoRegistrado[]; etapas: EtapaDeTrabajo[] };

/** Solo el administrador. desde/hasta en ISO con zona; maximo 31 dias. */
export async function getActividad(
  cookieStore: CookieStore,
  filtros: { desde: string; hasta: string; operario?: string },
): Promise<ActividadOperarios | null> {
  const params = new URLSearchParams({ desde: filtros.desde, hasta: filtros.hasta });
  if (filtros.operario) params.set("operario", filtros.operario);
  return fetchBackend<ActividadOperarios>(`/operarios/actividad?${params}`, cookieStore);
}

/** HU13: solo recepcionista o administrador, y antes de iniciar el servicio,
 * salvo una orden "Con novedad" cuyo cliente decidio no continuar. Si hay pagos,
 * la devolucion queda en el historial; los pagos no se tocan. */
export async function cancelarOrden(id: number, motivo: string): Promise<Response> {
  return api(`/ordenes/${id}/cancelacion`, { method: "POST", body: { motivo } });
}

/** Asigna o reasigna la orden (HU10). El backend valida el rol, el abono, que
 * el operario este activo y que el estado de la orden lo permita. */
export async function asignarOperario(id: number, operario: number): Promise<Response> {
  return api(`/ordenes/${id}/asignacion`, { method: "POST", body: { operario } });
}

/* ------------------------------- Danos y perdidas de prendas (HU19) ------------------------------- */

/** `valor_declarado` es lo que la lavanderia le debe al cliente (valor de una
 * unidad x unidades afectadas) y no toca el total de la orden; `valor_servicio`
 * es lo que se dejo de cobrar. */
export type DanoPrenda = {
  id: number;
  orden: number;
  orden_codigo: string;
  cliente_nombre: string;
  prenda: number;
  prenda_nombre: string;
  prenda_cantidad: number;
  cantidad_afectada: number;
  tipo: TipoDano;
  tipo_nombre: string;
  descripcion: string;
  valor_unitario_declarado: string;
  /** Total que se le debe al cliente: valor_unitario_declarado x cantidad_afectada. */
  valor_declarado: string;
  valor_servicio: string;
  operario_nombre: string | null;
  registrado_por_nombre: string | null;
  creado_en: string;
  estado: "pendiente" | "pagado";
  estado_nombre: string;
  pagado_por_nombre: string | null;
  pagado_en: string | null;
  observacion_pago: string;
  foto_url: string | null;
};

/** Administrador y recepcionista; el operario recibe 403. */
export async function getDanos(
  cookieStore: CookieStore,
  estado?: DanoPrenda["estado"],
): Promise<DanoPrenda[] | null> {
  return fetchBackend<DanoPrenda[]>(estado ? `/danos?estado=${estado}` : "/danos", cookieStore);
}

/** Solo el administrador; la observacion (por ejemplo, el medio de pago) es obligatoria. */
export async function pagarDano(id: number, observacion: string): Promise<Response> {
  return api(`/danos/${id}/pago`, { method: "POST", body: { observacion } });
}

/* ------------------------------- Pagos de una orden (HU21) ------------------------------- */

export type MetodoPago = "efectivo" | "transferencia" | "tarjeta";

/** Los pagos no se editan ni se eliminan: solo se registran y se listan. */
export type Pago = {
  id: number;
  monto: string;
  metodo: MetodoPago;
  creado_en: string;
  creado_por: number | null;
};

export async function getPagosOrden(id: number, cookieStore: CookieStore): Promise<Pago[] | null> {
  return fetchBackend<Pago[]>(`/ordenes/${id}/pagos`, cookieStore);
}

export async function registrarPago(id: number, monto: string, metodo: MetodoPago): Promise<Response> {
  return api(`/ordenes/${id}/pagos`, { method: "POST", body: { monto, metodo } });
}

/* ------------------------- Rastreo publico de pedidos (sin cuenta de cliente) ------------------------- *
 * Orden.codigo se diseno para esto: "codigo de rastreo... publico" (ver
 * backend/ordenes/models.py). No hay rol "cliente" en accounts.User, asi que
 * el seguimiento del pedido es publico por codigo en vez de requerir login. */

export type EtapaSeguimiento =
  | "Recibida"
  | "Clasificada"
  | "En proceso"
  | "Control de calidad"
  | "Lista para entrega"
  | "Pagada"
  | "Entregada";

/** Solo la etapa "Pagada" trae el estado del pago y sus montos, en pesos enteros: el
 * total es lo que realmente se cobra. Si es parcial, la fecha es la del ultimo abono. */
export type EtapaDeSeguimiento = {
  etapa: EtapaSeguimiento;
  fecha: string | null;
  estado_pago?: "pendiente" | "parcial" | "completo";
  abonado?: number;
  total?: number;
};

/** GET /ordenes/consulta/{codigo} (HU17): sin datos del cliente, usuarios ni montos. La
 * busqueda es exacta; un codigo que no existe responde 404 con su mensaje. Cada etapa trae
 * la fecha y hora (ISO con offset) en que la orden entro a ella, o null si sigue pendiente. */
export type SeguimientoOrden = {
  codigo: string;
  estado: EstadoOrden;
  fecha_estimada_entrega: string | null;
  /** null mientras la orden esta "En espera" (sin abono). */
  etapa_actual: EtapaSeguimiento | null;
  etapas: EtapaDeSeguimiento[];
  con_novedad: boolean;
  cancelada: boolean;
  fecha_cancelacion: string | null;
  /** Cambios en orden cronologico, con una etiqueta publica (p. ej. "Volvio a proceso"). */
  eventos: { etiqueta: string; fecha: string }[];
};

export async function rastrearOrden(codigo: string): Promise<Response> {
  return api(`/ordenes/consulta/${encodeURIComponent(codigo)}`);
}

/** Una orden en la consulta por cedula (HU17): sin datos del cliente, ids, pagos ni motivos. El
 * total va en pesos enteros y las prendas agrupadas, sin las danadas o perdidas. */
export type OrdenDeCliente = {
  codigo: string;
  estado: EstadoOrden;
  total: number;
  prendas: { cantidad: number; tipo_prenda: string; servicios: string[] }[];
};

/** Activas: todo lo que no esta Entregada ni Cancelada. Ambas listas, de la mas reciente a la mas antigua. */
export type OrdenesDeCliente = { activas: OrdenDeCliente[]; historial: OrdenDeCliente[] };

/** POST para que la cedula y el correo no queden en la URL. Cualquier dato que no coincida
 * responde el mismo 404, y el backend limita los intentos (429). */
export async function consultarPorDocumento(documento: string, correo: string): Promise<Response> {
  return api("/ordenes/consulta-por-documento", { method: "POST", body: { documento, correo } });
}

/* ------------------------------------- PQRS (EP06, publico) ------------------------------------- */

export type PqrsFormulario = {
  tipo: "peticion" | "queja" | "reclamo" | "sugerencia";
  nombre: string;
  documento: string;
  correo: string;
  telefono: string;
  codigo_orden: string;
  mensaje: string;
};

export async function crearPqrs(datos: PqrsFormulario): Promise<Response> {
  return api("/pqrs", { method: "POST", body: datos });
}

