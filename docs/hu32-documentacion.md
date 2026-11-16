# HU32 — Recordatorios de órdenes no reclamadas y comunicaciones promocionales

**Historia de usuario:** HU32 — Enviar recordatorios de órdenes no reclamadas y comunicaciones promocionales
**Subtarea Jira:** SCRUM-116 `[Desarrollo Backend]`

## 1. Backend

**Autor:** Juan Daniel Torres Morales

### Resumen

Un proceso envía por correo dos tipos de comunicación: un recordatorio a quien tiene una orden lista sin recoger y la promoción vigente (HU28) a los clientes de sus segmentos. Los criterios de aceptación de Jira son copia de los de HU31, así que el alcance sale del título: el aviso de "orden lista" de HU31 se mantiene y no se toca.

### Decisiones tomadas

- **Recordatorio de orden no reclamada.** La orden sigue "Lista para entrega" y lleva al menos N días así, contados desde la última vez que quedó lista (si vuelve a reproceso, el conteo se reinicia). N sale de `DIAS_RECORDATORIO_ORDEN_LISTA` (3 por defecto).
- **Sin spam.** Se repite cada N días y se detiene en 3 recordatorios por orden (`MAX_RECORDATORIOS`). Cada envío queda en el historial de la orden como notificación, igual que el aviso de HU31.
- **Promoción comunicada una sola vez por cliente** (`ComunicacionPromocional`, única por cliente y promoción). Se envía solo si la promoción está activa, vigente hoy y el cliente es de uno de sus segmentos. Quien se une al segmento después la recibe en la siguiente corrida.
- **Solo se registra lo enviado.** Si el correo falla, queda en el log y se reintenta en la siguiente corrida; un fallo no frena a los demás envíos.
- **Sin correo no se envía** y se cuenta en `sin_correo` para avisar por otro medio.
- **Error del sistema (escenario 2).** Si la base falla, se registra el error, la API responde `503` y no se aplica nada más.

### Cómo se dispara

```bash
python manage.py enviar_comunicaciones
```

o `POST /api/fidelizacion/comunicaciones/enviar` (solo administrador), que responde `{recordatorios: {enviados, sin_correo, fallidos}, promociones: {...}}`.

### Pruebas

`fidelizacion/tests.py` (`RecordatoriosOrdenesTests`, `ComunicacionesPromocionalesTests`): umbral de días, repetición y tope, reinicio por reproceso, sin correo, fallos de envío y de base, permisos y comando.

### Pendientes

- Programar el comando de forma periódica en el despliegue.
- HU33 (registro de todas las comunicaciones) podría unificar el historial de la orden con `ComunicacionPromocional`.
- Los criterios de aceptación de SCRUM-47 siguen sin reescribirse en Jira.
