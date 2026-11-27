# HU34 — Dashboard de indicadores

**Historia de usuario:** HU34 — Ver un dashboard con los indicadores operativos, comerciales y de fidelización
**Subtareas Jira:** SCRUM-118 y SCRUM-137 `[Desarrollo Backend]`

## 1. Backend

**Autor:** Juan Daniel Torres Morales

### Resumen

App nueva `indicadores` (EP10) con los endpoints de consulta del dashboard. Solo lee: no modifica datos. Las escenas 13 a 20 de la historia (carga y actividad de operarios, turno, calificaciones, historial de novedades, listados con buscador y paginación, autocompletado de cliente) ya estaban en `dev` por otros PR; aquí se verificó que existen y no se tocaron. Las tarjetas de inicio por rol (escena 20) son de frontend.

### Endpoints

Todos aceptan el periodo con `dia=AAAA-MM-DD`, `mes=AAAA-MM` o `desde` y `hasta`; sin parámetros es hoy. No se mezclan, no se aceptan fechas futuras y el rango máximo es de 366 días (`400`). El mes en curso llega solo hasta hoy.

| Ruta | Rol | Respuesta |
|---|---|---|
| `GET /api/indicadores/ventas` | administrador; recepcionista solo el total de hoy | `periodo`, `total`, `por_dia` (todos los días, en cero si no hay pagos), `sin_datos` |
| `GET /api/indicadores/servicios-y-prendas` | administrador | `servicios` y `tipos_de_prenda` con `cantidad` y `valor`, de mayor a menor; `limite` (10 por defecto, 50 máximo); `nota` |
| `GET /api/indicadores/clientes-frecuentes` | administrador | `clientes` con `ordenes`, de mayor a menor; `limite` |
| `GET /api/indicadores/ordenes-por-estado` | administrador | un registro por estado, también los que están en cero |
| `GET /api/indicadores/fidelizacion` | administrador | clientes por clasificación, puntos en circulación, promociones vigentes, puntos por inactividad en el periodo y clientes inactivos |

El operario recibe `403` en todos; la recepcionista, en todo lo que no sea el total de hoy (también por la API). El historial de un cliente frecuente (escena 8) es el existente `GET /api/clientes/{id}/ordenes`.

### Decisiones tomadas

- **Venta = pagos menos devoluciones de abono**, cada uno en el día en que se registró, en hora de Colombia. Una devolución puede dejar un día en negativo.
- **El monto de una devolución solo está en el texto del historial** ("$X devueltos al cliente..."), porque los pagos no se editan. Se lee de ahí; si ese texto cambia, hay que cambiar `_monto_devuelto`. Lo sólido sería guardar la devolución como dato propio.
- **Servicios y prendas.** Líneas de órdenes no canceladas, contadas el día en que pasaron a "Recibida" (`abono_alcanzado_en`). La cantidad son prendas atendidas, y una prenda con varios servicios cuenta una vez por tipo de prenda. La `nota` avisa que puede no coincidir con lo cobrado.
- **Cliente frecuente.** Órdenes no canceladas creadas en el periodo (las "En espera" cuentan). El empate se ordena por nombre.
- **Órdenes por estado** incluye "Con novedad", que existe en el modelo aunque la escena 9 no lo nombra.
- **Sin resultados.** Los totales salen en cero y `sin_datos` en `true`; la pantalla decide si muestra "sin datos".
- **Fidelización.** La historia no define estos indicadores; se eligieron los que la app ya tiene.

### Pruebas

`indicadores/tests.py`: periodos y sus errores, ventas (día, mes, rango, devoluciones, hora de Colombia, en cero), servicios y prendas, clientes frecuentes, estados, fidelización y permisos por rol.

### Pendientes

- Frontend del dashboard (gráficos, selector de fecha y vista de recepción).
- Guardar las devoluciones como dato estructurado.
