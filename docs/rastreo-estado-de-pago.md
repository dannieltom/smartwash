# Estado del pago en el rastreo público

**Proyecto:** SmartWash
**Historia relacionada:** HU17 (consultar el estado de la orden con su código)
**Código:** `backend/ordenes/serializers.py` (`estado_del_pago`, `ConsultaPublicaSerializer`) y `frontend/app/rastrear-pedido/linea-tiempo.tsx`

La línea de tiempo de "Rastrear pedido" (`GET /api/ordenes/consulta/{codigo}`) muestra el estado real del pago en la etapa **Pagada**.

## Estados

| Estado | Cuándo | Se muestra como | Fecha y hora |
|---|---|---|---|
| `pendiente` | No hay pagos registrados | "Pagada", pendiente (gris) | — |
| `parcial` | Lo abonado es mayor que 0 y menor que el total | "Pagada (parcial)" en ámbar, sin ✓, con "Abono: $X · Total: $Y" y debajo "Saldo pendiente: $Z" | La del **último abono** |
| `completo` | Lo abonado alcanza o supera el total | "Pagada completa", como etapa completada | La del **pago que completó el total** |

Un pago parcial no cuenta como etapa completada, así que los tramos de línea que lo tocan no se pintan.

## Montos

- **Total:** `Orden.valor_total`, lo que realmente se cobra. Es el mismo valor que usa el saldo del detalle interno: ya descuenta la fidelización, los descuentos por novedad y los servicios de prendas dañadas o perdidas, e incluye los servicios agregados por una novedad.
- **Abonado:** la suma de los pagos registrados (modelo `Pago`).
- Los dos van en **pesos enteros**.

## Qué no se expone

Es un endpoint público. La etapa de pago trae solo `estado_pago`, `abonado`, `total` y `fecha`. No incluye métodos de pago, referencias, notas, quién registró el pago ni ids. Fuera de la etapa de pago, la respuesta no trae montos.

La respuesta también trae `calificacion` (la satisfacción del cliente) y existe una consulta por cédula y correo: ver [rastreo-pqrs-satisfaccion.md](rastreo-pqrs-satisfaccion.md).
