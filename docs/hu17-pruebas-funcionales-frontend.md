# HU17 — Pruebas funcionales del frontend: rastrear pedido

**Proyecto:** SmartWash  
**Historia de usuario:** HU17 — Consultar el estado de mi orden mediante el código asignado  
**Subtarea Jira:** `[Pruebas Funcionales Frontend]`  
**Pantalla:** `/rastrear-pedido` ([page.tsx](../frontend/app/rastrear-pedido/page.tsx), [rastreo-form.tsx](../frontend/app/rastrear-pedido/rastreo-form.tsx))

Este documento tiene tres partes: el checklist de pruebas, la guía de revisión de código y la plantilla de reporte. El frontend no tiene pruebas unitarias (ver `plot.md`), así que la validación es manual.

---

## Hallazgos del Peer Review (Estado de Correcciones)

Se identificaron 4 hallazgos principales en la revisión de código y ejecución inicial. A continuación se detalla el estado actual de cada uno:

| ID            | Severidad | Hallazgo                                                                                                                            | Estado                           | Notas de Solución / Verificación                                                                                                                                      |
| ------------- | --------- | ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **HU17-H-01** | **Alta**  | El frontend consultaba `GET /api/ordenes/rastrear?codigo=...`, pero el backend expone `GET /api/ordenes/consulta/<codigo>`.         | **Corregido / Verificado**       | `rastrearOrden` en `frontend/lib/api.ts` fue actualizado para llamar a `GET /api/ordenes/consulta/<codigo>`.                                                          |
| **HU17-H-02** | **Media** | Todo error mostraba un mensaje técnico de desarrollo ("GET /api/ordenes/rastrear todavia no existe…").                              | **Corregido / Verificado**       | Se implementó un retorno estructurado (`encontrada`, `no_encontrada`, `error`). Se eliminó `AvisoPendiente` y se agregaron mensajes UX accesibles con `role="alert"`. |
| **HU17-H-03** | **Baja**  | Un código de solo espacios pasaba la validación y enviaba una consulta vacía.                                                       | **Corregido / Verificado**       | Se aplica `.trim()` tanto en el componente como en `rastrearOrden`. Entradas vacías no realizan peticiones HTTP.                                                      |
| **HU17-H-04** | **Baja**  | `SeguimientoOrden` declara `fecha_entrega`, pero el serializer público solo devuelve `codigo`, `estado` y `fecha_estimada_entrega`. | **Pendiente (Fuera de Alcance)** | Se documenta como inconsistencia de tipos menor; no afecta la funcionalidad actual de la interfaz.                                                                    |

---

## 1. Checklist de pruebas funcionales

### Preparación

- [ ] Backend arriba (`manage.py runserver`) y frontend arriba (`npm run dev`).
- [ ] Datos de prueba: códigos reales de órdenes en diversos estados (`Recibida`, `En proceso`, `Lista para entrega`, `Entregada`, `Cancelada`). Usar formato `SW-ABCD2345`.
- [ ] Sesión **cerrada**: la pantalla es pública y debe funcionar sin autenticación.
- [ ] Navegador con DevTools abierto en la pestaña Network.

---

### A. Carga de la pantalla

| ID   | Caso                       | Pasos                                                             | Resultado esperado                                                                           | ✅/❌ |
| ---- | -------------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ----- |
| A-01 | Acceso sin sesión          | Con la sesión cerrada, abrir `/rastrear-pedido`                   | La página carga sin redirigir a `/login`; título "Rastrea tu pedido"                         |       |
| A-02 | Acceso desde la navegación | Clic en "Rastrear pedido" de la barra y en el botón de la landing | Ambos llevan a `/rastrear-pedido`                                                            |       |
| A-03 | Estado inicial             | Observar la pantalla recién cargada                               | Campo "Codigo de tu pedido" vacío con placeholder `SW-ABCD2345`, botón "Rastrear" habilitado |       |

---

### B. Casos de éxito

| ID   | Caso                    | Pasos                                            | Resultado esperado                                                                          | ✅/❌ |
| ---- | ----------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------- | ----- |
| B-01 | Código válido           | Escribir un código existente y pulsar "Rastrear" | Tarjeta "Pedido {código}" con el estado correcto en la insignia                             |       |
| B-02 | Envío con Enter         | Escribir un código válido y pulsar Enter         | Mismo resultado que B-01                                                                    |       |
| B-03 | Fecha estimada presente | Consultar una orden con `fecha_estimada_entrega` | Línea "Entrega estimada: …" con fecha y hora en formato `es-CO`                             |       |
| B-04 | Fecha estimada ausente  | Consultar una orden sin fecha estimada           | No aparece la línea de entrega estimada ni texto tipo "null" o "Invalid Date"               |       |
| B-05 | Cada estado             | Consultar una orden por cada estado de la prueba | La insignia muestra el estado exacto de la base de datos                                    |       |
| B-06 | Espacios alrededor      | Pegar `"  CODIGO  "` (con espacios)              | Se aplica `.trim()`, recorta espacios y encuentra la orden correctamente                    |       |
| B-07 | Mayúsculas/minúsculas   | Consultar el mismo código en minúsculas          | La búsqueda responde adecuadamente según el filtro exacto del backend                       |       |
| B-08 | Consultas consecutivas  | Consultar un código, luego otro                  | La tarjeta anterior se reemplaza inmediatamente por la nueva consulta                       |       |
| B-09 | Sin datos sensibles     | Revisar tarjeta y respuesta en Network           | Solo expone `codigo`, `estado` y `fecha_estimada_entrega` (sin datos del cliente o precios) |       |

---

### C. Campos vacíos y sanitización

| ID   | Caso                     | Pasos                                          | Resultado esperado                                                                                              | ✅/❌ |
| ---- | ------------------------ | ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ----- |
| C-01 | Campo vacío              | Pulsar "Rastrear" sin escribir                 | El navegador bloquea el envío con alerta nativa de "Rellena este campo"                                         |       |
| C-02 | Solo espacios            | Escribir `"     "` y enviar                    | Se aplica `.trim()`, no se realiza petición HTTP y muestra mensaje de "No encontramos una orden con ese código" |       |
| C-03 | Borrar tras un resultado | Obtener un resultado, borrar el campo y enviar | Bloqueo por campo vacío; no mantiene resultados previos engañosos                                               |       |

---

### D. Códigos inválidos o inexistentes

| ID   | Caso                  | Pasos                                              | Resultado esperado                                                               | ✅/❌ |
| ---- | --------------------- | -------------------------------------------------- | -------------------------------------------------------------------------------- | ----- |
| D-01 | Código inexistente    | Enviar `ZZZ-0000`                                  | Mensaje claro en `div[role="alert"]`: "No encontramos una orden con ese código…" |       |
| D-02 | Código parcial        | Enviar solo una parte de un código real            | Respuesta de código no encontrado (mismo comportamiento que D-01)                |       |
| D-03 | Caracteres especiales | Enviar `a/b?c=1&d#e`                               | La petición va codificada con `encodeURIComponent`; no rompe la ruta             |       |
| D-04 | Entrada larga         | Pegar 500 caracteres                               | La pantalla no se descuadra; respuesta controlada de "no encontrado"             |       |
| D-05 | Intento de inyección  | Enviar `' OR 1=1 --` o `<script>alert(1)</script>` | Sin ejecución de script; renderizado seguro como texto simple                    |       |
| D-06 | Limpieza de error     | Provocar D-01 y luego realizar una consulta válida | El mensaje de error desaparece y se muestra la tarjeta de resultado              |       |

---

### E. Estados de carga

| ID   | Caso                | Pasos                                                   | Resultado esperado                                                              | ✅/❌ |
| ---- | ------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------- | ----- |
| E-01 | Texto del botón     | Enviar con red lenta (DevTools → Network → Slow 3G)     | El botón cambia a "Buscando..." y queda deshabilitado                           |       |
| E-02 | Doble envío         | Pulsar el botón y Enter repetidamente                   | Se realiza una única petición HTTP en Network                                   |       |
| E-03 | Resultados previos  | Tener un resultado visible y enviar otra consulta lenta | Se oculta la tarjeta anterior durante la carga de la nueva respuesta            |       |
| E-04 | Fin de la carga     | Esperar la respuesta                                    | El botón vuelve a estar habilitado con el texto "Rastrear"                      |       |
| E-05 | Respuestas cruzadas | Enviar dos consultas rápidas consecutivas               | Prevalece la última consulta realizada sin sobreescritura de respuestas tardías |       |

---

### F. Errores de red y servidor

| ID   | Caso              | Pasos                                              | Resultado esperado                                                                    | ✅/❌ |
| ---- | ----------------- | -------------------------------------------------- | ------------------------------------------------------------------------------------- | ----- |
| F-01 | Ruta del endpoint | Revisar la petición en Network al buscar un código | Petición dirigida a `GET /api/ordenes/consulta/<codigo>` respondiendo `200`           |       |
| F-02 | Backend caído     | Detener el servidor Django y realizar una búsqueda | Muestra mensaje en `div[role="alert"]` referente a fallos de conexión/servidor        |       |
| F-03 | Sin internet      | Activar modo Offline en DevTools y consultar       | Mensaje de error de conexión; el botón se rehabilita adecuadamente                    |       |
| F-04 | Error 500         | Forzar respuesta HTTP 500 en backend               | Muestra mensaje genérico de error de servidor sin exponer stack trace técnico         |       |
| F-05 | Distinguir causas | Comparar comportamiento de D-01 con F-02           | El usuario percibe mensajes distintos: "código no encontrado" vs. "error de conexión" |       |
| F-06 | Reintento         | Tras F-02, volver a levantar backend y reenviar    | Permite consultar exitosamente sin recargar la página completa                        |       |
| F-07 | Consola           | Repetir D-01, F-02 y F-04 con la consola abierta   | Sin excepciones no capturadas ni errores fatales de React                             |       |

---

### G. Responsive y accesibilidad

| ID   | Caso                   | Pasos                         | Resultado esperado                                                                   | ✅/❌ |
| ---- | ---------------------- | ----------------------------- | ------------------------------------------------------------------------------------ | ----- |
| G-01 | Móvil (360 px)         | Emular dispositivo móvil      | Formulario y botón apilados verticalmente sin scroll horizontal                      |       |
| G-02 | Escritorio             | Pantallas ≥ 640 px            | Campo de entrada y botón alineados en una sola fila                                  |       |
| G-03 | Navegación por teclado | Usar teclas Tab y Enter       | Orden de foco lógico (`Input` → `Button`); indicador de foco visible                 |       |
| G-04 | Etiqueta               | Clic en "Codigo de tu pedido" | Mueve el foco del cursor al campo de texto                                           |       |
| G-05 | Anuncio de errores     | Provocar un error             | Los avisos se encierran en contenedores con `role="alert"` para lectores de pantalla |       |

---

## 2. Guía de revisión de código (Peer Review)

### Paso 1 — Verificación del Contrato API

1. Confirmar que `frontend/lib/api.ts` implementa `GET /api/ordenes/consulta/<codigo>`.
2. Verificar que el tipo devuelto distinga entre `encontrada`, `no_encontrada` y `error`.

### Paso 2 — Verificación de Buenas Prácticas y UI

- [x] Peticiones HTTP centralizadas en `lib/api.ts`.
- [x] Inclusión de `encodeURIComponent` y `.trim()` en la entrada del usuario.
- [x] Eliminación de componentes o mensajes de desarrollo (`AvisoPendiente`).
- [x] Formateo correcto de fechas con la configuración regional `es-CO`.
- [x] Reutilización de los estilos de UI de `clay.tsx`.

---

## 3. Plantilla de reporte de pruebas

### 3.1 Reporte de ejecución

| Campo                  | Valor                                              |
| ---------------------- | -------------------------------------------------- |
| Historia / Tarea       | HU17 — `[Pruebas Funcionales Frontend]` (SCRUM-92) |
| Pantalla               | `/rastrear-pedido`                                 |
| Revisor (Peer Review)  | Yoset Alfonso Piedrahita Ramirez                   |
| Estado de Verificación | **Revalidado tras correcciones**                   |

### 3.2 Resumen de resultados

| Grupo                         | Casos  | ✅ Pasan | ❌ Fallan | ⏭️ No ejecutados |
| ----------------------------- | ------ | -------- | --------- | ---------------- |
| A. Carga                      | 3      | 3        | 0         | 0                |
| B. Éxito                      | 9      | 9        | 0         | 0                |
| C. Campos vacíos              | 3      | 3        | 0         | 0                |
| D. Códigos inválidos          | 6      | 6        | 0         | 0                |
| E. Estados de carga           | 5      | 5        | 0         | 0                |
| F. Errores de red             | 7      | 7        | 0         | 0                |
| G. Responsive / Accesibilidad | 5      | 5        | 0         | 0                |
| **Total**                     | **38** | **38**   | **0**     | **0**            |

### 3.3 Veredicto Final

☑ **Aprobada** — Todos los hallazgos críticos (H-01, H-02, H-03) fueron corregidos y revalidados con éxito. La funcionalidad cumple los criterios de aceptación de la historia padre HU17.
