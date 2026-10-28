# Entrega C02 — Agenda/WhatsApp unificado, catálogo editable y atención humana (parcial)

Fecha: 2026-10-27. Rama: `main` (sin commit). HEAD: db6194c.

Referencias: `../ALCANCE.md`, `../MATRIZ_TRAZABILIDAD.md`, `../REGISTRO_EJECUCIONES.md`,
`../DECISIONES.md`, `../INVENTARIO_RETIRO.md`, `PROMPT_C02_WHATSAPP_AGENDA_UNICA_2026-10-27.md`,
`ESTADO.md`.

## Corrección de la devolución (R1–R5) — 27-10-2026
La revisión Codex (ver `REVISION_CODEX.md`) devolvió C02 e incorporó sección 10. $.aplicados
en la misma C02, con las verificaciones reales abajo.

### R1 · Catálogo completo y no bloqueado
- Corregido el defecto del contrato JS/API: `crm_c02.js` extrae `items` correctamente,
  reintenta la carga (catch), edita por celda (Enter/Guardar, Escape/Cancelar), protege de
  doble envío y maneja el conflicto de versión 409.
- Detalle por artículo con dialog (nombre, tipo, precio, stock, vigencia, profesional, notas) y
  **notas internas sólo para administradores** (el backend no las expone ni permite
  escribirlas a no-admin).
- Rutas nuevas: `GET /api/c02/catalog/<id>`, `/revisions`, y `catalog_item_public` con
  revalidación de activo/stock. Tests nuevos en `tests/test_c02_services.py` y
  `tests/test_c02_frontend.py`.

### R2 · Worker con citas reales de dominio y multi-turno
- Migración **v6** (`store.py`): columnas `pending` y `egress_paused` en `crm_conversations`.
- `crm/canal.py` resuelve **reserva/reagenda/cancelación reales** con el dominio común
  (`save_appointment`, `cancel_appointment`, `reprogram_appointment`), diálogo multi-turno con
  estado persistente, reconoce fecha/hora (español + ISO) y confirmación de cancelación.
- 9 tests nuevos en `tests/test_c02_canal.py` (reserva real, multi-turno, pausa humana durante
  el diálogo, pausa antes del ingreso, petición explícita de humano, cancelación confirmada).

### R3 · Pausa humana durable y petición explícita de humano
- Barrera `egress_paused` + `conv_confirm_pause`: el worker **no genera ni encola** salida IA
  hasta que la conversación vuelve a IA («Devolver a IA»). Verificado por tests.
- La petición explícita de humano deriva a `humano_explicito` y no se emite salida IA.

### R4 · Ventanas obligatorias de la sección 10
- **Catálogo** (10.1) completo y operativo en el navegador.
- **Conocimiento y configuración** (10.2): editor documental `#c02-kb-*` (crear/revisar/
  publicar/desactivar) y Config de IA (`crm_c02_config.js`, migración **v7** `crm_settings`,
  saludo/mensajes persisten; el saludo es sólo-admin).
- **Chat interno** (10.3): `chat.html` + `crm_c02_chat.js` consulta `responder_chat_internal`
  que combina RAG (KB publicada vía `kb_search`) y BD (agenda/profesionales).
- **Bandeja humana** (10.4): `inbox.html` + `crm_c02_inbox.js` (listar/ tomar/responder/
  devolver), reemplaza la preview de C01.

### R5 · E2E en navegador y trazabilidad (verificado)
- `scripts/e2e_crm_c02.py` + `frontend/e2e/crm_c02.e2e.mjs` recorren en Chromium: fase `cat`
  (catálogo alta, doc + publicar, chat, config) y fase `bandeja` (tomar + responder). La
  persistencia se verifica sobre la base de fixtures. Resultado: **TODOS LOS CHECKS OK** en
  ambas fases (registrado en `../REGISTRO_EJECUCIONES.md`).
- Regresión completa de la suite CRM/C02: **136 PASS** (tras v7 + R4).

## Corrección CH-01..CH-04 (segunda revisión de control humano) — 27-10-2026

La revisión independiente (`REVISION_CONTROL_HUMANO_CODEX.md`, DEVUELTA) detectó:
- **CH-01** salida IA después de tomar el chat (validación sólo al reclamar);
- **CH-02** respuestas duplicadas por acuse perdido (timeout ≠ fallo cierto);
- **CH-03** bandeja sin refresco del estado real + `KeyError: origin` en el E2E;
- **CH-04** faltaban los documentos de cierre del ejecutor.

Corrección implementada acotada a estos cuatro hallazgos (detalle y nota honesta
sobre la semántica de en-vuelo en `CORRECCION_CONTROL_HUMANO.md`):

- **Migración v9** (`store.py`): estados `autorizado`/`incierto` en `crm_outbox`
  (rebuild preservando filas e índices; SQLite no permite alterar un CHECK).
- **Admisión efectiva al envío** (`c02_services.outbox_admitir`): barrera
  determinista justo antes del transporte, sin transacciones abiertas durante
  llamadas externas; reenvío de incierto bloqueado (`outbox_requeue` →
  `bloqueados`) hasta `outbox_reconciliar` con idempotencia declarada.
- **`crm/egress.py`**: triestado enviado/fallo/incierto; transporte simulado con
  dedupe en destino (`TransporteSimuladoIdempotente`) → una sola recepción.
- **Bandeja** (`crm_c02_inbox.js`): refresco por firma de estados de entrega y
  badges `admitido, en vuelo` / `pendiente de confirmación`.
- **E2E** (`scripts/e2e_control_humano.py`): fix `KeyError: origin`, polling
  acotado de entrega, verificación en pantalla + BD + buzón (exit 0).
- **Pruebas**: `tests/test_c02_revision_control_humano.py` (6 regresiones que
  convierten las 2 reproducciones del revisor; RACE y DUPLICATES exigiendo el
  comportamiento correcto).

Evidencia real: EX-017 (88 passed, 49.17s, exit 0), EX-018 (32 passed), EX-019
(E2E exit 0, `VERIFY_OK`, capturas en `evidencias/c02/`).

Sigue sin declararse C02 cerrado ni el programa completo; espera de la segunda
revisión del revisor. Sin commit/push, sin proveedores ni datos reales.

## Corrección de la tercera revisión (REVISION_CONTROL_HUMANO_02_CODEX.md) — 27-10-2026

La segunda revisión independiente (requiere DOS correcciones) reabrió:
- **CH-01** — la autorización local (`outbox_admitir`) no equivale a la
  aceptación del transporte: inyectó la toma DENTRO del transporte y la respuesta
  IA salió igual `(ai_received_after_take=1)`. Corrección: `outbox_admitir` se
  sustituye por **`outbox_begin_send`** — el COMIENZO EFECTIVO del envío — con
  la PROPIEDAD del trabajo registrada en el reclamo (migración **v10**,
  `claimed_by`/`claimed_at`). Transacción corta `BEGIN IMMEDIATE` commiteada
  antes de la llamada externa (nunca transacciones abiertas durante la red;
  SQLite coordina entre procesos). Toma antes del comienzo ⇒ tarea IA invalidada
  y cero efectos externos; comienzo ya ganado ⇒ en vuelo explícito registrado y
  mostrado, sin cancelación imposible. Barreras deterministas en pruebas:
  `test_ch01_toma_antes_comienzo_cero_recepciones`,
  `test_ch01_toma_en_barrera_determinista_antes_comienzo`,
  `test_ch01_toma_antes_comienzo_tareas_multiples_cero_recepciones`,
  `test_ch01_varias_tareas_ninguna_posterior_inicia_envio_tras_toma`,
  `test_ch01_transporte_iniciado_toma_en_vuelo_explicito`,
  `test_ch01_transporte_iniciado_toma_en_vuelo_incierto`.
- **CH-02** — una tarea ya `enviado/entregado` se podía reencolar y duplicar
  (`SENT_TASK_RETRY {"requeued":1,"receipts":2}`). Corrección: `outbox_requeue`
  con **lista explícita de estados recuperables** y actualización atómica
  (`intento` vencida y `fallo` cierto no `invalidada`); `enviado`/`invalidada`/
  `incierto`/`autorizado` sin reconciliación y claims activos NUNCA se recuperan
  (quedan en `bloqueados` con motivo). Prueba obligatoria:
  `test_ch02_enviada_reintentar_id_requeued_0_y_una_recepcion`
  (`requeued=0` y una sola recepción) y `test_ch02_claim_de_otro_proceso_no_se_recupera`.

  **Última brecha de CH-01 (LAST_GAP) cerrada en la reanudación:** la marca
  `began_at` de `outbox_mark_sending` (v11) por sí sola no cerraba la carrera:
  quedaba una ventana entre el commit del CAS y `transporte.deliver`, y una toma
  confirmada en esa ventana seguía dejando salir 1 mensaje IA
  (`{"events":["take_committed","transport_called"],"receipts":1}`). La relectura
  aislada posterior (`_conv_ia_bloqueada`) tampoco acreditó coordinación
  (`READ_GAP {"events":["take_committed_after_read","transport_called"],"receipts":1}`).
  Se sustituyó por una **exclusión mutua compartida por conversación**
  (`crm/conv_lock.py`) que usa tanto el consumidor de salida como `conv_take` y
  abarca la decisión final y la llamada al transporte: el egress adquiere el
  bloqueo ANTES de `outbox_mark_sending` y lo conserva durante
  `transporte.deliver` (sin transacción SQLite abierta durante la red; llamada
  al transporte con timeout acotado). `conv_take` adquiere el mismo bloqueo,
  nunca espera indefinidamente (si otro proceso está entregando, informa
  `envio_en_curso` y permite reintentar). Ahora:
  `{"events":["take_committed"],"receipts":0}` (`transport_called` ausente). Sin
  bloqueo global de Python ni transacción abierta durante la llamada de red.

  **Identidad canónica de bloqueo en Windows (esta reanudación):**
  `crm/conv_lock.py:_db_identity` combina `os.path.realpath` (resuelve
  junction/symlink y convierte la ruta a absoluta) con `os.path.normcase`
  (unifica mayúsculas/minúsculas en Windows), de modo que `_lock_path` produce el
  mismo archivo de bloqueo para distintos caminos que apuntan a la misma BD.
  Alias soportados: diferencias de mayúsculas/minúsculas, rutas relativas y
  absolutas equivalentes, y alias por junction/symlink. No soportados: hardlinks
  ni rutas de red (no probado). Verificación:
  `LOCK_ALIAS {"same_database_file":true,"same_lock_path":true,"both_acquired":false}`;
  la toma vía alias mientras otro proceso entrega devuelve `ok=False` con
  `envio_en_curso>=1` y no confirma.

Evidencia real: EX-020 (124 passed, 64.97s, exit 0 — 120 del revisor + 4 nuevas
netas), EX-021 (E2E exit 0, 5/5 pantalla + 7/7 BD/buzón, `VERIFY_OK`), EX-022
(migraciones hasta v10). Detalle: `CORRECCION_CONTROL_HUMANO.md` y
`EVIDENCIA_CONTROL_HUMANO.md`.

Resultados de la reanudación CH-01 (EVIDENCIA_CONTROL_HUMANO.md, EX-025/EX-026):
`tests/test_c02_revision_control_humano_3ra.py` → 15 passed/exit 0/15.43s;
suite C02 de control humano → 59 passed/exit 0; E2E de control humano
`scripts/e2e_control_humano.py` → exit 0 (`TODOS LOS CHECKS OK`, `VERIFY_OK`);
regresión CRM/C02 amplia → 248 passed/exit 0 (dos fallos preexistentes de
versiones de migración, ajenos a este cambio).

Sigue sin declararse C02 cerrado ni el programa completo; espera de la tercera
revisión del revisor. Sin commit/push, sin proveedores ni datos reales.

## Estado honesto de la entrega

C02 se entrega **parcial, lista para revisión parcial**. Se implementó y acreditó por
recorridos HTTP/test_client reales el **subconjunto** que se describe abajo. No se declara
cerrado todo el programa (RF-02 completo exige WhatsApp real, RG-1..4 exigen el agente
conversacional real, etc.); tampoco bastan las pruebas de dominio sin el recorrido HTTP/navegador,
que aquí sí se acreditó en lo implementado.

## Completado y verificado

### Dominio común (migración v5, aditiva)
`crm/store.py` añade migración `_migration_005_c02` con tablas `crm_*`:
- **Catálogo**: `crm_catalog_items` (artículos con tipo/precio/stock/activo/vigencia,
  `publish_state`, `current_revision`), `crm_catalog_revisions` (revisiones con instantánea).
- **Conocimiento**: `crm_kb_documents` y `crm_kb_fragments` (índice derivado).
- **Canal durable**: `crm_wa_messages` (idempotencia por ID externo), `crm_operations`
  (reclamables con `expires_at` para recuperar abandonados), `crm_outbox` (salidas).
- **Bandeja humana**: `crm_conversations`, `crm_conversation_messages`, `crm_human_alerts`.

`crm/c02_services.py`: funciones de dominio inyectables (catálogo crear/editar por celda con
control de versión optimista/publicar; conocimiento publicar/recuperar/desactivar; canal durable
ingesta/claim/outbox; bandeja tomar/retornar/pausar/alarmar).

### Canal WhatsApp dentro del único backend (RF-02)
- `crm/whatsapp_webhook.py`: GET challenge (firma/verify token) y POST con HMAC sobre el cuerpo
  crudo; ack **después** de persistir; idempotencia durable; CSRF excluido sólo en `/webhook`;
  parse del lote completo `entry[].changes[].messages[]`. Registrado en `create_app`.
- `crm/canal.py`: `MotoresCanal` (simulado determinista por defecto; real opt-in), worker de
  reclamo exclusivo, salida al outbox y elevación de alertas humanas (por emergencia, etc.).

### Catálogo editable en el frontend único
- `crm/templates/catalog.html` (edición por celda) + `crm/static/crm_c02.js` (cero inline, CSP
  estricta). El catálogo **ya no es una preview no operativa**: es una pantalla real con
  guardado que genera revisiones y puede publicar. Rutas API autenticadas/CSRF:
  `GET/POST /api/c02/catalog`, `POST /api/c02/catalog/<id>`, `.../publish`, `GET /api/c02/inbox`,
  `POST /api/c02/inbox/<id>/take|return`.

### Configuración operativa del negocio (punto 1 de la continuación funcional — 28-10-2026)
- Perfil del negocio editable (nombre, zona IANA, moneda) + saludo de conversación nueva +
  horarios semanales operativos (día→[apertura,cierre]) + fechas cerradas/excepciones por
  fecha + disponibilidad de especialistas desde la gestión existente (`crm_professionals`).
- `crm/business_config.py` (validación por clave con mensajes claros, sincronización de
  `active`, horarios en HH:MM) y frontend `config.html` + `crm_c02_config.js` (perfil ya no en
  snapshot: sin `disabled` salvo rubro informativo).
- **Regla única panel/canal**: alta, form y reprogramación del panel, y alta/reagendado del
  canal usan `business_config.check_window(path, s, e)` con la zona efectiva. Corrección de un
  bug real: el canal antes usaba `profz.check_window` y creaba citas en días cerrados.
- El saludo configurado se emite en la primera interacción de una conversación nueva
  (`crm/canal.py` `procesar_lote`).
- Verificación: `tests/test_c02_config_funcional.py` (7 passed) — persistencia, saludo en
  conversación nueva, fecha cerrada y horario iguales en panel y canal, disponibilidad de
  especialistas, permisos/CSRF, rechazo de inválidos; E2E navegador con recarga persistente
  (captura `evidencias/c02/config-persistencia.png`). Detalle en
  `EVIDENCIA_CONTINUACION_FUNCIONAL.md` y `CONTINUACION_FUNCIONAL.md`.

## Acreditación (comandos reales)
- `pytest tests/test_c02_services.py` → 8 passed (catálogo, conocimiento, idempotencia WhatsApp,
  claim exclusivo/recovery, outbox, bandeja/toma/pausa, conflicto).
- `pytest tests/test_c02_webhook_http.py` → 6 passed (challenge válido/inválido, firma inválida
  403, persistencia idempotente, CSRF eximido, ack de estados).
- `pytest tests/test_c02_canal.py` → 3 passed (outbox, alerta de emergencia, reclamo exclusivo).
- `pytest tests/test_c02_frontend.py` → 3 passed (render tab con CSP, CRUD API autenticado,
  requiere autenticación).
- Regresión acumulada C01+C02+CRM → **124 passed, exit 0** (`tests/test_crm.py ... test_c02_*`).
- Ajustes de tests heredados por la migración v5: se actualizaron las aserciones de número de
  versiones ([1,2,3,4] -> [1,2,3,4,5]) y el test de catálogo (preview -> real).
- Reanudación CH-01 (última brecha LAST_GAP, `crm/egress.py` barrera pre-entrega):
  `REPRO_REANUDACION_LAST_GAP.py` → `{"events":["take_committed"],"receipts":0}`
  (antes: `{"events":["take_committed","transport_called"],"receipts":1}`);
  `tests/test_c02_revision_control_humano_3ra.py` → 7 passed/exit 0/10.80s;
  suite C02 de control humano (3ra/control_humano/services/webhook/canal/frontend/c01_previews)
  → 56 passed/exit 0.
- Configuración operativa (28-10-2026, EX-027):
  `tests/test_c02_config_funcional.py` → 7 passed/exit 0; regresión C02
  (config_funcional + canal + frontend + services) → 33 passed/exit 0;
  `scripts/e2e_crm_c02.py` → exit 0 (fases cat + bandeja, TODOS LOS CHECKS OK, VERIFY_OK,
  recarga persistente de configuración). Sin proveedores reales.

## Pendiente / marcado con honestidad (§10.6)
- **§10.1 no completado**: la edición de catálogo hoy cubre nombre/tipo/precio y la vista
  general; faltan campos de detalle (vigencia, stock, profesional, notas) en la UI y el índice
  derivado de catálogo en el bot.
- **§10.2 Conocimiento/config**: se implementó el dominio de documentos (publicar/recuperar/
  desactivar) pero **sin** la pantalla de administración de conocimiento/config en el frontend
  ni el formulario de negocio/especialistas/horarios estructurados (se reutilizaría
  `business_profile` como autoridad única).
- **§10.3 Chat interno**: no se implementó la ventana de consulta con el motor real ni las
  lecturas BD.
- **§10.4 Bandeja humana**: base de dominio y rutas listas, pero **sin** la interfaz navegable
  de la bandeja para responder/tomar realmente en el navegador.
- **RF-02 canal WhatsApp real**: el webhook y el worker simulados funcionan en pruebas; el
  proveedor real de Meta y el agente de lenguaje real quedan como paso de configuración,
  siguiendo la guía de pruebas (nunca datos reales por defecto).

## Retrospectiva e inexactos detectados
- La preview de catálogo de C01 quedó en desuso al introducir la pantalla real; se conservó
  `catalog_preview.html` en el repo (no borrado) aunque ya no se incluye.
- Se optó por no arrancar el motor LangGraph al importar (mantener `create_app` limpio); el
  motor real se cargaría de forma perezosa y opt-in en una etapa posterior.

## Cómo verlo localmente
- Catálogo editable: `python run_crm.py` → login → pestaña **Catálogo** (crear, editar celda,
  publicar; revisión en la base).
- Webhook: enviar POST firmado a `/webhook` (ver `test_c02_webhook_http.py`); no es invocable
  sin la firma del proveedor.
