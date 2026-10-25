# Diseño P02 — Agenda visual adaptable, asistencia e historial

Fecha: 23-10-2026. Estado: implementación P02. Alcance: agenda comercial día/semana/mes,
estados operativos, observaciones internas e historial. No incluye ventas, inventario, RAG,
WhatsApp, campañas, OAuth, workers de sincronización ni despliegue.

## 1. Componentes y decisiones

- **Sin componente de calendario de terceros.** Se evaluó **FullCalendar 7.1.3**
  (fuente oficial: https://fullcalendar.io/license, consultada el 23-10-2026): el bundle
  Standard y los plugins no premium son **MIT**; los plugins premium (resource/timeline/scheduler)
  requieren **licencia comercial** o AGPLv3 para proyectos compatibles. No se incorpora porque:
  (a) no hay navegador/entorno de compilación para verificar el paquete vendido en esta entrega,
  (b) añadiría cientos de KB y riesgo de CSP sin poder validarlo, y (c) el alcance básico no exige
  columnas por recurso: filtros y etiquetas de profesional cubren hasta tres profesionales. No se
  incorpora ninguna función premium ni se inventa una licencia. Se implementa un módulo propio,
  local y versionado (`crm/static/agenda.js`, `crm/static/agenda.css`) sin CDN ni conexión externa.
  Licencia del módulo: código propio del repositorio. Decisión revisable si en una fase posterior
  se adopta un componente verificado.
- Flask/Jinja, SQLite y los servicios de P01 se conservan. La agenda usa JavaScript local
  (sin `eval` ni inline) y la CSP se ajusta a `script-src 'self'`.
- El acento es configurable por el instalador con `CRM_ACCENT` (hex validado) y se sirve en
  `/theme.css` como hoja de estilo del mismo origen; no hay estilos inline.

## 2. Esquema (migración v2)

Se mantiene `status` (`active`/`cancelled`) por compatibilidad y se añade el ciclo operativo:

- `crm_appointments.operational_status TEXT NOT NULL DEFAULT 'pending'`
  valores: `pending`, `confirmed`, `attended`, `no_show`, `cancelled`.
- `crm_appointments.row_version INTEGER NOT NULL DEFAULT 1` para control optimista.
- `crm_appointment_notes(id, appointment_id, author_user_id, body, created_at)`.
- `crm_appointment_history(id, appointment_id, action, actor_user_id, actor_label,
  created_at, before_json, after_json, reason, note_id)`.

Invariantes (en un único servicio, `crm/reservation_service.py`):

- `operational_status='cancelled'` ⇔ `status='cancelled'`; cualquier otro estado operativo
  mantiene `status='active'` y ocupa su intervalo.
- Citas P01 `active` se adoptan como `pending`; `cancelled` como `cancelled`.
  No se infiere asistencia de citas vencidas.
- `origin='demo'` se preserva en altas, reprogramaciones, transiciones y cancelaciones.
- Reprogramar conserva `id`, `event_id`, `origin`, y reinicia a `pending`.
- Historial/nota/cambio se escriben en la misma transacción; si falla la auditoría (FK),
  se revierte todo.

## 3. Estados y transiciones

| Estado actual | Acción normal | Requisito temporal | Resultado |
|---|---|---|---|
| pending | confirmar | antes del inicio | confirmed |
| pending/confirmed | reprogramar | antes del inicio | pending (nueva hora) |
| pending/confirmed | cancelar | antes del inicio | cancelled |
| pending/confirmed | atendida / no asistió | desde el fin | attended / no_show |
| confirmed | confirmar de nuevo | — | idempotente (sin historial nuevo) |
| cancelled | cancelar de nuevo | — | idempotente |
| attended/no_show | misma acción repetida | — | idempotente |
| cancelled | reprogramar/atender/cambiar | — | prohibido (crear otra cita) |
| cualquiera no cancelada | corrección admin | — | nuevo estado con motivo obligatorio |
| cancelled | corrección admin a no cancelada | — | prohibido (sin resurrección) |

«Pendiente de cierre» es una condición calculada (`pending|confirmed` y `ahora >= fin`); el
reloj no cambia el estado. Durante la cita sólo se permiten observaciones. El bot no recibe
acciones nuevas. `admin` y `user` operan la agenda; sólo `admin` corrige excepcionalmente.

## 4. Contrato de endpoints

Todos requieren sesión; las mutaciones requieren CSRF (`csrf` de formulario o cabecera
`X-CSRF-Token`) y validación de servidor. Fechas de entrada: ISO; sin offset se interpretan en
la zona del negocio y se validan contra huecos/ambigüedades DST (P01B). La salida incluye UTC y
etiquetas locales; el navegador nunca decide la zona.

- `GET /api/agenda?view=day|week|month&date=YYYY-MM-DD&professional=<id|''>&status=<estado|''>&cancelled=0|1`
  Calcula el rango visible en la zona del negocio (día, semana lunes-domingo, mes en rejilla de
  6 semanas; máximo 42 días). Devuelve profesionales, rango y citas que **atraviesan** el rango,
  sin observaciones ni historial. Límite de filas 1000; rango excesivo → 400.
- `GET /api/appointments/<id>`: detalle autenticado con `operational_status`, `sync_status`,
  `allowed_actions`, `pending_closure`, notas e historial.
- `POST /api/appointments`: alta (JSON). Crea en `pending` y registra historial de creación.
- `POST /api/appointments/<id>/transition`: `{action, version, reason?, start?, end?, target?}`.
  Acciones: `confirm`, `reprogram`, `cancel`, `attend`, `no_show`, `admin_correct`.
  `version` obligatoria; versión obsoleta → 409 `version_conflict` sin cambios.
- `POST /api/appointments/<id>/notes`: `{body}` autenticado; crea nota + entrada de historial
  en una transacción.
- Se conservan `POST /appointments` (alta/reprogramación de formulario) y
  `POST /appointments/<id>/cancel` por compatibilidad; la reprogramación de formulario exige
  `version`.
- Errores JSON: `{ "error": {"code": ..., "message": ...} }` con 400/401/403/404/409.
  Conflicto de horario/edición es distinguible de error interno. Nunca se muta con GET.

## 5. Permisos y privacidad

- Lectura y operación: usuario con sesión (admin o user). Corrección excepcional: sólo admin.
- Sin aislamiento por doctor en P02 (no existe asociación usuario-profesional).
- El bot conserva su contrato de guardado local; no obtiene notas ni transiciones.
- Observaciones e historial no salen en el listado general, ni a Google, ni al bot/WhatsApp.
  No se registran en logs técnicos.
- Títulos/notas se renderizan con `textContent`; JSON escapa; sin HTML crudo.

## 6. Sincronización (ajuste mínimo)

- La descarga de Google no toca `operational_status`, notas ni historial; no resucita citas
  canceladas localmente.
- Si un evento desaparece de Google y la cita local está `attended`/`no_show`, no se cambia el
  estado: se marca `sync_status='error'` con un mensaje de revisión y se añade historial de
  cancelación externa (actor sistema). La interfaz muestra el conflicto separado del estado.
- `origin='demo'` sigue excluido del envío.
- Red, reintentos y resolución completa de conflictos corresponden a P03.

## 7. Interfaz y accesibilidad

- Encabezado Agenda, período, Hoy, anterior/siguiente, Día/Semana/Mes, Nueva cita y zona.
- Filtros: profesional (Todos/cada uno), estado, mostrar canceladas.
- Semana inicial en PC/tablet, día en móvil; la vista se recuerda en `sessionStorage` y no cambia
  al redimensionar. Las tres vistas están disponibles en todos los tamaños.
- Día: rejilla horaria con carriles por profesional cuando el filtro es «Todos».
  Semana: rejilla de 7 días con horas; bloques posicionados y apilados si se solapan.
  Mes: rejilla de 6 semanas, chips compactos y «ver más» que abre el día.
- Celda libre abre alta con fecha/hora/profesional preseleccionados cuando procede; en mes se
  pide hora explícita. Cita abre panel lateral (escritorio) o pantalla completa (móvil).
- Diálogos nativos `<dialog>`: foco contenido, Escape, devolución de foco al origen.
- Estados de carga, vacío, error, conflicto y sesión vencida. Un conflicto conserva los datos
  del formulario.
- Etiquetas de estado/profesional con texto e indicador, no sólo color. Objetivos táctiles
  ~44 px. Sin hover/drag/doble clic como requisito. Contraste y zoom 200 %.
- Sin desbordamiento horizontal de la página en móvil.

## 8. Pruebas y evidencia

- Migración v1→v2 (activas/canceladas/demo, FK, idempotencia, rollback inducido).
- Tabla de transiciones con reloj controlado; idempotencia; admin vs user/bot.
- Conflictos y concurrencia web/bot; reprogramación conserva identidad; versión obsoleta.
- Historial/notas persisten y revierten si falla la auditoría; no salen en listado/Google/bot.
- Google simulado: preserva asistencia/notas, trata cancelación externa, excluye demo.
- Endpoints: sin sesión, CSRF, permisos, entradas inválidas, XSS, rango excesivo, filtros.
- Rangos medianoche/mes/DST; cliente con otra zona (el servidor usa la del negocio).
- Recorrido real con Playwright y capturas 360/768/1440, teclado y zoom 200 %, consola/CSP.
  Los datos son ficticios; nunca se usa `analitica.db`.

## 9. Resultado de la verificación (23-10-2026)

- Suite completa del workspace: 74 pruebas (P01/P01B/P02/calendario/demo) — todas pasan.
- Entorno mínimo `.venv-verify` (sin Pydantic/IA/Qdrant/Google): 69 pruebas — todas pasan.
- Chromium 140.0.7339.16 vía Playwright: día/semana/mes a 360/768/1440, filtros, alta,
  conflicto, nota/historial, reprogramación, cancelación, recarga, asistencia, «Ver más»,
  teclado (Enter/Escape y retorno de foco) y zoom 200 % sin desbordamiento de página.
- Consola del navegador: 0 errores no esperados. Recursos HTTP >= 400 no esperados: 0.
  El 409 del solape es esperado y se registra aparte.
- Capturas reales y resumen en `docs/producto/evidencias/p02/`.
- La validación estética/contraste fino y la aprobación quedan a cargo de Codex.

## 10. Correcciones P02B (revisión de Codex)

### Control de versión y sincronización

- Toda modificación **externa relevante** (título, inicio, fin, cancelación) incrementa
  `row_version` y escribe una entrada de historial (`cambio_externo`,
  `cancelacion_externa`) en la misma transacción. Una descarga idéntica no modifica la
  versión ni el historial (comparación de instantes tolerante a microsegundos).
- Las rutas humanas de reprogramación y cancelación exigen `version`: servicio, API,
  formulario de reprogramación y la ruta antigua `/appointments/<id>/cancel`. Sin versión
  o con versión obsoleta se devuelve conflicto y no se modifica la cita (la repetición de
  una cancelación ya cancelada sigue siendo idempotente).
- Nuevo estado de sincronización `review`: conflicto que requiere revisión humana y queda
  **excluido** de la cola de reenvío automático. Se distingue de `error` (fallo de
  transporte reintentable). Una cancelación externa posterior a asistencia no borra el
  estado ni las notas, no se reenvía y no duplica historial en sincronizaciones
  consecutivas. Una acción humana deliberada (reprogramar, cancelar, corregir) pasa la cita
  a `pending` para un reenvío autorizado.
- La interfaz muestra «Google: revisión»/«Error de sincronización» separado del estado
  operativo.

### Visualización

- La rejilla calcula su rango dinámicamente a partir de las citas visibles (mínimo 07–20,
  ampliable a 00–24). Las citas de 05–06, 21–22 y las que cruzan medianoche quedan dentro
  de la rejilla, sin recortes. Semana y Día segmentan por intersección real con cada día.
- En Día/Todos se muestran también profesionales inactivos que tengan citas; su carril es
  de sólo lectura (sin celdas de alta). El formulario sólo ofrece profesionales activos.
- Mes representa la intersección de cada cita con cada día y marca continuaciones
  (`↪`/`↦`, clases `continuation-start`/`continuation-end`, texto accesible).
- El formulario representa el intervalo completo con cuatro campos: `start_date`,
  `start_time`, `end_date`, `end_time`. Al abrir una cita existente se conservan ambos
  extremos (incluida una duración de 49 h o más) y no se acorta al guardar. Se permiten
  horas de reloj iguales cuando las fechas hacen válido el intervalo (24 h); se rechaza
  fin igual al inicio en el mismo instante o fin anterior. La comparación de pared se hace
  en el navegador y el servidor valida fin>inicio y DST en la zona del negocio.
- El alta desde Mes conserva la fecha pulsada en inicio y fin, exige horas explícitas y no
  inventa una hora. La fecha final queda visible y editable; no hay cambios silenciosos de
  día. La celda de 23:00 preselecciona fin 00:00 del día siguiente (nunca 24:00 en un
  `input type="time"`).
- Un token de petición descarta respuestas antiguas de vista/filtros que lleguen después
  de la última solicitada.

### Presentación

- Cabecera y controles móviles compactos (filtros en dos columnas, botones reducidos) para
  que la agenda aparezca en la primera pantalla; se conservan las acciones accesibles.
- El historial traduce los cambios a frases legibles (Detalle/Inicio/Fin/Estado/Situación/
  Sincronización/Motivo) con fechas de la zona del negocio; no muestra JSON crudo.
- Se mejora el contraste de horas (6.67:1) y flechas (10.04:1) y el objetivo táctil de Mes
  (44×44 px). Recursos locales y CSP `script-src 'self'` se mantienen.

### Evidencia P02B

- Pruebas nuevas: `tests/test_p02b.py` (versionado externo y edición obsoleta; cancelación
  sin versión/obsoleta; revisión persistente en dos sincronizaciones; reintento legítimo;
  API devuelve horarios extremos, medianoche e inactivos).
- Navegador real (Chromium/Playwright): día/semana/mes con 05–06, 21–22, 23–01, evento que
  empieza antes del rango e inactivo; altas desde Mes; carrera de vistas; historial legible;
  móvil 360; teclado; zoom 200 %; consola/CSP. Capturas en
  `docs/producto/evidencias/p02b/`.

## 11. Corrección P02C — fechas completas y pruebas estables

- El formulario usa `start_date` + `start_time` y `end_date` + `end_time`. La
  reprogramación conserva ambos extremos; una cita de 49 h abre con fecha final a dos
  días y se guarda sin acortarse. Una cita de 24 h conserva la misma hora en días
  distintos. Se rechaza fin igual en el mismo instante o anterior; el servidor mantiene
  la validación fin>inicio y DST.
- Celda de 23:00: inicio 23:00 y fin 00:00 con `end_date` del día siguiente; nunca se
  escribe 24:00 en el input. Mes conserva la fecha en ambos extremos y pide horas.
- `tests/test_p02c.py` cubre intervalos de 49 h, 24 h con igual hora, 23:00–00:00,
  23:00–01:00, fin inválido y filtro por día con una cita que cruza medianoche.
- `test_api_lifecycle_filters_and_security` usa una hora local fija (10:00) en una fecha
  futura para que +2 h no cambie de día; el caso de medianoche queda en prueba separada.
- `tools/evidencia_p02c.py` captura el payload real del navegador (`POST` de alta y
  transición), verifica la persistencia vía respuesta/detalle y guarda formularios y
  detalles en 360/1440. Evidencia en `docs/producto/evidencias/p02c/`.
