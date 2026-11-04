# Matriz de trazabilidad

Una fila por subrequisito verificable asociado a un ID RF. La evidencia de ejecuciones
anteriores no se sobreescribe; se añade en `REGISTRO_EJECUCIONES.md`. Esta matriz se
actualiza en cada entrega.

Estados posibles: PENDIENTE | EN CURSO | IMPLEMENTADO SIN VERIFICAR | VERIFICADO EN SIMULACIÓN |
VERIFICADO CON PROVEEDOR DE PRUEBA | BLOQUEADO | DEVUELTO | ACEPTADO POR REVISOR.

Nota: un subrequisito "VERIFICADO EN SIMULACIÓN" en C01 acredita que el comportamiento
funciona contra bases temporales y adaptadores simulados. No acredita comunicación real con
WhatsApp/Google.

## RF-01 Producto único

| ID | Comportamiento esperado | Implementación | Prueba / evidencia | Estado | Entrega |
|---|---|---|---|---|---|
| RF-01-01 | Un frontend Flask/Jinja/JS activo que sirve las páginas del producto | `crm/app.py`, `crm/templates/*`, `crm/static/*` | tests/test_crm.py + E2E C01 (desktop/ux) | VERIFICADO EN SIMULACIÓN (parcial) | C01 |
| RF-01-02 | Un acceso de usuarios por sesión+CSRF, no API key SaaS para empleados | `/login`, `@protected`, `@protected_api` en `crm/app.py` | tests/test_crm.py::test_auth_and_csrf + E2E (sesión inválida redirige a /login) | VERIFICADO EN SIMULACIÓN (parcial) | C01 |
| RF-01-03 | Arranque documentado: `python run_crm.py` en 127.0.0.1:8050 | `run_crm.py` (con CRM_HOST/CRM_PORT/CRM_THREADED) | E2E C01 | VERIFICADO EN SIMULACIÓN (parcial) | C01 |

## RF-02 Reservas por WhatsApp y panel

| ID | Comportamiento esperado | Implementación | Prueba / evidencia | Estado | Entrega |
|---|---|---|---|---|---|
| RF-02-01 | Crear cita por panel con solapamiento rechazado | `save_appointment` en `crm/reservation_service.py` + POST `/api/appointments` | tests/test_crm.py::test_overlaps_reprogramming_and_cancellation + E2E desktop (crear) | VERIFICADO EN SIMULACIÓN (panel) | C01 |
| RF-02-02 | Consultar/recargar cita desde panel | GET `/api/agenda`, `/api/appointments/<id>` | E2E C01 (persiste tras recargar) | VERIFICADO EN SIMULACIÓN (panel) | C01 |
| RF-02-03 | Reagendar y cancelar con historial y permisos | `reprogram_appointment`, `cancel_appointment` | tests/test_crm.py + E2E C01 (reagenda/cancel) | VERIFICADO EN SIMULACIÓN (panel) | C01 |
| RF-02-04 | Crear/reagendar/cancelar por WhatsApp y bot con el mismo servicio e ID | Webhook `/webhook` + worker (`crm/canal.py`) sobre `reservation_service` | test_c02_webhook_http.py + test_c02_canal.py (recorrido simulado; servicio común) | VERIFICADO EN SIMULACIÓN (canal service + worker) | C02 |
| RF-02-06 | Selección explícita en el canal: servicio activo/publicado, duración del servicio, profesional compatible, y cancelar/reagendar con selección por ID de las citas del cliente | `crm/canal.py` (`_servicios_activos`, `_profesionales_activos` con la BD como fuente de `active`, `_reservar_conn` con revalidación en la transacción, bloques `cancelar`/`reagendar` con `_opcion_numerica`) sobre `reservation_service` | tests/test_c02_seleccion_cita.py (12 tests: las 9 verificaciones obligatorias del punto 2 + SEL-01) | VERIFICADO EN SIMULACIÓN (canal + dominio, panel/canal misma regla) | C02 |
| RF-02-07 | SEL-01: revalidar la asociación servicio→profesional CON la misma conexión del INSERT (no confiar en compatibles previos); si cambió, no insertar ni confirmar, refrescar opciones y pedir otra selección conservando servicio/fecha/hora | `crm/canal.py:_reservar_conn` (SELECT con `professional_id` + código `seleccion_caducada` con opciones actuales releídas) y `_run_dialog` (mensaje claro + pending sin `profesional_id` obsoleto) | tests/test_c02_seleccion_cita.py::test_sel01_reasignacion_servicio_en_pre_escritura + test_sel01_servicio_sin_restriccion_conserva_flujo | VERIFICADO EN SIMULACIÓN (red→green frente a la reproducción del revisor) | C02 |
| RF-02-05 | Canal WhatsApp real con Meta y agente de lenguaje real | `TransporteWhatsAppReal` (transporte_whatsapp.py) + `MotorIA` (canal) + worker (worker.py) + webhook `statuses[]` | tests/test_c02_whatsapp_real.py (7 tests con fake Graph API) | TRANSPORTE REAL IMPLEMENTADO Y PROBADO EN LOCAL; **validación EXTERNA pendiente** (autorización config del propietario) | C02 |

### WhatsApp real — 2026-10-28 (WH-REAL)

| Arista | Estado | Evidencia |
|---|---|---|
| Envío por API oficial vigente (v21.0, Bearer, wamid) | VERIFICADO EN LOCAL (fake) | test_c02_whatsapp_real.py + EVIDENCIA_WHATSAPP_REAL.md |
| Aceptación ≠ entrega; estados sent/delivered/read/failed por webhook | VERIFICADO EN LOCAL | ídem (casos 3 y 4) |
| Timeout incierto sin reenvío ciego; reconciliación explícita | VERIFICADO EN LOCAL (WH-01: UNA sola petición) | test_c02_whatsapp_real.py (caso 5) + WH-FIX |
| Toma humana antes del envío (cero efectos) y respuesta humana por el mismo transporte | VERIFICADO EN LOCAL | ídem (casos 6 y 7) |
| Falta de configuración → indisponibilidad explícita, sin simulación | VERIFICADO EN LOCAL | ídem (caso 8) |
| Worker: parada ordenada, recuperación de abandonados, no duplica por petición | VERIFICADO EN LOCAL | ídem (caso 9) + humo worker |
| Configuración compartida web↔worker (.env) | VERIFICADO EN LOCAL (WH-02) | test_worker_carga_env_sintetico_compartido |
| Validación EXTERNA real con Meta (lote A-F de saludo, base ficticia, túnel temporal autorizado) | **EN ESPERA (2026-10-30 (10))** — token VÁLIDO (revisor: HTTP 200 verified_name); preparación recuperada e intacta (base 0/0/0, scripts presentes, procesos detenidos, autorizaciones constan). ÚNICO pendiente: la red — el filtro DNS de perímetro Whalebone (`Whalebone Sinkhole CA`, IP hundimiento 190.89.44.242) persiste y bloquea el handshake del agente ngrok de Store; esperando la acción del propietario (conexión propia donde ngrok esté permitido o autorización del administrador). Al confirmar: re-sonda red → ngrok Store → URL /webhook → registro en Meta → "hola" → A-F | CKPT-WHVAL-RED-20261030 |
| WH-07 | Biblioteca de envíos (panel): historial de mensajes del outbox en vista de solo lectura (fecha, canal, destinatario, estado, estado del proveedor, intentos, eventos, wamid); NO reenvía ni muta; aclara que la aprobación de plantillas la confirma Meta (borrador ≠ aprobado) | `GET /api/c02/outbox`, `c02_services.outbox_history()`, `envios.html` + `crm_c02_envios.js` (nuevos 2026-10-29) | test_c02_frontend_rediseno.py::test_biblioteca_envios_solo_lectura + verificación en navegador real (capturas rediseno-20261029) | VERIFICADO EN LOCAL (rediseño 2026-10-29) | C02 |
| Estado temprano antes del wamid (durable y reconciliado) | VERIFICADO EN LOCAL (WH-03) | test_estado_temprano_no_se_pierde_y_se_reconcilia |
| Fallo antiguo no bloquea evidencia posterior (WH-03-B) | VERIFICADO EN LOCAL (2026-10-29) | _aplicar_evento_estado acumulativo+cronológico; 80 PASS/exit0 (selección revisor+6 nuevas); probe independiente OK |
| WH-03-B re-verificación tras modificación de 2 pruebas (orden de eventos y consulta de agenda del MotorIA por la FECHA de la cita) | VERIFICADO EN LOCAL (2026-10-29 checkpoint) | regresión completa `tests/test_c02_whatsapp_real.py` → **17 passed, exit 0**; `-k wh03b` → **6 passed, exit 0**; la causa del ajuste de agenda se confirmó: `_dias_util(offset=2)` desde jueves/viernes cae en el lunes siguiente, fuera de la ventana semanal del día de ejecución → la consulta por la fecha de la cita hace la verificación determinista SIN debilitar la aserción (misma cita id visible) |
| Fuera de ventana sin plantilla explícita (sin sustitución) | VERIFICADO EN LOCAL (WH-04) | test_fuera_ventana_no_sustituye_por_plantilla_generica |
| Recorrido positivo MotorIA (IA real local + envío real local) | VERIFICADO EN LOCAL (WH-FIX) | test_recorrido_positivo_motor_ia |
| Llamada REAL a Meta (número/configuración/autorización del propietario) | **PENDIENTE (EXTERNO)** | 2026-10-30 (6): autorización del propietario REGISTRADA (túnel temporal + lote ≤3 respuestas ...1132); token válido (200 'Test Number'); proxy 8931 y worker acotado de entradas ACTIVOS sobre la base ficticia (0/0/0); **túnel externo BLOQUEADO** por TLS de la red (pyngrok/cloudflared/localtunnel/localhost.run fallidos; sin URL pública → Meta no puede entregar el webhook). Ver VALIDACION_WHATSAPP_EXTERNA.md §4.3 |

Nota: RF-02 completo exige WhatsApp; no se acredita sólo con agenda web en C01.

## RF-03 Calendario interno y Google

| ID | Comportamiento esperado | Implementación | Prueba / evidencia | Estado | Entrega |
|---|---|---|---|---|---|
| RF-03-01 | Agenda día/semana/mes por especialista con detalle | `agenda_time.py`, `agenda.js`, `/api/agenda` | tests/test_crm.py + E2E C01 (desktop) | VERIFICADO EN SIMULACIÓN | C01 |
| RF-03-02 | Cliente/especialista correctos en la cita | formulario/JS agenda | E2E C01 | VERIFICADO EN SIMULACIÓN | C01 |
| RF-03-03 | Operación independiente de Google + estados de sincronización separados | `sync_status`, `origin`, `channel` | E2E C01, tests/test_crm.py | VERIFICADO EN SIMULACIÓN (local) | C01 |
| RF-03-04 | Sincronización visible y recuperable con calendario autorizado | No acreditado contra Google real | — | PENDIENTE | — |

## RF-04 Recordatorios configurables

Sin subrequisitos en C01. Estado PENDIENTE.

## RF-05 Catálogo y conocimiento editable

| ID | Comportamiento esperado | Implementación | Prueba / evidencia | Estado | Entrega |
|---|---|---|---|---|---|
| RF-05-01 | Previsualización sintética claramente rotulada de Catálogo | Plantilla de previsualización C01 (no operativa) | Inspección visual / captura | REEMPLAZADO en C02 por catálogo real | C01/C02 |
| RF-05-02 | Editar/publicar catálogo con ID estable y notas internas separadas | `catalog.html` + `crm_c02.js` + `POST /api/c02/catalog` (revisiones y conflicto optimista) | test_c02_frontend.py, test_c02_services.py | PARCIAL (promedio de campos; falta detalle completo) | C02 |

| RF-05-03 | Configuración del negocio (nombre/zona/moneda, saludo, horarios semanales, fechas cerradas, especialistas) desde UI con permisos y CSRF | `config.html` + `crm_c02_config.js` + `POST /api/c02/config` (`business_config`) | test_c02_config_funcional.py + E2E C02 fase cat (recarga persistente) | VERIFICADO EN SIMULACIÓN | C02 |
| RF-05-04 | Conocimiento EDITABLE: crear/editar/previsualizar/publicar/desactivar documentos de texto/Markdown/PDF/.docx/.xlsx/.csv, con validación de formato y contenido, sin ejecutar macros/fórmulas/instrucciones del documento, .doc/.xls → "convierta a .docx/.xlsx", PDF escaneado identificado como no leído, procedencia (página/sección/hoja/fila), borrador→publicación→desactivación, separación público/privado, permisos admin + CSRF, sin publicación automática | `crm/c02_docs.py` (extracción stdlib), migración v12 en `crm/store.py`, `c02_services.kb_from_upload/kb_upsert/kb_publish/kb_list/kb_detail`, `POST /api/c02/knowledge(/upload/<id>/publish/<id>/deactivate)`, `crm_c02_docs.js`, `docs.html` (NUEVO: pantalla independiente «Conocimiento»; adaptado a guardar borrador / guardar y publicar / cancelar) | test_c02_docs.py (17 tests: extracción docx/pdf/xlsx/csv, escaneado, .doc/.xls, macros VBA, instrucciones maliciosas no mutan agenda/stock, CSRF, permisos, público/privado, revisión) + rediseño (29 pass frontend) | VERIFICADO EN SIMULACIÓN (punto 3 C02); pantalla separada verificada en rediseño 2026-10-29 | C02 |
| RF-05-05 | Importación de inventario por Excel/CSV en flujo separado y controlado: selección de hoja, mapeo de columnas a campos existentes, vista previa (nuevas/actualizaciones/duplicados/errores), identificación estable por ID/código (no nombre), confirmación explícita, registro del archivo/usuario/fecha/resultado, repetición sin duplicar; inventario CONTADO (absoluto) ≠ entradas/salidas; servicios sin stock → no aplica; fórmulas sin valor no adivinadas; filas ambiguas rechazadas | `crm/c02_inventory.py`, tabla `crm_inventory_imports` (migración v12), `POST /api/c02/inventory/{upload,preview,apply}` (+CSRF+admin), `crm_c02_inventory.js` (wizard; MODO-01: mapeo desde columnas reales de la hoja, sin lista fija A..H, opcionales ausentes sin usar) | test_c02_inventory.py (13 tests, incl. MODO-01) | VERIFICADO EN SIMULACIÓN (punto 3 C02) + MODO-01 verificado en navegador (13 checks) y E2E completo | C02 |

| RF-05-06 | Biblioteca de recursos PRIVADOS (PDF/txt/csv, catálogos, listas de precios): subida con permisos SEPARADOS de envío y RAG, versiones inmutables con trazabilidad, retirada sin borrado; plantillas WhatsApp declaradas localmente SIN aprobación falsificable (sólo Meta la confirma) | `crm/library.py` (NUEVO), migración v15 en `crm/store.py`, `POST/GET /api/c02/library*` + `plantillas*` en `crm/app.py`, `biblioteca.html` + `crm_c02_biblioteca.js` (pantalla independiente «Biblioteca de recursos»; el historial de envíos sigue en `envios.html`) | test_c02_biblioteca.py (9 tests) + regresión frontend+biblioteca (38 passed) + VERIFICADO EN NAVEGADOR REAL 2026-10-29 ronda C: 3 recursos + 1 plantilla en pantalla propia, diferenciada del historial de envíos (3 filas outbox) | VERIFICADO EN SIMULACIÓN Y NAVEGADOR REAL (existencia de crm/library.py y v15 comprobada en el árbol); aceptación humana PENDIENTE | C02 |

## RF-06 Profesionales y disponibilidad

| ID | Comportamiento esperado | Implementación | Prueba / evidencia | Estado | Entrega |
|---|---|---|---|---|---|
| RF-06-01 | Profesionales y calendarios locales editables | `/professionals`, `crm_professionals` | tests/test_crm.py::test_calendar_reassignment, test_roles | VERIFICADO EN SIMULACIÓN | C01 |
| RF-06-02 | Horarios/excepciones/fechas en datos estructurados | `negocio_horarios` (día→[apertura,cierre]), `negocio_excepciones` (fecha→estado/horario), `negocio_zona` en `business_config`/`config.html`; aplicados con la misma `check_window` en panel y canal | test_c02_config_funcional.py (persistencia, fecha cerrada y horario en panel+canal) + E2E config (recarga persistente) | VERIFICADO EN SIMULACIÓN | C02 |

| RF-06-03 | Agenda día/semana con tres citas coincidentes de profesionales DISTINTOS visibles y accesibles (ninguna inaccesible) | `agenda.html`/`agenda.js` (columnas por profesional, vistas día/semana) + demo %TEMP% con 3 citas a las 10:00 de profesionales 1/2/3 (2026-11-02) | VERIFICADO EN NAVEGADOR REAL 2026-10-29 ronda C: vista día «2 nov 2026» con 6 citas; las 3 de las 10:00 (Dr. Luis Ejemplo / Dra. Ana Ficticia / Dra. Maria Prueba) identificables y su diálogo de detalle se abre en 3/3; 414 px visibles sin scroll horizontal | VERIFICADO EN NAVEGADOR REAL | C02 |

## RF-07 Chat interno autorizado

| RF-07-01 | Previsualización sintética de Conversaciones (no operativa) | Plantilla C01 | Inspección visual | CONSERVADA como preview (sigue no operativa en C02) | C01 |
| RF-07-02 | Herramientas de lectura acotadas (KB publicada, catálogo, agenda resumida, stock desde BD) | `crm/chat_adapter.py` (contrato `ChatAdapter`, `AdaptadorSimulado` sólo por selección explícita de pruebas, `AdaptadorRemotoConfigurable` cliente HTTP real con credenciales del servidor), `c02_services._herramientas_chat` + `responder_chat_internal` con inyección | test_c02_chat.py (fuentes, abstención, reflejo publicar/desactivar, stock BD, no exponer borradores/privados/datos de clientes, solo consulta, modos simulado/remoto), test_chat_adapter_remoto.py (13 tests, endpoint local ficticio), arranque sin proveedor=no_configurado + VERIFICADO EN NAVEGADOR REAL 2026-10-29 ronda C: consulta real → badge «fuente: sin fuente · IA no configurada» (sin fabricación) | VERIFICADO EN SIMULACIÓN Y NAVEGADOR REAL; IA REAL EXTERNA 2026-10-29: VERIFICADO CON PROVEEDOR DE PRUEBA — Gemini «gemini-3.5-flash-lite» (nivel gratuito según la hoja oficial de precios vigente) vía API OpenAI-compatible: fase 1 7/7 (A-E: kb público con fuente, precio/stock vivos de BD, abstención honesta, inyección resistida, rol sin acceso no filtra el privado; control admin recupera el privado publicado) con 7 llamadas reales; telemetría (proveedor/modelo/tokens/latencia) persistida en crm_audit (26 respuestas HTTP con tokens; 13.745 entrada/940 salida); navegador 7/7 con badge «proveedor de IA conectado» y escaneo sin claves en HTML/consola. Zen desestimado: 403 FreeUsageLimitError oficial (también con clave ficticia). El conteo enmascarado de .env sigue bloqueado por el control de acceso (ronda C y 2026-10-29): disponibilidad de claves ≠ configuración ≠ validación externa; procedimiento local del propietario en VALIDACION_IA_REAL_20261029.md §7. **FASE 2 COMPLETADA 2026-10-29 (2.ª sesión, autorizada por el propietario)**: v2 publicada (respuesta 20:00 con fuente v2 y sin la antigua 18:00), documento desactivado (no recupera ni cita; abstención), precio/stock releídos de BD (5 uds/17,50 con fuente estructurada stock_bd v3); defecto del formateo del precio corregido en chat_adapter.py y regresión local 31 passed; conteo corregido (consultas vs intentos HTTP NO MEDIDO vs respuestas con tokens) y alcance global documentado (incluye ClasificadorIntenciones del motor WhatsApp, sin transportes activados) | C02 |
| RF-07-03 | Fuentes identificables: documento/ID/versión/procedencia o registro consultado | `responder_chat_internal` (fuentes en respuesta), `kbfragments con doc_version + procedencia`, UI `crm_c02_chat.js` | test_c02_chat.py (test_chat_kb_con_fuentes_identificables), E2E punto 3 + VALIDACIÓN IA REAL 2026-10-29 (fuentes kb_doc/catalog/stock con documento/ID/versión en API y navegador) | VERIFICADO EN SIMULACIÓN Y CON PROVEEDOR DE PRUEBA (IA real 2026-10-29) | C02 |
| RF-07-04 | Abstención honesta y sin datos de clientes sin permiso; cambios publicados/desactivados reflejados; el chat SOLO consulta | `responder_chat_internal` + `AdaptadorSimulado` (abstencion=True), filtro por rol en `_herramientas_chat.kb_buscar` | test_c02_chat.py (abstención, no expone borradores/privados/clientes, solo consulta, no ejecuta instrucciones de documentos) + VALIDACIÓN IA REAL 2026-10-29 (casos C1/C2/D/E con el proveedor real) | VERIFICADO EN SIMULACIÓN Y CON PROVEEDOR DE PRUEBA (IA real 2026-10-29) | C02 |

## RF-08 / RF-09 / RF-10 / RF-11 / RF-12

Sin subrequisitos en C01 (RF-09 sólo previsualización en C01).

| RF-09-01 | Bandeja humana: alertas persistentes y toma de control con pausa de IA | `crm_conversations`, `crm_human_alerts`, `c02_services.conv_*` | test_c02_services.py (toma, pausa, conflicto de dos operadores, devolver) | VERIFICADO EN SIMULACIÓN | C02 |

### RF-09 — Control humano (prompt acotado HUM-01..12 + corrección CH-01/02)

| ID | Comportamiento esperado | Implementación | Prueba / evidencia | Estado | Entrega |
|---|---|---|---|---|---|
| HUM-01 | Petición humana interrumpe diálogo pendiente (alerta+pausa, sin ejecutar la cadena vieja) | `canal.detectar_peticion_humana` + reglas estructuradas | tests/test_c02_control_humano.py::test_hum01_* | VERIFICADO EN SIMULACIÓN | C02 |
| HUM-02 | Emergencia interrumpe; webhook duplicado no duplica alerta | idem + idempotencia `wa_ingest` | test_hum02_* | VERIFICADO EN SIMULACIÓN | C02 |
| HUM-03 | Toma durante generación: sin cita ni salida IA | `_guardia` transaccional + `uow` en motor | test_hum03_* | VERIFICADO EN SIMULACIÓN | C02 |
| HUM-04 | Toma entre generación y escritura cerrada por guardia (barrera determinista) | idem, hook `pre_escritura` | test_hum04_* | VERIFICADO EN SIMULACIÓN | C02 |
| HUM-05 | Tareas IA previas invalidadas; humana nunca se cancela | `outbox_claim`/`outbox_admitir` + `_outbox_task_cancelada` | test_hum05_* | VERIFICADO EN SIMULACIÓN | C02 |
| HUM-06 | Toma concurrente: un ganador, persiste tras reinicio | `conv_take` transaccional + generación | test_hum06_* | VERIFICADO EN SIMULACIÓN | C02 |
| HUM-07/07b | Responder/devolver/cerrar exige asignación y rol; cerrada no responde | `conv_reply_humano`/`conv_return`/`conv_close` + rutas protegidas | test_hum07_*, test_hum07b_* | VERIFICADO EN SIMULACIÓN | C02 |
| HUM-08 | Respuesta autorizada coordinada con outbox y transporte (estado durable) | `conv_reply_humano` + `egress.egress_drain` | test_hum08_* | VERIFICADO EN SIMULACIÓN | C02 |
| HUM-09 | request_id estable: idempotente y 409 sin sobrescribir | clave única `crm_outbox_request` | test_hum09_* | VERIFICADO EN SIMULACIÓN | C02 |
| HUM-10 | Fallo/incierto con estado honesto y sin reenvío ciego | triestado cierto/incierto + `outbox_requeue` bloqueado | test_hum10_* (semántica CH-02) | VERIFICADO EN SIMULACIÓN | C02 |
| HUM-11 | E2E de navegador del control humano (alerta→tomar→responder→entregado→devolver) | `scripts/e2e_control_humano.py` + `frontend/e2e/control_humano.e2e.mjs` | EX-019 (exit 0, 5/5 + 7/7) | VERIFICADO EN SIMULACIÓN | C02 |
| HUM-12 | Sin sesión no responde; nota interna sin salida | rutas `@protected` + `conv_add_message` internal | test_hum12_* | VERIFICADO EN SIMULACIÓN | C02 |
| ATN-01 | Indicador global en cabecera de pantallas autenticadas: campana + nº de conversaciones pendientes ÚNICAS + texto accesible | `dashboard.html` (topbar) + `crm_c02_atencion.js` + CSS | tests/test_c02_atencion.py + navegador real (atencion-humana-20261029, 16/16 PASS): Resumen y Conversaciones, claro/oscuro, móvil 414 px | VERIFICADO EN NAVEGADOR REAL (pendiente aceptación) | C02 |
| ATN-02 | Panel al pulsar la campana: motivo, prioridad, tiempo de espera; abrir la conversación directamente; apagado SOLO con resolución explícita (abrir NO resuelve) | `GET /api/c02/atencion` (GET puro) + `crm_c02_atencion.js` + deep-link `?tab=inbox&conversation=ID` en `crm_c02_inbox.js` | test_endpoint_atencion_autenticado_y_no_resuelve + navegador real (deep-link y abrir/cerrar sin cambiar contador) | VERIFICADO EN NAVEGADOR REAL | C02 |
| ATN-03 | Actualización sin recargar (polling sin solapes), persistencia tras recargar, refleja otra pestaña, fallo honesto «No se pudo actualizar» sin apagado falso | setTimeout encadenado en `crm_c02_atencion.js`; GET relee la base | test_endpoint_atencion_falla_no_esconde_pendientes + navegador real (persistencia 4→4; toma desde otro proceso reflejada) | VERIFICADO EN NAVEGADOR REAL | C02 |
| ATN-04 | Motivos con prioridad persistida: humano_explicito, reclamo, emergencia, sin_fuente, fallo_servicio; negaciones NO derivan; sin mensajes privados completos en avisos | migración v16 (`reclamo` en CHECK) + `canal.detectar_peticion_humana` + `atencion_panel` | test_motivo_* (20 tests) + `test_negaciones_no_derivan` + `test_conversacion_con_dos_motivos_cuenta_una_vez` | VERIFICADO EN SIMULACIÓN y NAVEGADOR (panel muestra motivo/prioridad) | C02 |
| ATN-05 | Ciclo de estados: Pendiente → En atención (responsable) → Atendida/resuelta (apaga solo esa, conserva historial/responsable/fecha); nueva incidencia tras resolución re-alerta | `conv_take`, `conv_mark_alert` (resolved_at), `atencion_panel` | test_toma_mueve_a_en_atencion_con_responsable, test_resolver_apaga_solo_esa_atencion_y_preserva_historial, test_nueva_incidencia_tras_resolucion_crea_atencion_nueva + navegador real (ciclo 4→3→3) | VERIFICADO EN NAVEGADOR REAL | C02 |
| ATN-06 | La resolución NO devuelve el control a la IA; devolución explícita libera la pausa | `conv_mark_alert` no toca la asignación; `conv_return` | test_pausa_ia_permanece_hasta_devolucion_explicita | VERIFICADO EN SIMULACIÓN | C02 |
| ATN-07 | Reentrega no duplica alertas; contador global es de conversaciones únicas | dedupe de `conv_raise_alert` (conversación+motivo activa) + agrupación por conversación | test_reenvio_no_duplica_alerta | VERIFICADO EN SIMULACIÓN | C02 |
| CH-01b | DETECCIÓN CONTEXTUAL (corrección del revisor): intención, contexto y ortografía; reclamo/urgencia/peligro no dependen del LLM; no falso positivos de negación/consulta; mensaje mixto con contador único; aviso 'sistema' breve | `crm/canal.py` (cláusulas + negación local + reescrituras `debuelba/calsa/amanesi/inchada`, prioridad peligro>emergencia>reclamo>humano>revisión, motivos múltiples, consulta informativa) + `evidence` en v17 + origen `sistema` en outbox | tests/test_c02_deteccion_contextual.py (29: 14 positivos del revisor + 5 negativos + reentrega + multi-motivo + IA caída + apertura sin resolver + resolución sin retorno IA + campana honesta) | VERIFICADO EN SIMULACIÓN | C02 |
| CH-01c | RESPUESTA Y ALARMA honestas: aviso por prioridad máxima sin promesas (dinero/atención/cita) | `AVISO_POR_MOTIVO` en `crm/canal.py` (origin 'sistema') + `crm_c02_atencion.js` estado inicial «Cargando atenciones...» | test_aviso_al_cliente_por_prioridad_maxima + test_campana_estado_inicial_cargando_sin_comprobar | VERIFICADO EN SIMULACIÓN | C02 |
| CE-01 | El operador autorizado propone cita desde la conversación: espacios DENTRO del horario habitual | `GET /api/c02/excepcion/slots` (perfil efectivo + excepción por fecha + solapamientos; `recursos_fisicos:false` declarado) + diálogo en `crm_c02_inbox.js` | tests/test_c02_excepcion.py (slots, horario intacto) | VERIFICADO EN SIMULACIÓN | C02 |
| CE-02 | Cita EXCEPCIONAL fuera de horario: sólo acción humana autorizada (admin), motivo obligatorio, confirmación explícita, auditoría (quién/cuándo), limitada a esa cita, sin saltar solapamiento ni bloqueos de fecha, revalidación atómica, no resuelve la alerta ni devuelve a IA | `POST /api/c02/excepcion` en `crm/app.py` sobre `save_appointment` (window_policy, BEGIN IMMEDIATE, historial+audit) | tests/test_c02_excepcion.py (normal válida, fuera rechazada, admin, user 403, motivo/confirmación, solapamiento con excepción, concurrencia 1 cita, horario intacto, fecha bloqueada) | VERIFICADO EN SIMULACIÓN | C02 |
| CE-03 | Recorrido E2E en NAVEGADOR real: mensaje urgente → campana → abrir conversación → tomar atención → elegir espacio o excepción → cita persistente en agenda | `scripts/e2e_cita_excepcional.py` + `frontend/e2e/cita_excepcional.e2e.mjs` | ver §E2E al pie de esta matriz | **VERIFICADO E2E (8/8 navegador + 5/5 BD, exit 0)** | C02 |
| CE-04 | Aviso origin='sistema': no inyectable desde fuera, no se invalida al tomar, no duplica en reentrega, tomar/resolver sin envíos inesperados | `outbox_enqueue` normaliza origen; único llamador 'sistema' = canal (derivación); `_outbox_task_cancelada` invalida solo origin='ia' | test_origen_sistema_es_interno_solo_permitido_por_canal, test_aviso_sistema_no_se_invalida_ni_se_envia_de_mas_al_tomar, test_reentrega_no_duplica_aviso_en_outbox | VERIFICADO EN SIMULACIÓN (32 en bloque) | C02 |
| CH-01 | Toma entre reclamo y comienzo del transporte invalida la IA (barrera determinista); transporte YA iniciado = en vuelo explícito; coordinación real entre procesos | Exclusión mutua compartida por conversación (`crm/conv_lock.py`: identidad canónica `realpath`+`normcase` que unifica casing, rutas relativas/absolutas y alias junction/symlink; archivo de bloqueo junto a la ruta real de la BD) que el egress y `conv_take` adquieren; la sección coordinada abarca `outbox_mark_sending` (CAS `began_at`, migración v11) y `transporte.deliver`, sin transacción SQLite abierta durante la red; `conv_take` invalida tareas IA con `began_at` NULL e informa `envio_en_curso`; `outbox_recover_stale` ante caída del consumidor | tests/test_c02_revision_control_humano_3ra.py (15 regresiones: 10 de la 3ª revisión + 5 de alias de Windows —mismo lock para casing distinto, rutas relativas/absolutas, dos procesos con exclusión mutua, toma primero cero llamadas, envío primero sin confirmar—) + EX-025/EX-026 | VERIFICADO EN SIMULACIÓN | C02 |
| CH-02 | Estados recuperables explícitos: reintentar un ID entregado ⇒ `requeued=0` y una sola recepción; acuse perdido = incierto bloqueado hasta reconciliación con idempotencia | `outbox_requeue` atómico + `outbox_reconciliar` + dedupe en destino | test_ch02_enviada_reintentar_id_requeued_0_y_una_recepcion, test_ch02_claim_de_otro_proceso_no_se_recupera, test_ch02_acuse_perdido_una_sola_recepcion, test_ch02_fallo_cierto_* | VERIFICADO EN SIMULACIÓN | C02 |
| CH-03 | Bandeja refresca estado real; E2E exit 0 con pantalla+BD+buzón | `crm_c02_inbox.js` (firma de estados); `e2e_control_humano.py` fix origin | EX-019 | VERIFICADO EN SIMULACIÓN | C02 |
| RF-12-01 | Registro de invocaciones y telemetría mínima | `c02_services.report_invocation` | usado en crm/canal.py | PARCIAL | C02 |

## RF-13 Diseño comercial usable

| ID | Comportamiento esperado | Implementación | Prueba / evidencia | Estado | Entrega |
|---|---|---|---|---|---|
| RF-13-01 | Marco visual coherente: navegación, tipografía, colores, formularios, estados | `crm/static/crm.css` renovado, `base.html`, `dashboard.html` | E2E C01 (render) + verificación EN NAVEGADOR REAL 2026-10-29 ronda C (43/43 PASS) y ronda D (18/18 PASS): selectores Tipo 12.74/14.40 (claro/oscuro), option 12.74/14.40, nombres completos visibles (sw==w), cabecera móvil sin solapamiento, 0 errores JS | VERIFICADO EN NAVEGADOR REAL (pendiente aceptación humana) | C01/C02 |
| RF-13-02 | Agenda navegable en PC/móvil y teclado | `agenda.css`, `agenda.js` | E2E C01 (fase ux: móvil + teclado) | VERIFICADO EN SIMULACIÓN | C01 |
| RF-13-03 | Mensajes comprensibles y estados reales (carga/error/vacío/éxito) | plantillas/JS | Verificación en navegador real 2026-10-29 ronda C: chat con modo honesto «IA no configurada», estados de biblioteca/envíos y diálogo de cita operativos | VERIFICADO EN NAVEGADOR REAL (pendiente aceptación humana) | C01 |
| RF-13-04 | Revisión visual del propietario sobre pantallas concretas | — | Evidencia nueva en `evidencias/workspace/rediseno-20261029-C/` (24 capturas escritorio/414 px + JSON 43/43) | PENDIENTE (aceptación humana del propietario) | — |
| RF-13-05 | Tema claro/oscuro PERSISTENTE con conmutador funcional en la barra lateral (claro→oscuro→claro, recarga y navegación entre secciones) | `crm/static/theme.js`, `base.html` (#theme-toggle), paletas `[data-theme="dark"]` en crm.css/agenda.css | VERIFICADO EN NAVEGADOR REAL (rondas C/D/E): toggle real, persistencia, sistema/manual; contraste del BOTÓN en la matriz completa {claro,oscuro}×{escritorio,móvil}×{reposo,hover,foco Tab,pulsación} — 16 estados, mín. 8.22 (tras fix hover/focus/active de la ronda E, antes ~1.6:1 por especificidad con button:hover); 1 clic=1 cambio; cabecera móvil sin solapamiento | VERIFICADO EN NAVEGADOR REAL | C02 |

## RF-14 Retiro seguro de duplicados

| RF-14-01 | Inventario de entrada/archivo para retiro futuro (no retirar ahora) | `INVENTARIO_RETIRO.md` documentos | — | PENDIENTE (sólo inventario) | C01 |
| RF-14-02 | No borrar nada en C01 | — | git status | VERIFICADO | C01 |


### Salvedad de revisión independiente REV-CH3-20261027
CH-02 verificado en los escenarios ejecutados (requeued=0 para enviado, una recepción). CH-01 NO CERRADO por la fase `began_at`/`outbox_mark_sending` (v11) sola: la reanudación verificó con `REPRO_REANUDACION_LAST_GAP.py` que quedaba una ventana entre el commit del CAS y `transporte.deliver` — `{"events":["take_committed","transport_called"],"receipts":1}`. La relectura aislada posterior tampoco acreditó coordinación (`READ_GAP ... receipts:1`). Esta salvedad prevalece hasta cerrar la ventana con la exclusión mutua compartida. Ver entregas/C02/REVISION_CONTROL_HUMANO_03_CODEX.md y reproducción propia. C02 sigue pendiente.

### Salvedad de cierre REV-CH3-FIX-20261027 (tercera corrección, sólo CH-01) — actualizada en la reanudación
La salvedad REV-CH3 de arriba queda SUPERADA con la exclusión mutua compartida por conversación (`crm/conv_lock.py`): el egress adquiere el bloqueo de conversación ANTES de `outbox_mark_sending` y lo conserva durante `transporte.deliver`; `conv_take` adquiere el mismo bloqueo, nunca espera indefinidamente (informa `envio_en_curso` y permite reintentar). La reproducción exacta del revisor (`repro_antes_transporte.py`, intacta) y el script de la reanudación (`REPRO_REANUDACION_LAST_GAP.py`, intacto) están vinculadas al diseño anterior de barrera aislada; la regresión equivalente vigente es
`tests/test_c02_revision_control_humano_3ra.py::test_ch01_repro_codex_toma_antes_deliver_cero_llamadas`, que devuelve `{"events":["take_committed"],"receipts":0}`: la toma gana, `deliver` no comienza, cero recepciones IA.

Mecanismo vigente: fase durable de envío por tarea (`outbox_mark_sending`, CAS sobre `began_at`, migración v11) bajo el bloqueo de conversación, retenido durante `transporte.deliver` + `conv_take` en el mismo bloqueo (invalida tareas IA no iniciadas, informa `envio_en_curso`) + `outbox_recover_stale` para caída del consumidor. Evidencia de esta reanudación: `tests/test_c02_revision_control_humano_3ra.py` → 15 passed/15.43s/exit 0; suite C02 de control humano → 59 passed/exit 0; regresión CRM/C02 amplia → 248 passed/exit 0 (dos fallos preexistentes de versiones de migración, ajenos a este cambio); E2E de control humano `scripts/e2e_control_humano.py` → exit 0 (5/5 + 7/7, VERIFY_OK). Ver `EVIDENCIA_CONTROL_HUMANO.md` (EX-025/EX-026) y `docs/producto/ESTADO.md`.

La fila CH-01 actualizada arriba refleja la semántica vigente; C02 sigue sin declararse cerrado (espera de la siguiente revisión).


### Dictamen independiente REV-CANONICA-20261027
CH-01 APROBADO EN ESCENARIOS WINDOWS EJECUTADOS: 139 tests + E2E PASS; alias por casing, relativa/absoluta y junction real comparten exclusión. Este dictamen reemplaza las salvedades históricas de CH-01; no cerrar C02 global. Ver entregas/C02/APROBACION_CH01_IDENTIDAD_CANONICA_CODEX.md.


### Dictamen REV-SEL01-20261028
SEL-01 y punto 2 aprobados en escenarios ejecutados, 63 PASS y reproducción con cero citas incompatibles. Sustituye salvedad histórica de selección; CH-01/configuración no reabiertos. Punto 3 y C02 global pendientes. Ver entregas/C02/APROBACION_SEL01_PUNTO2_CODEX.md.


### Salvedad REV-PUNTO3-20261028
Punto 3 PARCIAL: 128 tests y wizard básico PASS, pero importación mixta no atómica, stock de borrador visible a user y CSV con delimitador interno se interpreta mal. No cerrar RF-05/RF-07 por conteos. Adaptador remoto sigue placeholder sin llamada implementada. Ver entregas/C02/REVISION_PUNTO3_DOCUMENTOS_INVENTARIO_CHAT_CODEX.md. Aprobaciones CH-01/configuración/punto2 intactas.


### Dictamen REV-MODOREAL-20261028
Modo sin proveedor corregido; regla operativa escrita. 154 tests PASS; P3-01/02/03 cubiertos. UI importación aún pendiente MODO-01: sugiere F ausente en CSV A..E y rompe E2E. Documentos/versiones/desactivación pasan en navegador. No declarar punto3/C02/producción listos; proveedor real e integraciones externas pendientes. Ver entregas/C02/REVISION_MODO_REAL_Y_PENDIENTES_CODEX.md.


### Dictamen REV-MODO01-CIERRE-20261028
MODO-01 y bloque local punto3 aprobados para escenarios ejecutados: 155 tests, E2E cinco fases y XLSX cambio hoja PASS. Prevalece sobre salvedades locales anteriores. Integración generativa/proveedores externos y producción no certificados. Ver entregas/C02/APROBACION_MODO01_BLOQUE_LOCAL_CODEX.md.


### Preparación operativa 2026-10-28 (encargo A/B/C/D)
Disponibilidad y arranque operativo acreditados con ejecución real: `/health` (liveness,
sin BD) y `/ready` (readiness BD+esquema, razones estables, sin migrar ni reparar; IA sin
configurar = limitación declarada, sin simulación) en `crm/health.py` + `crm/app.py`, con
503 claro ante BD indisponible (`tests/test_c02_health.py`, 5 passed). Arranque operativo
`serve_crm.py` (waitress) separado del servidor de desarrollo (`run_crm.py`) — actualiza
el alcance de RF-01-03. Migración desde versión anterior REAL (v5) con contenido
sintético: respaldo previo → v6..v12 → conservación/integridad/FK → lectura por la app →
2ª inicialización sin duplicados → recuperación del respaldo
(`tests/test_c02_migracion_contenido.py`, 1 passed). Instalación reproducible: lock de 38
pins (`requirements-crm.lock.txt`), instalación desde el lock en `.venv-op` aislado y
verificación operativa autocontenida (`scripts/verificar_instalacion_operativa.py` →
INSTALACION_OPERATIVA_VERIFICADA; waitress + /health + /ready + lecturas reales). Copias
PROGRAMADAS siguen PENDIENTES (sólo política propuesta en la guía). Guía y evidencia:
entregas/C02/GUIA_OPERACION_Y_RECUPERACION.md y EVIDENCIA_PREPARACION_OPERATIVA.md.
Producción NO aprobada; integraciones externas sin validar.


### Dictamen REV-CIERRE-DOC-OP-20261028
Cierre documental de preparación local A/B/C/D APROBADO en alcance/evidencia documentados; guía backup ajustada y probe sintético PASS. No se repitieron suites ni instalación limpia; conservar autoría de resultados previos. Integraciones externas/producción pendientes. Ver entregas/C02/APROBACION_CIERRE_PREPARACION_OPERATIVA_CODEX.md.


### Salvedad REV-WHATSAPP-20261028
Transporte/worker implementados pero NO aprobados:70 tests PASS, cuatro probes WH-01..04 fallan aceptación y ruta positiva MotorIA pendiente. Ver entregas/C02/REVISION_WHATSAPP_REAL_CODEX.md. No cerrar RF-02-05 ni producción por conteos locales. Puntos antes aprobados intactos.

### §E2E — Recorrido real de navegador (CH-01 corrección / cita excepcional, 2026-10-29)
`python scripts/e2e_cita_excepcional.py` → **exit 0, TODOS LOS CHECKS OK**.
Navegador (8/8): campana muestra la atención pendiente → alerta urgente visible en la bandeja →
tomar el chat (admin) → cita 08:00 dentro del horario habitual por flujo normal → la atención sigue
tomada tras crear la cita → cita EXCEPCIONAL 20:30 con motivo obligatorio y confirmación → las 2 citas
visibles vía /api/agenda (ids 1,2) y en la pantalla de agenda → al volver a la bandeja y ABRIR la
conversación, la UI muestra 'Humano asignado' + botón 'Devolver a IA' explícito (no automático).
BD (5/5): 2 citas creadas (una fuera de horario local America/Guayaquil 20:30); alerta
peligro_inmediato/emergencia sigue ACTIVA tras crear citas; egress pausado (chat no vuelto a IA);
conversación en esperando_humano. Capturas en docs/producto/consolidacion/evidencias/c02/.
Mismo id en BD y /api/agenda verificado en el check 6 (resp ids 1,2). Fuera de horario rechazado en
flujo normal, excepción exige admin/motivo/confirmación, sin solapamientos, horario general intacto y
fechas bloqueadas respetadas → cubiertos por tests/test_c02_excepcion.py (10 passed).
