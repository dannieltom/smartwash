# Rastreo por cédula, PQRS y calificación de satisfacción

**Proyecto:** SmartWash
**Historias relacionadas:** HU17 (rastreo público, ampliada), HU20 (PQRS, ampliada) y EP06 (Incidencias y postventa: satisfacción)
**Código:** `backend/ordenes/views.py` (`ConsultaPorDocumentoView`, `QuejaCreateView`), `backend/ordenes/serializers.py` (`QuejaSerializer`, `ConsultaPublicaSerializer`), `backend/satisfaccion/` y `frontend/app/{rastrear-pedido,pqrs,calificaciones}/`

Las tres rutas son públicas: el cliente no tiene cuenta. Por eso cada una tiene límite de intentos y expone solo datos no confidenciales.

## Endpoints

| Método y ruta | Quién | Qué hace |
|---|---|---|
| `GET /api/ordenes/consulta/{codigo}` | Público | Rastreo por código (sin cambios). Gana el campo `calificacion`. |
| `POST /api/ordenes/consulta-por-documento` | Público | Órdenes del cliente que demuestra su cédula y su correo. |
| `POST /api/pqrs` | Público | Petición, queja, reclamo o sugerencia. |
| `POST /api/ordenes/consulta/{codigo}/calificacion` | Público | Calificación de 1 a 5 estrellas de una orden entregada. |
| `GET /api/calificaciones` | Administrador y recepcionista | Promedio, total y lista de calificaciones. |

Los tres `POST` públicos exigen el token CSRF, igual que la recuperación de contraseña. El frontend lo envía solo desde `api()` en `lib/api.ts`.

## Rastreo por cédula y correo

`POST /api/ordenes/consulta-por-documento` con `{"documento": "...", "correo": "..."}`.

- **Por qué POST:** así la cédula y el correo no quedan en la URL, en el historial del navegador ni en los logs del servidor.
- **Verificación:** la cédula se normaliza igual que al registrar al cliente (sin espacios y sin distinguir mayúsculas). El correo se compara sin espacios a los lados y sin distinguir mayúsculas.
- **Mismo error en todos los fallos:** si la cédula no existe, si el correo no coincide o si el cliente no tiene correo registrado, la respuesta es siempre `404` con `{"detail": "No encontramos pedidos con esos datos. Revisa tu cédula y el correo que registraste."}`. Así nadie puede averiguar qué cédulas son clientes.
- **Sin correo, solo código:** un cliente sin correo registrado solo puede consultar con el código de su orden. Un correo vacío nunca coincide.

Respuesta `200`:

```json
{
  "activas": [
    {
      "codigo": "SW-ABCD2345",
      "estado": "En proceso",
      "total": 16500,
      "prendas": [{"cantidad": 3, "tipo_prenda": "Camisa", "servicios": ["Lavado", "Planchado"]}],
      "calificacion": null
    }
  ],
  "historial": []
}
```

- **`activas`:** todo lo que no está Entregada ni Cancelada, incluidas En espera y Con novedad.
- **`historial`:** las órdenes Entregada y Cancelada, todas.
- **Orden:** las dos listas van de la más reciente a la más antigua.
- **`total`:** `valor_total` en pesos enteros.
- **`prendas`:** agrupadas como en la bandeja, sin las prendas dañadas o perdidas.
- **`calificacion`:** `null` o solo `{"estrellas": n}`.

En la pantalla, la pestaña "Con cédula" muestra las órdenes activas en tarjetas. Cada tarjeta tiene "Ver seguimiento", que carga bajo demanda la misma línea de tiempo del rastreo por código. El botón "Historial de órdenes" despliega las entregadas y canceladas. Nada se guarda en la URL ni en el almacenamiento del navegador.

## PQRS

`POST /api/pqrs` recibe los cuatro tipos (`peticion`, `queja`, `reclamo`, `sugerencia`) y guarda el tipo en `Queja.tipo`.

| Tipo | Código de la orden | Estado de la orden |
|---|---|---|
| Petición | Obligatorio | Cualquiera |
| Queja | Obligatorio | Solo **Entregada** ("La queja solo aplica a ordenes ya entregadas.") |
| Reclamo | Obligatorio | Cualquiera |
| Sugerencia | Opcional; si se envía, la orden debe existir | Cualquiera |

- Sin código en un tipo que lo exige, la respuesta es `400` con `{"codigo_orden": ["Indica el codigo de la orden."]}`.
- Un código que no existe responde "No encontramos una orden con ese codigo. Revisa el comprobante."
- Las quejas registradas antes de este cambio quedan con tipo `queja` (migración `ordenes/0018`). Desde la `0018`, la orden es opcional.
- El formulario se puede prellenar por URL: `/pqrs?tipo=queja&codigo=SW-XXXX`. Solo acepta los cuatro tipos válidos e ignora cualquier otro valor.

## Calificación de satisfacción

`POST /api/ordenes/consulta/{codigo}/calificacion` con `{"estrellas": 1-5, "comentario": "..."}`. El comentario es opcional y tiene un máximo de 500 caracteres.

- **Solo órdenes entregadas:** si la orden no está entregada, la respuesta es `400` "Solo puedes calificar una orden ya entregada."
- **Una sola vez:** un segundo intento responde `400` "Esta orden ya fue calificada."
- **Código inexistente:** `404` con el mensaje de la consulta pública.
- **Inmutable:** la calificación no se edita ni se borra. Igual que `Pago` y `Comprobante`, el modelo lanza `PermissionDenied`.
- **App y migración propias:** vive en la app `satisfaccion`, con su migración `0001`.

Quién ve la calificación:

- **Rastreo por código:** `calificacion` llega como `null` o `{"estrellas", "comentario"}`.
- **Consulta por cédula:** solo `{"estrellas"}`.
- **Detalle interno de la orden:** `calificacion` llega como `null` o `{"estrellas", "comentario"}`.
- **`GET /api/calificaciones`:** admite `?desde=` y `?hasta=` opcionales, como `AAAA-MM-DD` (`hasta` incluye el día completo) o como fecha y hora ISO. Devuelve `{"promedio", "total", "calificaciones"}`, con el promedio redondeado a un decimal y la lista de la más reciente a la más antigua.

Si el cliente califica con 1 o 2 estrellas, la pantalla le ofrece "Presentar una queja", que lleva a `/pqrs?tipo=queja&codigo=...`.

## Límites de intentos

Están en `REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]` de `config/settings.py`. Superarlos responde `429`. Los intentos fallidos también cuentan.

| Alcance | Límite | Clave |
|---|---|---|
| `consulta-documento` | 20 por hora | IP |
| `consulta-documento-cuenta` | 10 por hora | Cédula normalizada |
| `pqrs` | 10 por hora | IP |
| `calificar-orden` | 20 por hora | IP |
| `calificar-orden-codigo` | 5 por hora | Código de la orden |

El límite por cédula frena a quien prueba correos contra una misma cédula aunque cambie de IP.

## Qué expone y qué no el rastreo público

**Expone:**

- el código y el estado;
- las etapas con sus fechas;
- la fecha estimada;
- el estado del pago con lo abonado y el total en pesos enteros (ver [rastreo-estado-de-pago.md](rastreo-estado-de-pago.md));
- en la consulta por cédula, el total y las prendas agrupadas;
- la calificación.

**No expone:**

- el nombre, teléfono, correo ni documento del cliente;
- ids internos;
- usuarios ni operarios;
- métodos o referencias de pago;
- notas ni motivos de cancelación o de novedad.
