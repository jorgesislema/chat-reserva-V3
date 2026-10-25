# Estado de continuidad — leer al retomar

Actualizado: 23-10-2026. Responsable de especificación/revisión: Codex. Implementación prevista: DeepSeek.
Raíz real: `H:\git\chat-clinica-dental - copia\chat-reserva-V3`.

## Orden de lectura

AGENTS.md → este archivo → PLAN.md → REPLICACION.md → PROMPT_01_DEEPSEEK.md → MAPA.md.
Estos documentos continúan el trabajo aunque se pierda el historial del chat.

## Punto actual

**24-10-2026: Premium trasladado a proyecto independiente.**
Por instrucción del propietario, `docs/producto/premium` y `docs/entregas`
se movieron a `H:\git\Agente de reserva V4`, conservando esas rutas relativas.
Los 10 archivos se verificaron por SHA256 al moverlos; después se actualizaron
las rutas en destino y se añadieron guías de entrada propias de V4.
GLM trabaja V4 en esa nueva raíz. Este proyecto V3 conserva código e historial
como referencia de lectura. No se movió ni modificó código, datos o secretos.
Siguiente paso Premium: leer `H:\git\Agente de reserva V4\README.md` y ejecutar
PR00 documental allí. Las referencias anteriores a Premium más abajo son historia.

**Actualización más reciente: carpeta de entregas y evidencia para revisión.**
Se creó documentalmente `docs/entregas/` con README, índice y plantilla. GLM debe
guardar cada fase en `<ID>/ENTREGA.md`, con diseño/cambios, ejecuciones separadas
de pruebas, logs depurados, reportes, capturas, pendientes y respuestas a revisión.
Codex guarda dictamen propio sin que GLM lo reescriba. Prompts, estructura,
aceptación y PLAN.md actualizados. No hay entregas implementadas ni pruebas
nuevas: sólo documentación. Siguiente paso: GLM realiza PR00 y registra su entrega
en `docs/entregas/PR00/ENTREGA.md` para revisión.

**Actualización más reciente: estructura del repositorio antes de construir.**
El propietario solicita actualizar los prompts para que GLM comience desde un
repositorio ordenado. Se añadió `premium/06_ESTRUCTURA_REPOSITORIO.md`: árbol
destino `src/crm_premium`, responsabilidades, dependencias, mapa desde módulos
actuales y transición gradual. Se actualizaron índice, prompts y PLAN.md.
Secuencia: PR00 inventario/diseño documental → revisión → PR00B estructura
ejecutable mínima a cargo de GLM → revisión → PR01 PostgreSQL. Aceptación añade
T36–T38. Sólo cambios documentales; sin código, movimiento de carpetas operativas,
migraciones, ejecución de pruebas de aplicación ni despliegue. Siguiente paso:
usar el prompt inicial al final del documento 06 o maestro + PR00 del documento 04.

**Actualización posterior del 23-10-2026: especificación Premium documental.**
El propietario pide sólo lógica, documentación y prompts; Codex es dirección y
revisión, GLM será implementación y pruebas. Se preparó `premium/00_LEER_PRIMERO.md`
y documentos 01–05 de producto/investigación, datos/seguridad, experiencia/plantillas,
prompts por entregas PR00–PR10 y matriz T01–T35. Modelo confirmado: freelancer
instala en VPS del cliente y entrega código; sin suscripción propia, mantenimiento
opcional; múltiples usuarios y perfiles clínica/tienda/colegio/inmobiliaria.
PostgreSQL local se interpreta privado en la misma VPS, con acceso web HTTPS.
Conectores adicionales preparados no se declaran implementados. Se consultaron
fuentes oficiales y la base documental/captura actual; no se ejecutaron pruebas
de aplicación, ni migraciones, ni servicios externos. No se modificó código,
secretos ni datos operativos. PLAN.md incorpora el alcance específico Premium.
Siguiente paso: entregar a GLM el prompt maestro y PR00 (auditoría documental),
revisar su resultado antes de autorizar PR01. Volúmenes, proveedor VPS y primeros
conectores se concretan por instalación. P03 mantiene pendiente su prueba externa;
el estado histórico de implementaciones siguiente se conserva sin revalidarlo.

WhatsApp de pruebas: el propietario confirmó que el envío desde el panel de
Meta llegó a su teléfono. GUIA_WHATSAPP_PRUEBAS.md actualizada con la ruta real
del panel y pasos de App Secret/Verify Token. No se obtuvieron, leyeron ni
guardaron credenciales mediante Codex. Recepción backend/túnel y conversación
real siguen sin verificar. Cambio documental; sin nuevas pruebas de aplicación.

**G01 aceptada por Codex tras G01B**. Dictamen independiente en
`REVISION_G01B_CODEX.md`: 135 pruebas mínimas pasaron (161.93s) y 11 de texto
del procesador pasaron (8.35s; 2 casos audio excluidos). Reproducciones Madrid,
DST y cierre corregidas. Ejecución adicional con audio interrumpida sin resultado
final; las 160 pruebas completas siguen siendo evidencia de GLM. Sólo documentos
actualizados en esta revisión, sin aplicación, datos operativos ni commit/push.
Siguiente paso: especificar P04 (bandeja y pausa persistente de IA), conservando
pendiente la prueba real de P03. El propietario informa claves actualizadas;
Codex no las inspeccionó ni acreditó webhook o conversación real.

Entrega histórica: **G01B implementada y presentada para revisión** (correcciones R1–R3
de `REVISION_G01_CODEX.md`, prompt `PROMPT_GLM_01B_CORRECCIONES.md`): zona única
gobernada por el perfil con conflicto explícito contra `CRM_TIMEZONE`
(reproducción Codex corregida: perfil Madrid → UTC persistido 09:00, Google
simulado con timeZone Europe/Madrid); extracción sólo del último `AIMessage`
con normalización de bloques (no envía texto humano/de herramienta ni
estructuras internas, texto y audio); `check_window` por instantes UTC con
límites al segundo y fin a medianoche contando un solo día. Suites: 135
mínima (`.pytest_cache/g01b-min`, 213.83s) y 160 bot
(`.pytest_cache/g01b-bot`, 283.88s), ambas salida 0. Detalle en
`REPORTE_G01.md` (sección G01B) y `DISENO_G01.md` (§9). No autoaceptada.

Entrega G01 original: **revisada y devuelta** (`REVISION_G01_CODEX.md`); Codex
ejecutó 122 pruebas mínimas y reprodujo los tres hallazgos. Entrega G01 (histórico):
**implementada y presentada para revisión** (`PROMPT_GLM_01_ESTABILIZACION.md`,
implementador GLM, 23-10-2026): perfil de negocio compartido web/bot con la misma
regla de horario (A1), un único registro por interacción incluido HANDOFF
(A2-telemetría) y analítica con duración UTC, canal de creación e instantánea
coherente del ETL (A5). Ver `REPORTE_G01.md`, `DISENO_G01.md` y `perfiles/`.
Sin avanzar a otros módulos; la prueba real de Google sigue pendiente y no se
declaró P03 aceptada.

Auditoría independiente Codex del 23-10-2026 guardada en
`AUDITORIA_REPO_2026-10-23.md`: 78 pruebas agenda/CRM + 18 Google/BI pasaron
en dos ejecuciones actuales con bases temporales. No es suite integral del bot.
Se reprodujeron errores de duración DST y clasificación de origen bot en BI;
siguen pendientes horarios compartidos, transferencia humana durable, módulos
comerciales, conocimiento editable y paquete replicable. No se cambió aplicación
ni datos operativos durante esta auditoría. Consultar ese documento antes de
priorizar nuevas funciones; se conserva el historial de entregas siguiente.

**Cambio de gobernanza autorizado por el propietario (23-10-2026):** a partir de P03 un
único asistente ejerce dirección, implementación y revisión. Se conserva la disciplina:
una fase a la tiempo, pruebas reales ejecutadas (no históricas), evidencia verificable,
registro por entrega y no iniciar la fase siguiente sin cerrar la anterior. La revisión
propia debe repetir suites y reproducir hallazgos como hacía Codex.

P02C revisada y **aceptada**; P01 y P02 quedan aceptadas (`REVISION_P02C_CODEX.md`).
P03 (Google confiable y conexión administrable) **implementada y auto-revisada**
(97/92 pruebas en verde, evidencia real con Google simulado). Su aceptación final
queda condicionada a la prueba en un calendario real exclusivo autorizado por el
propietario. Ver `PROMPT_03_DEEPSEEK.md`, `DISENO_P03.md`, `REPORTE_P03.md` y
`docs/producto/evidencias/p03/`.
Historial:
1. P01 entregada por DeepSeek → **devuelta** por Codex.
2. P01B corrigió migraciones transaccionales, horas DST y fixture/restauración.
3. Codex revisó y **aceptó P01** (`REVISION_P01B_CODEX.md`).
4. P02 agregó agenda visual, estados operativos, notas e historial; Codex la **devolvió**.
5. P02B corrigió versión externa, revisión persistente, citas ocultas, alta desde Mes y
   presentación; Codex la **devolvió** por fecha final perdida y un test horario inestable.
6. P02C corrigió el intervalo completo del formulario y estabilizó el test; Codex la
   **aceptó** tras repetir ambas suites (82/77), reproducir R1 y repetir el recorrido
   de navegador con evidencia propia (0 fallos).
Ver `REPORTE_P02.md` (secciones P02, P02B y P02C), `DISENO_P02.md`,
`REVISION_P02C_CODEX.md` y `docs/producto/evidencias/p02c/`.
P03–P08 siguen pendientes; P03 puede especificarse ahora (no iniciarla sin prompt).

## Tarea G01/G01B — estabilización (G01B lista para nueva revisión)

- Fecha: 23-10-2026. Rama `actualisacion-dependencias`. Implementación: GLM.
  Sin commit ni push. Prompt: `PROMPT_GLM_01_ESTABILIZACION.md`; diagnóstico y
  diseño en `DISENO_G01.md`; entrega en `REPORTE_G01.md`.
- Cambios: `crm/business_profile.py` nuevo (perfil validado + `check_window`,
  `CRM_PERFIL_NEGOCIO`, perfil interno por defecto = comportamiento histórico);
  `perfiles/` con consultorio, servicios (Madrid) y pruebas 24×7; migración v4
  (`channel` web/bot/google + backfill google, histórico NULL); regla de
  horario en `reservation_service` (`outside_business_hours`, excepción
  admin con motivo e historial, bot nunca) usada por web (`app.py`) y bot
  (`integration.py`, `api/agent.py` sin zona/horarios/textos fijos);
  `api/procesamiento.py` + `api/main.py` con un único registro por interacción
  (A2); `crm/analytics.py` con duración UTC, `dim_canal`+`es_demo`,
  `BEGIN` de lectura y rechazo source=target.
- Pruebas: `test_business_profile.py` (10), `test_g01_reservas.py` (7),
  `test_g01_handoff.py` (6, entorno del bot), +5 en `test_analytics.py`;
  fixtures 24×7 en `test_crm/test_p02/test_p02c` separando consistencia
  temporal de horario (justificado por archivo, sin retirar cobertura);
  versiones de migración actualizadas a `[1,2,3,4]` como en v2/v3.
- Evidencia actual: 122 pasadas (.venv-verify, `g01-final-min2`, 170.30 s) y
  140 pasadas (venv del bot con agente/API, `g01-final-bot2`, 233.32 s).
  Primera corrida de regresión: 8 fallos (versiones v4 + tres pruebas P02 con
  bot/hora arbitraria sin perfil de prueba); corregidos y re-ejecutadas.
  Iteración de pruebas nuevas con 5 fallos propios, también registrada.
- No se modificó `.venv-crm`, `analitica.db`, secretos ni servicios externos.
- Límites: pausa durable de IA/bandeja = P04; A8 audio sin cambios; feriados
  y catálogo de servicios sólo contrato documentado; scripts de evidencia de
  navegador P02 requieren perfil 24×7 si se re-ejecutan.
- Estado G01: **devuelta por Codex** (`REVISION_G01_CODEX.md`, R1–R3).
- G01B (23-10-2026): `resolve_profile` con precedencia y conflicto explícito;
  `TIMEZONE`/`BUSINESS_NAME` derivados del perfil en `app.py`; bot, agente y
  CLI analítica usan `configured_profile().zone`; `_extraer` sólo último
  `AIMessage` con bloques normalizados; `check_window` por instantes UTC con
  segundos y medianoche de un solo día. Pruebas: +6 zona (g01_reservas),
  +7 extracción (g01_handoff), +8 horario preciso (business_profile); fixture
  de handoff corregida a `HumanMessage`. Resultados: 135 mínima
  (`g01b-min`, 213.83s) y 160 bot (`g01b-bot`, 283.88s), salida 0.
  Estado: **G01B lista para nueva revisión**. No autoaceptada.

## Tarea independiente: capa analítica estrella (entregada)

- Fecha: 23-10-2026. Rama `actualisacion-dependencias`. Sin commit ni push.
- Origen: petición del propietario («modelo estrella en la base de datos») +
  análisis de mejoras. Diseño elegido: base separada por ETL idempotente
  (opción 1); se descartó tocar el esquema operacional. Documento de mejoras
  priorizadas: `MEJORAS.md`.
- Entrega: `crm/analytics.py` (stdlib puro): reconstruye `analitica_bi.db`
  (o `CRM_ANALYTICS_DB`) con `fact_citas` + `dim_fecha/cliente/profesional/
  estado/origen` y 4 vistas KPI; fechas en zona del negocio; CLI
  `python -m crm.analytics`; botón admin «Reconstruir base analítica»
  (`POST /analytics/rebuild`, CSRF, sólo administración) en la pestaña
  Sincronización. `tests/test_analytics.py` (4): cuadre con el operacional,
  medidas (duración/primera cita/cruce de medianoche), zona, idempotencia,
  permisos/CSRF. `analitica_bi.db` queda fuera de Git (`*.db` ignorado).
- Futuro: `fact_ventas` (P05) y `fact_conversaciones` (P04, absorbe
  `interacciones` legacy); P07 consulta esta base en vez de agregar SQL sobre
  el operacional.
- Evidencia actual (no histórica): 101 pruebas en el entorno completo del
  workspace (basetemp `.pytest_cache/star-full`, 274.03 s) y 96 en
  `.venv-verify` (`.pytest_cache/star-verify`, 222.07 s), ambas con
  `tests/test_analytics.py` incluido. Primera corrida de la suite analítica:
  1 fallo de permisos por token CSRF capturado antes del login en el propio
  test; corregido y re-ejecutado en verde.
- Estado: entregada y auto-revisada.

## Reporte P03 (implementada; aceptación condicionada a prueba real)

- Fecha: 23-10-2026. Rama `actualisacion-dependencias`. Sin commit ni push.
- Entrega: outbox sin red dentro de transacciones de escritura, confirmación
  optimista por `row_version`, retirada 0→1→5→15→60→360→1440 min (primer fallo
  reintenta inmediato, contrato P02B), conflicto lógico → `review` fuera de la
  cola, arriendos por profesional (`crm_sync_leases`) para web + tarea
  programada, migración v3 atómica, pestaña admin «Sincronización» con cola y
  «Enviar ahora» (admin, CSRF, historial y versión).
- Archivos: `crm/store.py`, `crm/calendar.py` (reescrito), `crm/app.py`,
  `crm/templates/sync.html` (nuevo), `base.html`, `dashboard.html`,
  `tests/test_p03.py` (nuevo, 14), adaptación de expectativas de versiones a
  `[1,2,3]` en `test_p01b/test_p02/test_reservation_service`, `tests/test_crm.py`
  (pestaña), `tools/evidencia_p03.py` (nuevo), `README.md`, docs de producto.
- Evidencia actual (no histórica): 97 pruebas en el entorno completo del
  workspace (basetemp `.pytest_cache/p03-full2`); 92 en `.venv-verify`
  (`.pytest_cache/p03-verify2`). Primera corrida: 4 fallos por expectativas de
  versión; corregidos y re-ejecutadas. Recorrido `tools/evidencia_p03.py`:
  6 escenarios ok, consola/recursos no esperados 0, capturas en
  `docs/producto/evidencias/p03/`. Sonda real de bloqueo: un segundo proceso
  SQLite escribe durante la llamada de red (antes habría obtenido `locked`).
- No se modificó `.venv-crm`, `analitica.db`, secretos ni servicios externos.
- Límites: verificación con calendario real pendiente de autorización; reintento
  vencido ocurre en el próximo ciclo (sin demonio); OAuth pendiente.
- Estado: aceptación condicionada; único criterio abierto = prueba real.

## Reporte P02C (aceptada)

- Fecha: 23-10-2026. Rama `actualisacion-dependencias`. Sin commit ni push.
- Correcciones:
  - Formulario con cuatro campos: `start_date`, `start_time`, `end_date`, `end_time`.
    Abrir/reprogramar conserva ambos extremos (49 h incluidas); se permiten horas iguales
    en fechas distintas (24 h); se rechaza fin igual en el mismo instante o anterior.
    Celda 23:00 → fin 00:00 del día siguiente, nunca 24:00. Mes conserva fecha en ambos
    extremos y pide horas explícitas.
  - `tests/test_p02.py::test_api_lifecycle_filters_and_security` usa una hora local fija
    segura en fecha futura; el cruce de medianoche queda en prueba separada.
  - `tests/test_p02c.py` (2 pruebas): intervalos 49 h/24 h/23–00/23–01, fin inválido y
    filtro por día con cruce de medianoche.
  - `tools/evidencia_p02c.py`: payload real del navegador, persistencia y capturas.
- Evidencia actual (no histórica):
  - 82 pruebas en el entorno completo del workspace (basetemp `.pytest_cache/p02c-full`).
  - 77 en `.venv-verify` (sin Pydantic/IA/Qdrant/Google) con basetemp
    `.pytest_cache/p02c-final`.
  - Chromium real: 49 h abre/guarda con fin intacto; 24 h con igual hora y fechas
    distintas; 23–00 y 23–01; fin inválido sin POST; Mes con fechas explícitas; zoom 200 %.
    0 consola/recursos no esperados.
  - Capturas en `docs/producto/evidencias/p02c/`; se conservan P02 y P02B.
- No se modificó `.venv-crm`, `analitica.db`, secretos ni servicios externos.
- Límites: Google/WhatsApp simulados; la revisión estética de Codex cubrió las capturas
  P02C y el recorrido automatizado; DST continúa validándose en el servicio.
- Revisión: Codex repitió ambas suites (82 completas, 77 mínimas), reprodujo el caso
  de 49 h con payload del formulario y repitió el recorrido de navegador con evidencia
  propia sin sobrescribir la entrega: 0 fallos. Dictamen: aceptada.

## Reporte P02B (devuelta; resuelta por P02C)

- Fecha: 23-10-2026. Rama `actualisacion-dependencias`. Sin commit ni push.
- Correcciones:
  - `crm/calendar.py`: cambios externos relevantes incrementan `row_version` y escriben
    historial en la misma transacción; descarga idéntica no invalida; cancelación externa
    posterior a asistencia pasa a `sync_status='review'` (excluida de reenvíos) y no pierde
    notas/asistencia; `error` sigue siendo reintentable.
  - `crm/reservation_service.py` y `crm/app.py`: reprogramación/cancelación exigen versión
    también en la ruta antigua de formulario; sin versión/obsoleta → conflicto sin cambios.
  - `crm/static/agenda.js`/`agenda.css`: rejilla dinámica 00–24, segmentación por
    intersección, carriles inactivos de sólo lectura, mes con continuaciones, alta desde Mes
    con fecha conservada y hora explícita, token contra respuestas antiguas, historial
    legible, cabecera móvil compacta, contraste y objetivos táctiles.
  - `tests/test_p02b.py` (6 pruebas) y `tools/evidencia_p02b.py`.
- Evidencia actual (no histórica):
  - 80 pruebas en el entorno completo del workspace (basetemp `.pytest_cache/p02b-full2`).
  - 75 en `.venv-verify` (sin Pydantic/IA/Qdrant/Google) con basetemp `.pytest_cache/p02b-final2`.
  - Chromium real: 05–06, 21–22, 23–01, evento previo al rango, inactivo, mes con
    continuaciones, alta desde Mes, carrera de vistas, historial legible, móvil 360,
    teclado y zoom 200 %; contraste 6.67/10.04; táctil Mes 44×44; 0 consola/recursos no
    esperados; sin desbordamiento.
  - Capturas nuevas en `docs/producto/evidencias/p02b/`; se conservan las de P02.
- No se modificó `.venv-crm`, `analitica.db`, secretos ni servicios externos.
- Límites: Google/WhatsApp simulados; red y resolución asistida de conflictos en P03;
  revisión estética humana pendiente de Codex.

## Reporte P02 (entrega inicial, devuelta)

- Fecha: 23-10-2026. Rama `actualisacion-dependencias`. Sin commit ni push.
- Cambios principales:
  - `crm/store.py`: migración v2 con `operational_status`, `row_version`, notas e historial;
    backfill de canceladas; ejecutor atómico de P01B conservado.
  - `crm/reservation_service.py`: transiciones (confirmar, reprogramar, cancelar, atendida,
    no asistió, corrección admin), versión optimista, notas, historial, listado/detalle; reglas
    e invariantes en un único servicio.
  - `crm/agenda_time.py`: rangos día/semana/mes en zona del negocio y DST.
  - `crm/app.py`: CSP `script-src 'self'`, CSRF por cabecera, `/theme.css` con `CRM_ACCENT`,
    API `/api/agenda` y `/api/appointments...`; rutas de formulario con versión/motivo.
  - `crm/calendar.py`: no resucita canceladas, no borra asistencia/notas; cancelación externa
    tras cierre se marca como conflicto de sincronización con historial.
  - `crm/templates/agenda.html`, `crm/static/agenda.css`, `agenda.js`: agenda propia local,
    sin CDN ni componente de terceros; panel lateral/móvil, filtros y diálogos accesibles.
  - `tests/test_p02.py`: 17 pruebas. `tools/evidencia_p02.py`: recorrido real con Playwright.
- Evidencia actual (no histórica):
  - 74 pruebas pasaron en el entorno completo del workspace.
  - 69 pasaron en `.venv-verify` (sin Pydantic/IA/Qdrant/Google) con basetemp
    `.pytest_cache/p02-verify-2`.
  - Chromium real: día/semana/mes a 360/768/1440, alta, conflicto, nota, historial,
    reprogramación, cancelación, recarga, asistencia, «Ver más», teclado y zoom 200 %;
    0 errores de consola no esperados, 0 recursos >=400 no esperados, sin desborde de página.
  - Capturas reales en `docs/producto/evidencias/p02/` (no mockups).
- No se modificó `.venv-crm`, `analitica.db`, secretos ni servicios externos.
- Límites: sin Google/WhatsApp reales; red en transacción de sync corresponde a P03; sin
  aislamiento por doctor; valoración estética humana pendiente de Codex.

## Reporte P01B (lista para nueva revisión)

- Fecha: 23-10-2026. Rama `actualisacion-dependencias`. Sin commit ni push.
- Cambios:
  - `crm/store.py`: migraciones sin `executescript`, con `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK`
    explícitos; cada migración + versión atómica; serialización de inicializaciones; adopción
    atómica; `user_version` legacy intacto.
  - `crm/reservation_service.py`: rechazo de horas locales inexistentes/ambiguas sin offset
    (`NonexistentLocalTime`, `AmbiguousLocalTime`) y zona inválida (`InvalidZone`); offsets
    explícitos conservados. Códigos `nonexistent_local_time`, `ambiguous_local_time`, `invalid_zone`.
  - `crm/integration.py`: propaga el mensaje específico de zona/hora; no duplica validación.
  - `tests/conftest.py`: import diferido normal (sin `importorskip`), revela errores reales.
  - `tests/test_p01b.py` nuevo: 13 pruebas de migraciones atómicas/concurrentes, `user_version`,
    respaldo/restauración ficticia, DST Madrid y rechazo web/bot.
  - `README.md`: respaldo/restauración consistente y pruebas del CRM mínimo.
- Evidencia actual (no histórica): 52 pasaron en `.venv-verify` (39 previas + 13 nuevas,
  basetemp nuevo `.pytest_cache/p01b-verify-1`); 57 en el entorno completo del workspace;
  concurrencia de inicialización 5/5; `test_database.py` revela `ModuleNotFoundError: pydantic`
  en el entorno mínimo (ya no se omite).
- No se modificó `.venv-crm`, `analitica.db`, secretos ni servicios externos.
- Fallos pendientes: ninguno en las pruebas ejecutadas. Sin verificación real de Google/WhatsApp.

## Reporte P01 (entrega inicial, devuelta)

- Fecha: 23-10-2026. Rama `actualisacion-dependencias`. Sin commit ni push.
- Objetivo: base Python verificable y operaciones comunes de reservas web/bot.
- Cambios principales:
  - `crm/reservation_service.py` nuevo: `save_appointment` (alta y reprogramación) y
    `cancel_appointment`, con zona IANA, fin>inicio, futuro, profesional activo, cliente
    opcional, conflictos por intervalo, exclusión de la propia cita, `event_id` preservado,
    `BEGIN IMMEDIATE`, resultados estructurados y auditoría con actor humano/sistema/bot.
  - `crm/app.py`: rutas de agenda delegan en el servicio; ya no duplican SQL ni validación.
  - `crm/integration.py`: adaptador del bot delega en el servicio; sin Flask ni app web.
  - `crm/store.py`: migraciones versionadas propias en `crm_migrations`; ya **no** escribe
    `PRAGMA user_version` (no pisa la versión legacy). Adopción de bases existentes como línea base 1.
  - `tests/conftest.py`: import diferido de `GestorDB` (las pruebas CRM no requieren Pydantic).
  - `tests/test_reservation_service.py`: 12 pruebas nuevas (solape web/bot, concurrencia real,
    profesionales distintos/inactivo, fechas/zona/offset/pasado con reloj inyectable,
    reprogramación y doble cancelación, rollback por FK/auditoría, `origin=demo`, bot sin admin,
    migraciones idempotentes y arranque sin IA/Qdrant/Google).
  - `requirements-crm.txt` mínimo (Flask, python-dotenv, tzdata); `requirements-crm-test.txt`
    (pytest) y `requirements-crm-sync.txt` (Google opcional). `requirements.txt` del bot sin cambios.
- Entorno verificado: `.venv-verify` **nuevo** dentro del workspace, con sólo Flask 3.1.2,
  python-dotenv 1.0.1, tzdata 2025.2, pytest 8.1.1 y Werkzeug 3.1.9 (sin Google/IA/Qdrant/Dash/Streamlit).
  No se modificó `.venv-crm` (entorno del cliente).
- Pruebas actuales (no históricas): 44 pasaron en el entorno completo del workspace
  (`test_crm`, `test_reservation_service`, `test_calendar_tool`, `test_demo_seed`); 39 pasaron en
  `.venv-verify` (CRM, reservas y demo). Arranque del CRM en entorno mínimo sin módulos pesados.
- Límite registrado: pip requirió `REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE`/`PIP_CERT` apuntando a
  `certifi` porque el proceso heredaba una ruta CA inválida; no se cambiaron variables del sistema.
- Fallos pendientes: ninguno detectado en las pruebas ejecutadas. Sin verificación de cuentas
  Google/WhatsApp reales (fuera del alcance de P01).

## Evidencia conocida y límites

- CRM Flask/Jinja en crm/, entrada run_crm.py; roles, leads, citas en tabla y Google por profesional.
- reserve() en crm/integration.py y appointment_save() en crm/app.py ya delegan en reservation_service.
- P02 agrega operational_status junto a active/cancelled, agenda visual y asistencia;
  su aceptación está pendiente de las correcciones documentadas.
- Google aún usa red dentro de BEGIN IMMEDIATE. No dar por verificada la sincronización con cuentas reales.
- Existe backend anterior FastAPI, Dash/Streamlit y modelos antiguos: no son una sola aplicación comercial.
- RAG actual no tiene publicación gestionada en frontend y recrea colección al indexar.
- requirements.txt fue modificado respecto de la revisión inicial; no asumir que sus rangos actuales instalan.
- .venv-crm es el entorno usado por el cliente. No reutilizar .venv de otra carpeta/computadora.
- Hay datos ficticios en la base activa, cargados con autorización: 3 profesionales, 60 contactos,
  265 citas DEMO y 29 huecos del 23-10 al 05-11 de 2026. No son clientes reales.
- Respaldo anterior a demo en backups/crm-antes-demo-20261023-095746-833600.db. No versionar bases.
- Protección de envío de citas origin=demo añadida a crm/calendar.py; prueba específica existente.
- Históricamente pasaron 48 pruebas de CRM/DB/calendario/agente/RAG en una revisión anterior.
  No constituyen resultado de la revisión actual ni certifican dependencias o cuentas reales.
- En la carga demo pasaron dos pruebas unittest de repetición y exclusión de envío Google;
  integridad/FK sin fallos y sin cruces de horarios en esa carga. Sin nueva ejecución en este turno.

## Cambios preexistentes observados al iniciar este plan

git status: README.md, crm/calendar.py y requirements.txt modificados; seed_demo_crm.py y
tests/test_demo_seed.py sin seguimiento. Conservar; no atribuir a P01 ni revertirlos.
No se hizo commit ni despliegue en esta entrega. No inspeccionar el contenido secreto de .env.

## Siguiente acción

1. Codex revisa G01B: `REPORTE_G01.md` (sección G01B), `DISENO_G01.md` (§9),
   el diff y la repetición de las suites (135 mínima / 160 bot). Decidir
   aceptación o devolución; no autoaceptada por el implementador.
2. Pendiente del propietario: calendario de prueba exclusivo + credenciales
   para cerrar P03 (G01 no la sustituye); decisión sobre commits por fase.
3. Tras G01B aceptada: P04 (bandeja y transferencia humana) sobre el perfil y
   la telemetría única ya corregidos; requiere cuenta Meta de prueba antes de
   aceptar el canal real.
P01/P02 aceptadas; su historial se conserva en este archivo y en las revisiones.
Si hay bloqueos, avanzar sólo tareas independientes y dejar comando, error y paso pendiente exactos.

## Registro obligatorio por entrega

Copiar este formato para cada Pxx:
- Fecha, versión/commit o identificación del árbol y responsable.
- Objetivo; archivos cambiados; decisiones y desviaciones del plan.
- Comandos ejecutados y resultados, distinguiendo actual/histórico/simulado/real.
- Fallos pendientes y si son previos o nuevos, con evidencia.
- Recursos de prueba usados; confirmar que no se enviaron datos demo a clientes.
- Criterios aceptados y pendientes; siguiente tarea concreta.
- Estado: pendiente / en curso / bloqueada por causa identificada / lista para revisión / aceptada.
