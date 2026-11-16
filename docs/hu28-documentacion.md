# HU28 — Promociones con vigencia por segmento de clientes

**Historia de usuario:** HU28 — Crear promociones con vigencia y asignarlas a segmentos de clientes
**Subtareas Jira:** SCRUM-110 y SCRUM-132 `[Desarrollo Backend]`

## 1. Backend

**Autor:** Juan Daniel Torres Morales

### Resumen

El administrador crea promociones con fecha de inicio y de fin obligatorias y las asigna a uno o más segmentos de clientes. Una promoción vigente, activa y asignada al segmento del cliente queda disponible y la orden la toma al calcular su descuento. Vive en la app `fidelizacion`: modelos `Promocion` y `SegmentoPromocion`.

### Decisiones tomadas

- **Promoción y regla de descuento son cosas distintas.** `ReglaDescuento` (HU08) admite fin de vigencia vacío y una sola clasificación; la promoción exige las dos fechas y al menos un segmento.
- **Segmento = clasificación del cliente** (`Ocasional`, `Frecuente`, `VIP`), las únicas segmentaciones que existen hoy. Se guardan en `SegmentoPromocion`, con restricción única por promoción y clasificación.
- **Descuento como en HU08.** `porcentaje` (0–100) o `monto_fijo`, validado en el serializer y como `CheckConstraint`. Un monto fijo nunca descuenta más que el monto de la orden.
- **`vigente_hasta` es inclusivo y puede ser igual a `vigente_desde`** (promoción de un solo día).
- **Una promoción se desactiva, no se borra** (`activa`); no hay endpoint de borrado.
- **Solo el administrador crea, lista, consulta y edita.** El recepcionista puede consultar las disponibles de un cliente.
- **Cómo se aplica.** `Orden.recalcular` toma el mayor entre el descuento de las reglas y el de las promociones; no se acumulan, igual que las reglas entre sí.
- **Cancelar.** Una petición inválida no cambia nada: la creación y la edición (datos y segmentos) son atómicas.

### Endpoints

| Método | Ruta | Rol | Respuesta |
|---|---|---|---|
| `GET` | `/api/fidelizacion/promociones` | administrador | `200`, lista |
| `POST` | `/api/fidelizacion/promociones` | administrador | `201`, o `400` por campo |
| `GET` | `/api/fidelizacion/promociones/{id}` | administrador | `200` |
| `PATCH` | `/api/fidelizacion/promociones/{id}` | administrador | `200`, o `400`; combina lo enviado con lo guardado |
| `GET` | `/api/fidelizacion/promociones/disponibles?cliente={id}` | administrador, recepcionista | `200`, `400` sin cliente, `404` si no existe |

Cuerpo: `{nombre, descripcion, tipo, valor, segmentos: ["VIP", ...], activa, vigente_desde, vigente_hasta}`. La respuesta agrega `disponible` (activa y hoy dentro de la vigencia).

### Pruebas

`fidelizacion/tests.py` (`PromocionApiTests`, `PromocionDescuentoTests`) y dos pruebas en `ordenes/tests.py` que verifican el descuento en la orden.

### Pendientes

- Frontend de HU28 (SCRUM-111).
- Las promociones no tienen tope de uso ni se combinan con el canje de puntos de HU27.
