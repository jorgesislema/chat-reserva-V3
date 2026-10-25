# Reporte P02 — Agenda visual adaptable, asistencia e historial

Fecha: 23-10-2026. Rama: `actualisacion-dependencias`. Implementación: DeepSeek.
Revisión/aceptación: Codex. Estado de la entrega P02: **devuelta por Codex**
(`REVISION_P02_CODEX.md`). Estado tras P02B: **devuelta** (`REVISION_P02B_CODEX.md`).
Estado tras P02C: **aceptada** (`REVISION_P02C_CODEX.md`); P02 queda aceptada.

Sin commit, push ni despliegue. No se abrió `.env`, no se tocaron `analitica.db`, `.venv-crm`,
usuarios reales ni servicios externos. Las pruebas y la evidencia usan datos ficticios y bases
temporales.

## Objetivo y alcance

Convertir la agenda en la pantalla comercial principal (día/semana/mes, filtros, alta,
reprogramación, cancelación, asistencia, observaciones e historial) conservando Flask/Jinja,
SQLite y el servicio de reservas de P01. No se implementaron ventas, inventario, RAG, chat,
WhatsApp, campañas, OAuth, workers ni despliegue.

## Decisiones y desviaciones

1. **Calendario propio, sin componente de terceros.** Se evaluó **FullCalendar 7.1.3**
   (https://fullcalendar.io/license, consultada el 23-10-2026): bundle Standard/plugins no premium
   **MIT**; premium (resource/timeline/scheduler) requiere licencia comercial o AGPLv3. No se
   vendió/incorporó porque no se podía verificar el paquete completo en navegador para distribución
   en esta entrega, añadía peso y riesgo de CSP, y el alcance básico no exige columnas por recurso.
   Se implementó un módulo local (`crm/static/agenda.js` + `agenda.css`), sin CDN, sin función
   premium y sin inventar una licencia. Decisión revisable si una fase posterior adopta un
   componente verificado.
2. **Modelo de estados compatible.** Se conserva `status` (`active`/`cancelled`) y se añade
   `operational_status` (`pending`, `confirmed`, `attended`, `no_show`, `cancelled`).
   Invariantes en un único servicio (`crm/reservation_service.py`):
   cancelada ⇔ ambos cancelados; el resto mantiene `status='active'` y ocupa su intervalo.
   Citas P01 `active` se adoptan como `pending`; `cancelled` como `cancelled`. No se infiere
   asistencia de vencidas.
3. **Versión optimista.** `row_version` se incrementa en cada cambio de la cita. La API y el
   formulario de reprogramación exigen `version`; una versión obsoleta devuelve 409
   `version_conflict` sin cambios. Las notas no incrementan la versión (no sobrescriben estado).
4. **Mes estable de 6 semanas (42 días).** Evita saltos de altura al navegar; el rango máximo
   del servicio es 62 días.
5. **Semana con una columna por día y apilado de solapes.** Día usa carriles por profesional
   cuando el filtro es «Todos». No hay arrastrar/soltar; reprogramar es por formulario.
6. **CSP mínima.** `script-src 'self'`, sin `unsafe-inline` ni `unsafe-eval`; estilos sólo del
   mismo origen. El acento se sirve en `/theme.css` desde `CRM_ACCENT` validado como hex, sin
   estilos inline. Las pruebas existentes de CSP se actualizaron y justifican el cambio.
7. **Sincronización: ajustes mínimos.** La descarga no resucita canceladas ni borra
   `operational_status`/notas. Si un evento desaparece de Google y la cita está
   `attended`/`no_show`, se conserva la asistencia, se marca `sync_status='error'` y se añade
   historial de cancelación externa; la interfaz muestra el conflicto separado del estado.
   Red/reintentos y resolución completa siguen en P03.
8. **El bot no recibe acciones nuevas.** Conserva su contrato de guardado local y no accede a
   notas, historial ni correcciones.

## Archivos afectados

| Archivo | Cambio |
|---|---|
| `crm/store.py` | Migración v2: `operational_status`, `row_version`, tablas de notas e historial, backfill de canceladas. |
| `crm/reservation_service.py` | Ciclo operativo, transiciones, versión, notas, historial, listado y detalle; reprogramación con motivo. |
| `crm/agenda_time.py` | **Nuevo.** Rangos día/semana/mes en zona del negocio, etiquetas y DST. |
| `crm/app.py` | Config `CRM_ACCENT`, CSP, CSRF por cabecera, `/theme.css`, API de agenda, rutas de formulario con versión/motivo. |
| `crm/calendar.py` | Preservación de asistencia/notas y conflicto de cancelación externa; no resucitar canceladas. |
| `crm/templates/base.html` | Meta CSRF, `theme.css`, `agenda.css`, enlace de salto, bloque de scripts. |
| `crm/templates/dashboard.html` | La pestaña Agenda incluye el parcial; se retiró la tabla monolítica. |
| `crm/templates/agenda.html` | **Nuevo.** Parcial de agenda, diálogos, filtros y formularios accesibles. |
| `crm/static/agenda.css`, `agenda.js` | **Nuevos.** Diseño adaptable y lógica local de día/semana/mes y panel. |
| `tests/test_crm.py` | CSP actualizada (script-src 'self') y reprogramación con versión. |
| `tests/test_p01b.py`, `tests/test_reservation_service.py` | Expectativas de versiones de esquema `[1,2]` por la migración v2. |
| `tests/test_p02.py` | **Nuevo.** 17 pruebas de migración, transiciones, API, historial, Google simulado y rangos. |
| `tools/evidencia_p02.py` | **Nuevo.** Recorrido real con Playwright y capturas ficticias. |
| `docs/producto/DISENO_P02.md`, `REPORTE_P02.md` | Diseño y este reporte. |
| `docs/producto/evidencias/p02/` | Capturas reales 360/768/1440, zoom 200 %, consola y resumen. |
| `README.md`, `docs/producto/ESTADO.md` | Instrucciones, pruebas, migración y continuidad. |

Cambios preexistentes conservados: `README.md`, `crm/calendar.py`, `requirements.txt`,
`seed_demo_crm.py`, `tests/test_demo_seed.py`. No se revirtió ninguno.

## Migración v2 y respaldo

- Versión 2 posterior a v1, sin editar la migración publicada; se ejecuta en la transacción
  atómica del ejecutor de P01B (sin `executescript` ni commits internos).
- Añade `operational_status` (default `pending`), `row_version` (default 1), backfill
  `operational_status='cancelled' WHERE status='cancelled'`, y crea
  `crm_appointment_notes` / `crm_appointment_history` con índices.
- Preserva filas, identidades, índices, FKs, `origin='demo'` y `PRAGMA user_version` legacy.
- Probada desde esquema P01 con citas activas/canceladas/demo, repetición idempotente y fallo
  inducido con rollback y reintento. Una base nueva y una adoptada terminan con el mismo esquema.
- Respaldo/restauración: se mantiene la guía de P01B (respaldo consistente con API `backup`,
  procesos detenidos y sin WAL/SHM de otra generación). Ensayo ficticio cubierto por
  `tests/test_p01b.py`.

## Contrato de API

- `GET /api/agenda?view=day|week|month&date=AAAA-MM-DD&professional=&status=&cancelled=0|1`:
  rango visible en zona del negocio, citas que lo atraviesan, sin notas; máx. 1000 filas y
  42/62 días.
- `GET /api/appointments/<id>`: detalle autenticado con estado operativo, sincronización,
  `pending_closure`, acciones permitidas, notas e historial.
- `POST /api/appointments`: alta en `pending` con historial de creación.
- `POST /api/appointments/<id>/transition`: `confirm`, `reprogram`, `cancel`, `attend`,
  `no_show`, `admin_correct`; exige `version`. 409 para versión/solape/tiempo; 403 para
  corrección no admin.
- `POST /api/appointments/<id>/notes`: nota interna + historial en la misma transacción.
- Se conservan las rutas de formulario `/appointments` y `/appointments/<id>/cancel`; la
  reprogramación de formulario exige `version`.
- CSRF por `csrf` de formulario o cabecera `X-CSRF-Token`; sesión requerida; sin mutaciones GET;
  errores JSON `{error:{code,message}}`.

## Evidencia ejecutada (real, no histórica)

```powershell
# Suite completa del workspace (P01, P01B, P02, calendario y demo)
python -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_calendar_tool.py tests/test_demo_seed.py -q
# 74 passed

# Entorno mínimo (sin Pydantic/IA/Qdrant/Google), basetemp nuevo
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/p02-verify-2
# 69 passed

# Recorrido real en Chromium con datos ficticios
python tools/evidencia_p02.py
# failures: []; zoom 200 %: sin desbordamiento; consola no esperada: 0; recursos >=400 no esperados: 0
```

El recorrido automatizado cubrió: login, día/semana/mes a 360/768/1440, filtro por profesional,
alta desde hueco, conflicto con conservación del formulario, detalle, nota, historial,
reprogramación, cancelación, vista de canceladas, recarga con persistencia de la nota, asistencia
de una cita vencida, «Ver más» del mes y teclado (Enter/Escape con retorno de foco). Chromium
140.0.7339.16 (Playwright del entorno de verificación; no es dependencia del producto).

Capturas reales en `docs/producto/evidencias/p02/`:
`day-360/768/1440.png`, `week-360/768/1440.png`, `month-360/768/1440.png`,
`zoom-200-1440.png`, más `consola.json` y `RESUMEN.md`.

El 409 del solape aparece como mensaje de consola del navegador y se registra como conflicto
esperado; no se contabiliza como fallo.

## Pruebas nuevas (`tests/test_p02.py`, 17)

Migración v1→v2 con activas/canceladas/demo, FK, `user_version=5`, idempotencia y rollback con
reintento; tabla de transiciones con reloj controlado (futuro, durante, pasado, cancelada,
idempotencia, admin vs user/bot, sin resurrección); versión obsoleta; API (alta, confirmación,
filtros, solape, reprogramación con identidad, 401/400/403, fecha inválida, vista inválida,
rango excesivo); notas/historial persistentes y rollback por FK; notas fuera de Google y del bot;
Google simulado (asistencia/notas preservadas, cancelación externa, actualización sin reiniciar
asistencia, demo excluida); rangos medianoche/mes/DST; zona del negocio distinta del navegador;
«Pendiente de cierre» calculado sin persistir asistencia.

## Privacidad y seguridad

- Observaciones e historial no aparecen en el listado general, ni en Google, ni en el bot.
- Títulos/notas se renderizan con `textContent`; el HTML no contiene títulos maliciosos.
- Notas limitadas a 2000 caracteres; motivo de corrección a 300; sin secretos ni conversaciones.
- API sin sesión → 401; sin CSRF → 400; corrección no admin → 403; sin SQL arbitrario.
- `admin` y `user` operan la agenda; sólo `admin` corrige excepcionalmente. No se afirma
  aislamiento por doctor (fuera de alcance).

## Límites y pendientes

- Sin verificación real de Google/WhatsApp. La red dentro de `BEGIN IMMEDIATE` en sincronización
  sigue pendiente para P03.
- La valoración estética/contraste fino queda para la revisión de Codex; el implementador validó
  estructura, interacción, teclado, zoom, CSP y consola de forma automatizada, no una auditoría
  visual humana.
- En móvil, la vista semanal usa desplazamiento horizontal **dentro** del panel de agenda (no de
  toda la página); el mes es compacto con «Ver más».
- Sin aislamiento usuario-profesional ni reasignación de calendario (fuera de P02).
- `requirements.txt` del bot sigue sin considerarse reproducible; no se tocó. No se añadieron
  dependencias de producto para P02 (Playwright es sólo herramienta de evidencia).

## Criterios de aceptación

| Criterio P02 | Estado |
|---|---|
| Día/semana/mes en PC/tablet/móvil, vista recordada | Cumplido (capturas y recorrido) |
| Filtros, alta, conflicto, reprogramación, cancelación | Cumplido |
| Asistencia desde el fin y notas/historial | Cumplido |
| Estados e invariantes compatibles con P01/sync | Cumplido (pruebas) |
| Migración v2 atómica/idempotente | Cumplido |
| Endpoints con sesión, CSRF, permisos y errores | Cumplido |
| Notas internas fuera de Google/bot | Cumplido |
| CSP local sin unsafe, sin inline | Cumplido (consola sin violaciones) |
| Teclado, foco, zoom 200 %, sin desborde de página | Cumplido (automatizado) |
| Evidencia real 360/768/1440 | Cumplido (`docs/producto/evidencias/p02/`) |

Estado: **lista para revisión**. No iniciar P03 hasta la decisión de Codex.

---

# P02B — Correcciones de la revisión

Fecha: 23-10-2026. Rama `actualisacion-dependencias`. Estado: **P02B lista para nueva
revisión** (no aceptada). P01 sigue aceptada. Sin commit, push, despliegue ni servicios
externos reales. Se conserva la evidencia P02 en `docs/producto/evidencias/p02/`.

## Hallazgos corregidos

### R1 — Control de versión completo

- `crm/calendar.py`: la descarga compara título/inicio/fin con tolerancia de instantes; si
  hay diferencia, actualiza y hace `row_version=row_version+1` + historial
  `cambio_externo` en la misma transacción. Una descarga idéntica no incrementa versión ni
  historial. Las cancelaciones externas también incrementan versión e historial.
- `crm/reservation_service.py`: reprogramar o cancelar una cita activa exige
  `expected_version`; sin versión u obsoleta se devuelve `version_conflict`.
  `crm/app.py` exige versión también en la ruta antigua `/appointments/<id>/cancel`.
- Pruebas: `test_remote_change_bumps_version_and_stale_edit_conflicts` (cambio remoto →
  versión 2 + historial; edición con versión 1 → conflicto sin perder el cambio remoto;
  descarga idéntica no altera versión/historial; edición con versión 2 aceptada) y
  `test_cancel_requires_version_on_service_form_and_api` (servicio, formulario y API sin
  versión/obsoleta → rechazo y estado intacto).

### R2 — Conflicto externo persistente

- Nuevo valor de sincronización `review` para conflictos que requieren revisión humana.
  Se excluye de la cola de salida (`pending`/`error`); `error` sigue siendo reintentable.
- Una cancelación externa posterior a `attended`/`no_show` conserva estado, asistencia y
  notas, marca `review`, agrega historial una sola vez y no se reenvía en sincronizaciones
  posteriores.
- Pruebas: dos sincronizaciones consecutivas sin manipular la base, remoto vacío y PATCH
  404 → `patched=0`, `inserted=0`, estado/asistencia/notas intactos, historial
  `cancelacion_externa` una sola vez; error 500 de transporte → `error` y reintento
  exitoso en la siguiente sincronización.

### R3 — Citas sin ocultar

- Rejilla con rango horario dinámico (mínimo 07–20, ampliable a 00–24) calculado por
  intersección real; 05–06, 21–22, 23–01 y eventos que empiezan antes del rango quedan
  visibles sin recortes.
- Día/Todos incluye profesionales inactivos con citas; su carril es de sólo lectura y el
  formulario sólo ofrece profesionales activos.
- Mes usa intersección por día y marca continuaciones con `↪`/`↦` y clases accesibles.
- Prueba backend `test_api_returns_out_of_window_cross_midnight_and_inactive`; navegador
  con los casos visuales y comprobación de que las tarjetas quedan dentro de su carril.

### R4 — Alta desde Mes y carreras de vista

- El formulario separa fecha (`date`) y horas (`start_time`/`end_time`). Al pulsar un día
  del mes conserva la fecha y deja las horas vacías (sin inventar una hora). La reserva
  creada se verifica en la API con `start_local` de esa fecha.
- Token de petición en `load()` descarta respuestas antiguas; prueba de navegador con
  respuesta semanal retrasada y cambio inmediato a mes: no se dibuja la vista antigua.

### R5 — Presentación

- Cabecera/controles móviles compactos (filtros en rejilla de dos columnas, botones y
  espaciados reducidos) para que la rejilla aparezca en la primera pantalla; se comprobó
  que `.agenda-surface` empieza antes de 700 px a 360 px y que hay una cita visible.
- Historial legible sin JSON crudo, con fechas de la zona del negocio: Detalle/Inicio/Fin/
  Estado/Situación/Sincronización/Motivo.
- Contraste de horas 6.67:1 y flechas 10.04:1; objetivo táctil de Mes 44×44 px. Recursos
  locales y CSP sin `unsafe-*` conservados.

## Archivos P02B

`crm/calendar.py`, `crm/reservation_service.py`, `crm/app.py`, `crm/static/agenda.js`,
`crm/static/agenda.css`, `crm/templates/agenda.html`, `tests/test_crm.py`,
`tests/test_reservation_service.py`, `tests/test_p02.py`, `tests/test_p02b.py` (nuevo),
`tools/evidencia_p02b.py` (nuevo), `docs/producto/evidencias/p02b/` (nuevo),
`docs/producto/DISENO_P02.md`, este reporte, `README.md` y `ESTADO.md`.

## Comandos y resultados reales

```powershell
# Suite completa del workspace (basetemp dentro del workspace)
python -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_calendar_tool.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/p02b-full2
# 80 passed in 105.60s

# Entorno mínimo, basetemp nuevo
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/p02b-final2
# 75 passed in 102.59s

# Evidencia real en Chromium
python tools/evidencia_p02b.py
# failures: []; contraste horas 6.67 / flechas 10.04; táctil Mes 44x44;
# consola no esperada 0; recursos >=400 no esperados 0; sin desbordamiento 360/768/1440
```

El recorrido de navegador cubrió: rejilla con citas 05–06, 21–22, 23–01 y evento previo al
rango; carril inactivo de sólo lectura; mes con continuaciones; alta desde Mes conservando
fecha y sin hora inventada; carrera de vistas; detalle e historial legibles; móvil 360;
teclado; zoom 200 %; consola y CSP.

## Evidencia

Nueva carpeta `docs/producto/evidencias/p02b/`:
`day-360/768/1440.png`, `week-360/768/1440.png`, `month-360/768/1440.png` (rejilla con citas,
página completa), `detail-history-360/768/1440.png`, `month-create-360.png`,
`mobile-first-360.png`, `zoom-200-1440.png`, `consola.json` y `RESUMEN.md`.
Se conservan las capturas anteriores en `evidencias/p02/`.

## Límites

- Google/WhatsApp siguen simulados; no se declara validación real. La red dentro de la
  transacción de sincronización y la resolución asistida de conflictos corresponden a P03.
- La valoración estética/contraste fino adicional queda para la revisión humana de Codex;
  el implementador validó estructura, posiciones, teclado, zoom, consola y CSP de forma
  automatizada con capturas reales.
- En móvil la vista semanal mantiene desplazamiento horizontal **dentro** del panel de
  agenda; la página completa no desborda.
- La resolución de un conflicto `review` se hace reprogramando, cancelando o mediante
  corrección administrativa (que devuelve la cita a `pending`). No se añadió un botón
  separado de «ignorar conflicto»; para una cita ya Atendida la corrección es de
  administración, coherente con las reglas de P02.
- No se añadieron dependencias de producto; Playwright es sólo herramienta de evidencia.

---

# P02C — Fechas completas y pruebas estables

Fecha: 23-10-2026. Rama `actualisacion-dependencias`. Estado: **P02C aceptada por
Codex** (`REVISION_P02C_CODEX.md`); P02 queda aceptada. P01 sigue aceptada. Sin
commit, push, despliegue ni servicios externos reales. Se conserva la evidencia de
`evidencias/p02/` y `evidencias/p02b/`.

## Correcciones

### R1 — El formulario representa el intervalo completo

- `crm/templates/agenda.html`: cuatro campos visibles, `start_date`, `start_time`,
  `end_date`, `end_time` (sustituyen la fecha única).
- `crm/static/agenda.js`:
  - Abrir una cita existente copia fecha y hora de **ambos** extremos; una duración de
    49 h conserva su fecha final. No se reconstruye el fin a partir de una sola fecha.
  - Se permiten horas de reloj iguales cuando las fechas son distintas (24 h); se rechaza
    fin igual en el mismo instante o anterior. El servidor sigue validando fin>inicio y
    DST en la zona del negocio.
  - La celda de 23:00 preselecciona inicio 23:00 y fin 00:00 con fecha final siguiente;
    nunca usa 24:00 en `input type="time"`.
  - El alta desde Mes conserva la fecha pulsada en inicio y fin, muestra ambas fechas y
    pide horas explícitas; no inventa hora ni cambia la fecha silenciosamente.
- `tools/evidencia_p02.py` y `tools/evidencia_p02b.py` se adaptaron a los campos nuevos
  para no quedar obsoletos.

### R2 — Test dependiente de la hora

- `tests/test_p02.py::test_api_lifecycle_filters_and_security` usa ahora una hora local
  fija (10:00) en una fecha futura, de modo que `start + 2 h` sigue en el mismo día local.
  No se cambió lógica de producción para hacerlo pasar.
- Se añadió `tests/test_p02c.py` con un caso separado de cruce de medianoche y
  expectativas por día: la cita 23:30–00:30 aparece en ambos días; una cita del día
  siguiente no aparece en el primero; el filtro por profesional respeta ambos casos.
- También cubre 49 h, 24 h con la misma hora en días distintos, 23:00–00:00,
  23:00–01:00 y fin inválido.

## Archivos P02C

`crm/templates/agenda.html`, `crm/static/agenda.js`, `tests/test_p02.py`,
`tests/test_p02c.py` (nuevo), `tools/evidencia_p02.py`, `tools/evidencia_p02b.py`,
`tools/evidencia_p02c.py` (nuevo), `docs/producto/evidencias/p02c/` (nuevo),
`docs/producto/DISENO_P02.md`, este reporte, `README.md` y `ESTADO.md`.

## Comandos y resultados reales

```powershell
# Suite completa con basetemp dentro del workspace
python -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_p02c.py tests/test_calendar_tool.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/p02c-full
# 82 passed in 104.76s

# Entorno mínimo, basetemp nuevo dentro del workspace
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_p02c.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/p02c-final
# 77 passed in 102.26s

# Evidencia real en Chromium con payload del navegador
python tools/evidencia_p02c.py
# failures: []; consola no esperada: 0; recursos >=400 no esperados: 0
```

El recorrido de navegador comprobó:
- Cita de 49 h: formulario con fecha final a dos días; payload real
  `start=AAAA-MM-DD T10:00`, `end=(+2 días) T11:00`; persistencia 49 h.
- Cita de 24 h: misma hora de reloj, fechas distintas; persistencia 24 h.
- Celda 23:00: fin 00:00 del día siguiente, payload correcto y persistencia 1 h.
- Cita 23:00–01:00: conserva fecha final siguiente y 2 h al guardar.
- Fin igual mismo instante y fin anterior: rechazo en formulario, sin POST.
- Alta desde Mes: `start_date`/`end_date` iguales a la fecha pulsada, horas vacías antes
  de completarlas y payload con esa fecha.
- Zoom 200 % sin desbordamiento.

## Evidencia

`docs/producto/evidencias/p02c/`: `form-49h-360.png`, `form-49h-1440.png`,
`detail-49h-360.png`, `detail-49h-1440.png`, `form-23-360.png`,
`form-invalid-360.png`, `form-month-360.png`, `zoom-200-1440.png`, `consola.json` y
`RESUMEN.md`. No se sobrescribió la evidencia P02/P02B.

## Límites

- Google/WhatsApp siguen simulados; no se declara validación real. No se inició P03.
- La validación estética humana final queda para Codex; las capturas son reales y se
  comprobó el payload/persistencia, no sólo la apariencia.
- La comparación cliente de fin>inicio usa hora de pared del negocio; los huecos/ambigüedades
  DST siguen rechazándose en el servicio.
- Sin cambios de dependencias: Playwright es sólo herramienta de evidencia.
