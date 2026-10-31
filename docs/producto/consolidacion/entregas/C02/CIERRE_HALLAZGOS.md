# CIERRE DE HALLAZGOS — Corrección C02 (R1–R5)

Fecha: 2026-10-27 (UTC). Rama: `main` (sin commit). HEAD de referencia: db6194c.
Raíz: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`.
Dictamen parcial por módulo (como exige la devolución): **aprobar catálogo no acredita pausa humana**.

Convención de columnas: **Reproducción** (comportamiento que el revisor o la prueba observó) ·
**Causa** · **Cambio** · **Archivo/símbolo** · **Prueba** · **Ejecución/evidencia** · **Estado** · **Pendiente**.

Los casos base (R1 catálogo bloqueado, R2 0 citas, R3 salida IA tras toma, petición explícita)
se convirtieron en regresiones de fixtures primero (debían fallar por la causa esperada) y en
verdes tras la corrección. Ejecuciones reales en `../REGISTRO_EJECUCIONES.md` (EX-011..EX-016).
No se infló ningún conteo: se suman pruebas nuevas y se registran comandos y resultados reales.

---

## R1 — Catálogo bloqueado → operativo y completo (estado: APROBADO en su alcance)

### R1.1 Carga catastrófica y contrato JS/API
- Reproducción: GET `/api/c02/catalog` devuelve `{items:[...]}`, pero el JS pasaba el objeto a
  `render(items)` y hacía `items.forEach` → error en consola, tabla oculta y «Cargando catálogo...».
- Causa: `crm_c02.js` no extraía `items` del payload (`catalog_list` devuelve `{"items":…}`).
- Cambio: el JS lee `j.items`; añadido control de error inicial con reintento (`#c02-cat-retry`)
  y sin spinner eterno.
- Archivo: `crm/static/crm_c02.js` (`reload`, `flash`, manejo de `retryBtn`).
- Prueba: `tests/test_c02_frontend.py::test_catalog_tab_render_con_csp_estricta`,
  `test_catalog_api_crud_autenticado` (catálogo vacío y con artículos).
- Ejecución/evidencia: EX-011 (16 PASS). Navegador real con catálogo vacío y con artículos en EX-015.
- Estado: **Cerrado**. Pendiente: ningún caso de consola/spinner; verificación de accesibilidad
  teclado/móvil queda como verificación de revisión (no automatizada aquí).

### R1.2 Edición por celda y detalle
- Reproducción: no había edición completa por celda ni detalle; foco perdido podía guardar.
- Causa: control de celda y dialog de detalle ausentes en la entrega parcial.
- Cambio: edición por celda (Enter/Guardar confirma, Escape/Cancelar descarta, no guarda por
  perder foco), detalle por artículo con dialog; doble envío protegido y borrador conservado en
  error; detección de revisiones concurrentes (409 no da aviso de éxito).
- Archivo: `crm/static/crm_c02.js` (celdas, dialog, submit), `crm/templates/catalog.html`,
  `crm/app.py` (rutas detalle/revisiones), `crm/c02_services.py` (`catalog_detail`).
- Prueba: `tests/test_c02_frontend.py::test_catalog_api_crud_autenticado` (incluye 409 y revisión vieja).
- Ejecución: EX-011. Estado: **Cerrado**. Pendiente: ninguno en alcance.

### R1.3 Campos y separación observaciones públicas / notas internas
- Reproducción: sin separación de notas internas.
- Causa: campo único en el esquema.
- Cambio: `public_notes` vs `internal_notes`; el backend no expone ni permite escribir
  `internal_notes` a no-admin (`catalog_list`/`catalog_detail` con filtro, `catalog_update` con
  rol); montón para público sin notas internas.
- Archivo: `crm/c02_services.py` (`catalog_list`, `catalog_detail`, `catalog_update`,
  `catalog_item_public`), `crm/app.py`.
- Prueba: `tests/test_c02_services.py::test_catalog_revisions_history`,
  `test_catalog_public_snapshot_and_revalidation`, `test_c02_frontend.py::test_knowledge_editor_crud_and_admin_only`
  (patrón admin-only).
- Ejecución: EX-011. Estado: **Cerrado**. Pendiente: ninguno.

### R1.4 Publicación y realidad de revisiones/precio/stock/activo
- Reproducción: botón «Re-editar» que volvía a publicar; precio vacío como cero y stock cero como
  desconocido era ambiguo.
- Causa: semántica de precio/stock en db parcial.
- Cambio: precio vacío ≠ 0 (NULL); stock 0 ≠ desconocido separado por `stock_na`; activo/stock/
  vigencia se revalidan en la instantánea pública; desactivar impide nuevas ofertas conservando
  historia/citas. Una revisión borrador no se filtra al público.
- Archivo: `crm/c02_services.py` (`catalog_item_public`, `catalog_deactivate`, revisión).
- Prueba: `tests/test_c02_services.py::test_catalog_public_snapshot_and_revalidation`.
- Ejecución: EX-011. Estado: **Cerrado**. Pendiente: ninguno.

---

## R2 — Worker no creaba citas → reserva/reagenda/cancelación reales (estado: APROBADO en alcance)

### R2.1 Continuación de diálogo y operaciones comunes reales
- Reproducción: `wa_ingest('quiero reservar mañana 10:30')`, `worker.paso()`,
  `wa_ingest('mañana 10:30')`, `worker.paso()` → **0 filas de cita**; `procesar_lote` sólo
  preparaba el primer mensaje, no continuaba ni ejecutaba el dominio.
- Causa: el worker no llevaba contexto por conversación ni llamaba a las operaciones comunes.
- Cambio: `crm/canal.py` reescrito con contexto durable por conversación (migración **v6**:
  `pending`, `egress_paused`), multi-turno persistente y ejecución real de
  `save_appointment`/`cancel_appointment`/`reprogram_appointment` (dominio `reservation_service`),
  con selección de servicio/especialista/fecha-hora, solicitud de faltantes, confirmación y
  control transaccional de solape; servicio de duración consultado (no fijo).
- Archivo: `crm/canal.py` (worker y motor), `crm/c02_services.py` (`conv_by_key`,
  `conv_set_pending`/`clear_pending`, `conv_egress_paused`, `appointments_for_lead`),
  `crm/store.py` (migración v6).
- Prueba: `tests/test_c02_canal.py::test_worker_reserva_crea_cita_real`,
  `test_worker_dialogo_multiturno_reserva`, `test_worker_cancelacion_confirmada`.
- Ejecución: EX-012 (9 PASS). Evidencia: cita persistida que el frontend agenda consulta.
- Estado: **Cerrado**. Pendiente: adaptadores generativos reales (LLM/perfil) quedan como
  integración opt-in/configurada, no simulada en la aceptación del recorrido sintético.

---

## R3 — Pausa humana y petición explícita de humano (estado: APROBADO en alcance)

### R3.1 No hay salida IA tras la toma de humano
- Reproducción: `conv_take` + entrada + worker aún añadía 1 salida a `crm_outbox`.
- Causa: un helper de pausa que el worker no llamaba no protegía el canal.
- Cambio: el worker consulta `conv_confirm_pause` antes de generar/encolar cualquier salida IA
  y respeta `egress_paused` durante todo el diálogo; la toma de control queda durable hasta
  «Devolver a IA».
- Archivo: `crm/canal.py`, `crm/c02_services.py` (`conv_confirm_pause`), migración v6.
- Prueba: `tests/test_c02_canal.py::test_worker_pausa_humana_bloquea_salida`,
  `test_worker_pausa_humana_tras_ingesta_dialogo`.
- Ejecución: EX-012. Estado: **Cerrado**.

### R3.2 Petición explícita de humano sin marcador de LLM
- Reproducción: `MotorSimulado.intencion('quiero hablar con un humano',{})` devolvía `consulta`
  (dependía de un marcador LLM).
- Causa: no había detección directa de la intención explícita.
- Cambio: el worker reconoce la petición explícita («hablar con un humano», etc.) y deriva a
  `humano_explicito` sin depender del marcador generado por LLM.
- Archivo: `crm/canal.py`, `crm/c02_services.py`.
- Prueba: `tests/test_c02_canal.py::test_worker_peticion_explicita_humano`.
- Ejecución: EX-012. Estado: **Cerrado**.

---

## R4 — Ventanas obligatorias de la sección 10 (estado: APROBADO en alcance)

- **10.1 Catálogo** → ver R1. Navegador real en EX-015.
- **10.2 Conocimiento y Configuración**:
  - Reproducción: editor documental/config no existía en la UI.
  - Cambio: editor de conocimiento (`#c02-kb-*`: crear/revisar/publicar/desactivar; detalle con
    cuerpo sólo-admin) y Config de IA (`crm_c02_config.js` + migración **v7** `crm_settings`:
    saludo/mensajes persisten; saludo sólo-admin).
  - Archivo: `crm/c02_services.py` (`kb_*`, `config_get_all`/`config_set`), `crm/app.py`,
    `crm/templates/config.html`, `crm/static/crm_c02_config.js`, `crm/store.py` (v7).
  - Prueba: `tests/test_c02_frontend.py::test_knowledge_editor_crud_and_admin_only`,
    `test_config_ai_admin_guarda_y_usuario_no_ve`.
  - Ejecución: EX-013, EX-015. Estado: **Cerrado**.
- **10.3 Chat interno (RAG + BD)**:
  - Cambio: `chat.html` + `crm_c02_chat.js`; `responder_chat_internal` combina `kb_search` (RAG
    sobre KB publicada) y `_agenda_summary` (BD agenda/profesionales).
  - Prueba: `tests/test_c02_frontend.py::test_chat_interno_responde_desde_kb_y_bd`.
  - Ejecución: EX-013 (respuesta en el navegador en EX-015). Estado: **Cerrado**. Pendiente:
    sustituir el motor determinista por un LLM real configurado (opt-in) sin cambiar el recorrido.
- **10.4 Bandeja humana**:
  - Reproducción: base de dominio y rutas, pero sin interfaz navegable.
  - Cambio: `inbox.html` + `crm_c02_inbox.js` (listar / tomar / responder como operador /
    devolver), reemplaza la preview de C01; el thread y el envío operan sobre `conv_add_message`.
  - Prueba: `tests/test_c02_frontend.py::test_inbox_api_take_reply_return`,
    `tests/test_c01_previews.py::test_inbox_tab_renders_operational_human_tray`.
  - Ejecución: EX-013 (API), EX-016 (navegador: tomar + responder, `['inbound','outbound']`).
  - Estado: **Cerrado**.

---

## R5 — E2E de navegador y trazabilidad (estado: en curso / entregado para revisión)

### R5.1 E2E en navegador real
- Cambio: `scripts/e2e_crm_c02.py` (bootstrap base sintética + server + runner Playwright) y
  `frontend/e2e/crm_c02.e2e.mjs` con fases `cat` y `bandeja`; verificación de persistencia sobre
  la base de fixtures (no sólo capturas).
- Ejecución/evidencia: EX-015 (fase `cat` TODOS OK; artículo/doc/saludo en DB) y EX-016 (fase
  `bandeja` TODOS OK; `['inbound','outbound']`). Capturas en `../evidencias/c02/`.
- Estado: **Entregado**. Pendiente: repetir puntualmente en otra máquina/sistema para
  confirmar ausencia de dependencia de timing (la creación de artículo emite 12 ediciones
  secuenciales sobre HTTP y se detecta por la DB de forma determinista).

### R5.2 Regresión y ajustes de tests heredados
- Migración v7 añadida al final; tests de versiones actualizados a `[1..7]` y recuento
  `crm_migrations 7`. `test_c01_previews` ajustado porque la pestaña Inbox pasó de preview a
  bandeja operativa (no se «arregló» para aceptar el fallo: se cambió la expectativa al nuevo
  comportamiento correcto de R4).
- Ejecución: EX-014 (**136 PASS**, ~143s). Estado: **Cerrado**.

---

## Segunda revisión de control humano — CH-01..CH-04 (27-10-2026)

Fuente: `REVISION_CONTROL_HUMANO_CODEX.md` (DEVUELTA; revisor intacto). Corrección
acotada a los cuatro hallazgos; detalle completo en `CORRECCION_CONTROL_HUMANO.md`
y evidencia real en `EVIDENCIA_CONTROL_HUMANO.md` (EX-017..019).

- **CH-01 — IA después de tomar el chat (alta).** Barrida: la validación sólo
  ocurría al reclamar (`outbox_claim`); la toma entre reclamo y envío salía igual.
  Cambio: admisión efectiva al envío (`outbox_admitir`, migración **v9** estado
  `autorizado`/`en_vuelo`), transacción corta `BEGIN IMMEDIATE` justo antes del
  transporte; nunca transacción abierta durante llamadas externas; criterio
  explícito de en vuelo (la admitida antes de la toma puede llegar; se muestra,
  el resto se invalida). Pruebas: `tests/test_c02_revision_control_humano.py`
  (toma entre reclamo y envío, tareas múltiples, barrera determinista, en vuelo).
  Estado: **Cerrado con la semántica documentada** (ver nota honesta en
  CORRECCION sobre el punto de inyección de la reproducción del revisor).
- **CH-02 — Respuestas duplicadas (alta).** Recepción seguida de acuse perdido
  se marcaba `fallo` y se reenviaba → 2 recepciones. Cambio: triestado
  `enviado`/`fallo`(cierto)/`incierto`(timeout); `outbox_requeue` bloquea
  `incierto`/`autorizado` (devuelve `bloqueados`) y `invalidada`; reenvío sólo
  con `outbox_reconciliar(..., asumir_idempotente=True)`; el transporte simulado
  demuestra idempotencia del destino (dedupe por request_id/correlación+payload):
  **una sola recepción**. Pruebas: `test_ch02_acuse_perdido_una_sola_recepcion`,
  `test_ch02_fallo_cierto_si_reenvio_permitido_una_recepcion`, HUM-10
  actualizado. Estado: **Cerrado**.
- **CH-03 — Estado de entrega y navegador.** Bandeja: refresco por firma de
  estados de entrega (cola → admitido/en vuelo → entregado/incierto), nuevos
  badges. `scripts/e2e_control_humano.py`: corregido `KeyError: origin` (la
  consulta de verify no traía la columna) y `esperar_resultado` con polling
  acotado sobre estados durables (sin sleeps para ocultar fallos). E2E completo
  exit 0 con comprobaciones en pantalla + base temporal + buzón (EX-019, 5/5
  Playwright + 7/7 verify). Estado: **Cerrado**.
- **CH-04 — Documentación.** Creados `CORRECCION_CONTROL_HUMANO.md` y
  `EVIDENCIA_CONTROL_HUMANO.md`; actualizados CIERRE (esta sección), ENTREGA,
  MATRIZ (HUM-01..12 + CH-01/02), REGISTRO (EX-017..019) y ESTADO. Informes del
  revisor intactos. Estado: **Cerrado**.

Regresión completa con bases temporales (EX-017): **88 passed, exit 0, 49.17s**
(82 del revisor + 6 regresiones nuevas). EX-018: **32 passed** (migraciones v9).
EX-019: E2E **exit 0** y `VERIFY_OK`.

---

## Tercera revisión de control humano (REVISION_CONTROL_HUMANO_02_CODEX.md) — 27-10-2026

Fuente: `REVISION_CONTROL_HUMANO_02_CODEX.md` (requiere DOS correcciones; revisor
intacto). El dictamen reabrió CH-01 y CH-02 con reproducciones propias:

- **CH-01 reabierto — autorización local ≠ aceptación del transporte.** El
  revisor inyectó la toma DENTRO del transporte (tras `outbox_admitir`) →
  `RACE {"state":"humano_asignado","ai_received_after_take":1}`. No acepta
  renombrar estados como criterio. Corrección (tercera iteración): el reclamo
  (`outbox_claim`/v10) registra la PROPIEDAD del trabajo (`claimed_by`/
  `claimed_at`), y `outbox_admitir` se sustituye por **`outbox_begin_send`**:
  el COMIENZO EFECTIVO del transporte, transacción corta commiteada antes de la
  llamada externa que linealiza la carrera toma-vs-comienzo. Toma antes del
  comienzo ⇒ invalidada, cero efectos externos; comienzo ya ganado ⇒ en vuelo
  explícito registrado y mostrado. SQLite BEGIN IMMEDIATE = coordinación entre
  procesos (sin bloqueo global de Python).

  **Última brecha (LAST_GAP) cerrada en la reanudación:** la reanudación
  verificó con `REPRO_REANUDACION_LAST_GAP.py` que la marca `began_at` de
  `outbox_mark_sending` (v11) por sí sola NO cerraba la carrera: quedaba una
  ventana entre el commit del CAS y `transporte.deliver`, y una toma confirmada
  en esa ventana seguía dejando salir 1 mensaje IA
  (`{"events":["take_committed","transport_called"],"receipts":1}`). La relectura
  aislada posterior (`_conv_ia_bloqueada`) tampoco acreditó coordinación
  (`READ_GAP {"events":["take_committed_after_read","transport_called"],"receipts":1}`).
  Se sustituyó por una **exclusión mutua compartida por conversación**
  (`crm/conv_lock.py`) que usan tanto el consumidor de salida como `conv_take`,
  y que abarca la decisión final y la llamada al transporte: el egress adquiere
  el bloqueo ANTES de `outbox_mark_sending` y lo conserva durante
  `transporte.deliver` (sin transacción SQLite abierta durante la red; llamada
  al transporte con timeout acotado). `conv_take` adquiere el mismo bloqueo,
  nunca espera indefinidamente (si otro proceso está entregando, informa
  `envio_en_curso` y permite reintentar). Ahora:
  `{"events":["take_committed"],"receipts":0}` (`transport_called` ausente).

  **Identidad canónica de bloqueo en Windows (esta reanudación):** `crm/conv_lock.py:_db_identity`
  combina `os.path.realpath` (resuelve junction/symlink y convierte la ruta a
  absoluta) con `os.path.normcase` (unifica mayúsculas/minúsculas en Windows),
  de modo que `_lock_path` produce el mismo archivo de bloqueo para distintos
  caminos que apuntan a la misma BD. El lock file se ubica junto a la ruta real
  de la base. Alias soportados: diferencias de mayúsculas/minúsculas, rutas
  relativas y absolutas equivalentes, y alias por junction/symlink. No
  soportados: hardlinks ni rutas de red (no probado). Verificación:
  `LOCK_ALIAS {"same_database_file":true,"same_lock_path":true,"both_acquired":false}`;
  la toma vía alias mientras otro proceso entrega devuelve `ok=False` con
  `envio_en_curso>=1` y no confirma.
  Estado: **Cerrado (reanudación, exclusión mutua real entre procesos con
  identidad canónica de bloqueo en Windows)**.

- **CH-02 reabierto — tarea ya entregada reencolable.** El revisor:
  `outbox_requeue(outbox_id=<enviado/entregado>)` → reencoló y consumió otra vez
  → `SENT_TASK_RETRY {"requeued":1,"receipts":2}`. Corrección (tercera
  iteración): **lista explícita de estados recuperables** con actualización
  atómica (comparación de estado/attempts/propiedad): sólo `intento` vencida y
  `fallo` cierto no `invalidada`; `enviado`/`invalidada`/`incierto`/`autorizado`
  sin reconciliación válida y claims activos NUNCA se recuperan (quedan en
  `bloqueados` con motivo). Prueba obligatoria: reintentar un ID entregado ⇒
  `requeued=0` y **una sola recepción** (`test_ch02_enviada_reintentar_id_requeued_0_y_una_recepcion`).
  Estado: **Cerrado (3ª iteración)**.

Regresión de la 2ª revisión + nuevas (EX-020): **124 passed, exit 0, 64.97s**
(120 del revisor + 4 nuevas netas; `test_c02_revision_control_humano.py`: 10).
Regresiones de la exclusión mutua (EX-025/EX-026 de esta reanudación):
`test_c02_revision_control_humano_3ra.py` → **15 passed, exit 0, 15.43s**;
suite C02 de control humano → **59 passed, exit 0**; regresión CRM/C02 amplia
→ **248 passed, exit 0** (dos fallos preexistentes de versiones de migración,
ajenos a este cambio). E2E de control humano (EX-021, repetido): **exit 0**,
5/5 pantalla + 7/7 BD+buzón, `VERIFY_OK`. Migraciones hasta **v11**
(`[1..11]`). Informes del revisor intactos.

---

## Resumen global
- R1–R4: **cerrados** con pruebas y evidencia de navegador (EX-011..EX-016).
- R5: **entregado** con regresión 136 PASS y E2E en verde; queda la confirmación de estabilidad
  de timing en otra máquina.

## Pendientes de la entrega completa (fuera de R1–R5)
- Intenciones/agente generativo (LLM) reales opt-in y configurados, sin sustituir el recorrido
  sintético ya acreditado.
- Provedores reales externos (Meta WhatsApp, Google Calendar) bajo la guía de pruebas con
  autorización específica (nunca reales por defecto). Nunca se usaron datos de clientes.
- Revisión independiente de este cierre por el rol revisor antes de pasar a C03.


## Revisión independiente REV-CANONICA-20261027
CH-01 aprobado en escenarios ejecutados; 139 tests y E2E PASS. Identidad canónica Windows validada, incluyendo junction y ruta relativa reales. No reabrir CH-01 sin regresión nueva. C02 conserva pendientes fuera de control humano. Dictamen: APROBACION_CH01_IDENTIDAD_CANONICA_CODEX.md.
