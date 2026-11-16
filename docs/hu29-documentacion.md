# HU29 — Clientes inactivos y beneficios automáticos

**Historia de usuario:** HU29 — Detectar clientes inactivos y asignarles beneficios automáticos según las reglas configuradas
**Subtareas Jira:** SCRUM-112 y SCRUM-133 `[Desarrollo Backend]`

## 1. Backend

**Autor:** Juan Daniel Torres Morales

### Resumen

El administrador configura reglas de inactividad: "si un cliente lleva N días sin comprar, súmale X puntos". El sistema detecta a esos clientes, deja la lista disponible y suma los puntos una sola vez por período de inactividad. Vive en la app `fidelizacion`: modelos `ReglaInactividad` y `BeneficioInactividad`, y el servicio `fidelizacion/services.py`.

### Decisiones tomadas

- **El período configurado es el de las reglas.** Sin ninguna regla activa no hay período: la lista y la asignación responden `409` y no cambian nada (precondición del escenario 1).
- **Beneficio = puntos de bonificación**, sumados a `Cliente.puntos`. No se mezcla con promociones (HU28) ni con el canje (HU27).
- **Qué es inactivo.** Sin órdenes en los últimos N días. Una orden cancelada no cuenta como actividad. Quien nunca compró cuenta desde que se registró. El día número N ya es inactivo.
- **No se paga dos veces.** `BeneficioInactividad` es único por cliente, regla y fecha de última actividad: mientras el cliente no vuelva a comprar, la regla no se repite; si vuelve y se inactiva otra vez, recibe de nuevo. Correr el proceso varias veces es seguro.
- **Todo o nada (escenario 2).** La asignación corre en una transacción. Si algo falla, se revierte, el error queda en el log (`fidelizacion.services`) y la API responde `503` sin aplicar cambios.
- **Reglas con varios períodos se suman** (30 días: 50 puntos y 90 días: 200 puntos dan 250 a quien lleva 120).
- **El historial de beneficios es de solo lectura**, también en el admin.

### Endpoints (solo administrador)

| Método | Ruta | Respuesta |
|---|---|---|
| `GET` / `POST` | `/api/fidelizacion/reglas-inactividad` | `200` lista / `201` o `400` |
| `GET` / `PATCH` | `/api/fidelizacion/reglas-inactividad/{id}` | `200` o `400` |
| `GET` | `/api/fidelizacion/clientes-inactivos` | `200` con `id, nombre_completo, documento, clasificacion, puntos, ultima_actividad, dias_inactivo`; `409` sin reglas activas |
| `POST` | `/api/fidelizacion/clientes-inactivos/asignar-beneficios` | `200 {beneficios, puntos, clientes}`; `409` sin reglas; `503` si falla |

La lista usa el período más corto de las reglas activas. La regla se desactiva con `activa`, no se borra.

### Cómo se dispara

El proceso es manual desde el endpoint o por comando, para programarlo en cron o en el Cron Job de Render:

```bash
python manage.py asignar_beneficios_inactividad
```

### Pruebas

`fidelizacion/tests.py`: detección, reglas, lista y asignación, incluidos el límite de días, la idempotencia, el rollback y los permisos.

### Pendientes

- Programar el comando de forma periódica en el despliegue.
- Frontend de HU29 y la pantalla de HU30 que muestre los puntos recibidos.
