# CONTINUACIÓN FUNCIONAL — Punto 1 (configuración) y Punto 2 (selección explícita en el canal)

## REGLA DEL PROPIETARIO (vigente para todos los agentes)

> **REGLA DEL PROPIETARIO**: el producto operativo debe usar integraciones reales. Está prohibido sustituirlas por respuestas simuladas, datos ficticios o fallbacks silenciosos y presentarlas como terminadas. Si falta configuración o falla el proveedor, la interfaz debe indicar que la función no está disponible. Los dobles de prueba sólo se permiten dentro de pruebas automatizadas o desarrollo seleccionado explícitamente; nunca acreditan conexión externa ni preparación para producción.

Encargo de continuación funcional (entrega C02): punto 1 — configuración operativa del
negocio (COMPLETADO y APROBADO por Codex, 2026-10-28); punto 2 — selección explícita de
servicio, profesional, duración y cita en el canal de reservas (COMPLETADO en esta sesión,
2026-10-28, detenido para revisión). CH-01 permanece aprobado y fuera del alcance. El punto
3 (chat interno con adaptador IA real) queda registrado para después; NO se inicia.

---

## PUNTO 2 — Selección explícita de servicio, profesional, duración y cita (canal)

### Alcance

Flujo completo en `crm/canal.py` sobre el dominio existente del panel
(`crm/reservation_service.py`). Sin frontend ni backend nuevos, sin IA generativa ni RAG.

**CREAR**
- Usa servicios activos y publicados del catálogo (`_servicios_activos`: kind=servicio,
  publish_state=publicado, active, vigencia válida y `duration_min` > 0; un servicio sin
  duración no es reservable — no se inventan valores).
- La duración procede del servicio seleccionado (nunca 30 min fijos): se verifica en BD la
  duración real guardada.
- Profesional activo y compatible: si el servicio tiene `professional_id`, ese; si no,
  cualquiera activo; la BD es la fuente de verdad de `active` (el contexto del operador solo
  aporta la lista candidata).
- Si hay varias opciones o falta información, el canal pregunta con una lista numerada
  (servicio → profesional → fecha/hora) y conserva las selecciones en el pending de la
  conversación entre mensajes.
- Antes de guardar, `_reservar_conn` revalida en la MISMA transacción de la guardia:
  servicio activo/publicado con duración, profesional activo, ventana horaria
  (`business_config.check_window`, mismas excepciones por fecha que el panel) y conflictos
  (`save_appointment`).
- Confirma al cliente los datos realmente guardados: "Reservé Reserva: <servicio> con
  <profesional> para <fecha> a las <hora> (<duración> min)…". El título en la agenda es
  `Reserva: <servicio>` y coincide con lo persistido.

**CANCELAR y REAGENDAR**
- Identifica las citas del cliente de esa conversación (`appointments_for_lead`).
- Con varias: muestra la lista numerada y pregunta cuál; `_opcion_numerica` interpreta la
  respuesta ("2", "la 2", "opción 2", "#2"); el ID conservado en el pending.
- Nunca toma la primera cita silenciosamente; una selección inválida repite la lista sin
  modificar nada; una cita que ya no está pendiente se rechaza sin tocar el resto.
- Reagendar conserva la duración de la cita original (`_duracion_min_de_cita` de start/end)
  y respeta `business_config.check_window` y los conflictos.
- Cancelar pide confirmación y conserva el historial (cancela el estado operativo).
- Un cliente nunca modifica una cita ajena: la selección se valida siempre contra las citas
  del lead de su conversación (probado con un segundo teléfono).

### Requisito → cambio → prueba → resultado (punto 2)

| Requisito | Cambio (archivo/función) | Prueba | Resultado |
|---|---|---|---|
| Duración del servicio seleccionado (no 30 min fijos) | `crm/canal.py` `_reservar_conn(servicio=...)` lee `duration_min` vigente de BD | `test_duracion_procede_del_servicio_seleccionado` (2 servicios: 30 y 45; elige el 2º) | duración real 45 min en BD (end−start), PASS |
| Selección de profesional compatible | `_run_dialog` (reservar) + `_profesionales_activos` (BD activa) | `test_profesional_seleccionado_por_numero_en_bd` (elige el 2º de 2) | professional_id=2 en BD, PASS |
| Cancelar la segunda de dos citas sin tocar la primera | bloque `cancelar` con lista + confirmación | `test_cancelar_segunda_cita_y_primera_intacta` | cita 2 cancelled, cita 1 pendiente, PASS |
| Reagendar la segunda de dos citas sin tocar la primera | bloque `reagendar` con selección por ID y duración conservada | `test_reagendar_segunda_cita_y_primera_intacta` | cita 2 en nueva fecha con misma duración (60'), cita 1 intacta, PASS |
| Selección ambigua/inexistente/ajena sin mutación | lista numerada + `_opcion_numerica` + validación contra el lead | `test_seleccion_ambigua_inexistente_o_ajena_no_muta` | 0 citas creadas/canceladas indebidamente, PASS |
| Selecciones conservadas entre mensajes | pending de la conversación (`conv_set_pending`) | `test_selecciones_conservadas_entre_mensajes` (4 turnos) | cita con servicio B (45') y profesional 1, PASS |
| Servicio desactivado antes de guardar | revalidación en `_reservar_conn` (misma transacción) | `test_servicio_desactivado_antes_de_guardar_se_rechaza` | 0 citas, mensaje clara, PASS |
| Profesional desactivado antes de guardar | `_profesionales_activos` con BD como fuente + revalidación | `test_profesional_desactivado_antes_de_guardar_se_rechaza` | 0 citas, PASS |
| Horario cerrado / conflicto rigen desde el dominio | `window_policy=business_config.check_window` + `save_appointment` | `test_horario_cerrado_y_conflicto_respetan_dominio` | fecha cerrada y solapamiento rechazados, PASS |
| Misma cita persistida canal ↔ panel (HTTP) | webhook → worker → GET `/api/appointments/<id>` | `test_recorrido_http_canal_y_misma_cita_desde_panel` | idénticos professional/title/start/end/lead, PASS |

### SEL-01 — revalidación transaccional de la asociación servicio→profesional (corrección del revisor, 2026-10-28)

**Defecto reproducido por Codex** (`REVISION_SELECCION_RESERVAS_CODEX.md` +
`revision_seleccion_codex/repro_compatibilidad.py`): el cliente selecciona al profesional 1;
antes de guardar, el servicio pasa a estar asignado al profesional 2 (hook `pre_escritura`);
el canal creaba la cita con el profesional 1 porque `_reservar_conn` releía
`active/publish_state/duration_min` del servicio pero NO su `professional_id`, y confiaba en
la lista `compatibles` calculada antes de la transacción.

**Requisito → cambio → prueba → resultado**

| Requisito | Cambio (archivo/función) | Prueba | Resultado |
|---|---|---|---|
| Revalidar la asociación servicio/profesional ACTUAL con la MISMA conexión del INSERT; no confiar en `compatibles` previos | `crm/canal.py:_reservar_conn` — SELECT ahora incluye `professional_id`; si la restricción vigente no coincide con el profesional seleccionado devuelve `{'code': 'seleccion_caducada', 'profesionales': <opciones actuales releídas con la misma conexión>}` | `test_sel01_reasignacion_servicio_en_pre_escritura` (basado en la reproducción del revisor) | RED primero: `citas_creadas==1` (cita incompatible creada); tras el fix: **0 citas incompatibles** (assert 0) |
| Si dejó de ser compatible, no crear la cita ni emitir confirmación | ídem (el rechazo ocurre dentro de la transacción de la guardia, antes del INSERT) | aserción `out['citas_creadas'] == 0`, `n == 0`, sin "Reservé" en outbox | PASS |
| Refrescar opciones y pedir una selección válida; conservar servicio/fecha/hora | `crm/canal.py:_run_dialog` (reservar) — maneja `seleccion_caducada`: mensaje claro "¿Desea elegir otra opción?" + lista actual; pending conserva servicio/fecha/hora y descarta el `profesional_id` obsoleto | aserciones de texto (mensaje con "profesional" y "otra opción") y completar respondiendo con la nueva opción | PASS |
| Completar con el profesional válido sin reiniciar la conversación | ídem — el siguiente turno responde el número de la lista refrescada y crea la cita con el profesional 2 | `out['citas_creadas'] == 1`, `professional_id == 2`, `title == 'Reserva: Servicio Fixture'` | PASS |
| Fecha, hora y duración correctas | ídem — duración del servicio (45 min), fecha/hora originales | `end−start == 45 min`, `start == f+'T15:30:00'` (10:30 local, UTC−5) | PASS |
| Servicio sin restricción y profesional compatible conservan su funcionamiento | sin cambio de regla (restricción NULL ⇒ cualquier activo) | `test_sel01_servicio_sin_restriccion_conserva_flujo` (y `test_profesional_seleccionado_por_numero_en_bd`) | PASS |

### Hallazgos corregidos durante el punto 2 (no heredados, de esta sesión)

- **`crm/store.py::use` roto en Python 3.13**: un `@contextmanager` de un solo uso; reabrirlo
  dos veces (lo hace `reprogram_appointment`: lee el `old` y luego guarda) lanzaba
  `AttributeError: '_GeneratorContextManager' object has no attribute 'args'`. Reemplazado por
  `_UoW` reutilizable con la misma semántica (entrega la conexión sin commit). Reagendar por el
  canal quedó así probado por primera vez.
- **`MotorSimulado.intencion`**: 'quiero reagendar' se clasificaba como 'reservar' porque
  'reagendar' contiene 'agendar'; corregido con límites de palabra (`\b`) y el chequeo de
  'reagendar' antes que 'reservar'.
- **`_profesionales_activos`**: el `active` venía del contexto inyectado; ahora la BD es la
  fuente de verdad (un profesional desactivado se rechaza aunque el contexto lo liste).
- **`_cita_local`**: `astimezone` no acepta un string de zona; corregido con `zoneinfo`.
- **Adapter tests heredados**: `tests/test_c02_canal.py` y `tests/test_c02_config_funcional.py`
  siembran ahora un servicio publicado con duración (el canal ya no reserva sin catálogo);
  el título esperado cambió a `Reserva: <servicio>`.

---

## Alcance cubierto en esta entrega

1. **Nombre e información pública del negocio**: `negocio_nombre`, `negocio_zona` y
   `negocio_moneda` editables desde `config.html` y persistidos en `crm_settings`; el
   perfil efectivo usa esos valores (zona efectiva para web, bot y disponibilidad).
2. **Saludo inicial**: guardado con `config_set('saludo', ...)`; se emite en la primera
   interacción de una conversación nueva (integración real en `crm/canal.py`
   `procesar_lote`, no solo la función `responder_primer_mensaje` que no se llamaba).
3. **Especialistas y su disponibilidad**: la configuración lee la gestión existente
   (`crm_professionals`, una única fuente de verdad). Guardar especialistas en
   configuración sincroniza la columna `active` de la misma tabla; panel y canal respetan
   la disponibilidad real (cita a profesional inactivo → rechazo con mensaje).
4. **Horarios semanales**: estructura `{día 0..6: [apertura HH:MM, cierre HH:MM]}` guardada
   como regla operativa (no texto informativo). Se aplica con la misma
   `business_config.check_window` desde el panel (`api_appointment_create`, form `POST
   /appointments`, reprogramación) y desde el canal (alta y reagendado por WhatsApp/bot).
5. **Fechas cerradas y excepciones por fecha**: `{fecha: {"estado": "cerrado"} |
   {"estado": "horario", "horario": [apertura, cierre]}}`, editadas desde el panel y
   aplicadas con la misma regla en panel y canal.

### Requisitos transversales

- **Persistencia**: todo se guarda en `crm_settings` con `config_set_extended` y se
  mantiene tras recargar (verificado: pytest + E2E navegador con recarga).
- **La edición exige permisos administrativos y CSRF**: rutas `/api/c02/config` GET/POST
  protegidas (`@protected` + `@admin` por defecto, `@protected_api` con `X-CSRF-Token`);
  el muro global `before_request` rechaza POST sin token CSRF válido (código `csrf`, 400).
- **Valores inválidos rechazados con mensaje claro**: validación por clave en
  `config_set_extended` (nombre vacío, zona IANA no válida, moneda no de 3 letras,
  horarios con apertura ≥ cierre, excepciones con fecha/estado/horario mal formados,
  especialistas sin id o nombre).
- **Notas internas y secretos no expuestos**: `config_get_all(include_secrets=False)`;
  un usuario no administrador recibe `settings == {}` en GET y 403 en POST (test
  `test_config_permisos_y_csrf`).
- **Los cambios de configuración no reinterpretan silenciosamente citas existentes**: se
  cambian las reglas de creación/reprogramación (ventana y zona efectivas), no se
  reescriben citas ya agendadas; la reprogramación también aplica la política vigente.

## Archivos tocados en esta entrega (configuración)

- `crm/business_config.py` — especialistas desde gestión existente, validación estricta por
  clave, sincronización de disponibilidad, horarios en HH:MM en `config_get_extended`,
  saludo/mensaje fuera efectivos.
- `crm/app.py` — `api_appointment_create`, form `POST /appointments` y acción
  `reprogram` usan `business_config.check_window` y `zone()` efectivos (regla única
  panel/canal).
- `crm/canal.py` — `procesar_lote` emite el saludo configurado en conversación nueva;
  `_reservar_conn` y reprogramación aplican `business_config.check_window` (las
  excepciones por fecha antes NO se aplicaban en el canal — bug real corregido).
- `crm/templates/config.html`, `crm/static/crm_c02_config.js`, `crm/static/crm.css` —
  frontend de configuración: perfil editable (antes con `disabled=true`), saludo, horarios
  semanales, excepciones por fecha y disponibilidad de especialistas, con guardado por
  campos, mensajes de error claros y persistencia.
- `frontend/e2e/crm_c02.e2e.mjs` — recorrido E2E ampliado de configuración (guardar +
  recarga + persistencia, captura `config-persistencia.png`).
- `tests/test_c02_config_funcional.py` — suite nueva de configuración funcional.
- Documentos de trazabilidad (ver `EVIDENCIA_CONTINUACION_FUNCIONAL.md`).

## Verificación obligatoria (punto 3 del encargo)

| # | Verificación | Cómo | Resultado |
|---|---|---|---|
| 1 | Editar desde navegador, guardar, recargar y comprobar persistencia | E2E Playwright `config.html` | VERIFICADO (captura `config-persistencia.png`) |
| 2 | Cambiar el saludo y verificar su uso en conversación nueva | pytest `test_saludo_guardado_se_usa_en_conversacion_nueva` + E2E outbox | VERIFICADO |
| 3 | Cerrar una fecha y comprobar rechazo desde panel y canal | pytest `test_fecha_cerrada_rechaza_misma_reserva_panel_y_canal` | VERIFICADO (canal: `citas_creadas=0` + mensaje "está cerrado"; panel: 400) |
| 4 | Cambiar horario semanal y comprobar que ambos canales aplican la misma regla | pytest `test_horario_semanal_misma_regla_panel_y_canal` | VERIFICADO (fuera de ventana rechazado en ambos; dentro aceptado en ambos) |
| 5 | Permisos, CSRF y rechazo de configuración inválida | pytest `test_config_permisos_y_csrf`, `test_config_valores_invalidos_se_rechazan_con_mensaje` | VERIFICADO |
| 6 | Ejecutar la regresión pertinente y guardar capturas | pytest C02 (33 tests) + E2E | VERIFICADO — ver `EVIDENCIA_CONTINUACION_FUNCIONAL.md` |

## Pendientes registrados para después (NO iniciados en estas entregas)

- Chat interno con adaptador IA real, conocimiento editable y fuentes (punto 3 de la
  continuación funcional). La selección explícita de servicio/profesional/duración y cita
  (punto 2) está COMPLETADA en esta sesión y detenida para revisión.

## Evidencia y continuidad

- `docs/producto/consolidacion/entregas/C02/EVIDENCIA_CONTINUACION_FUNCIONAL.md`
- `docs/producto/consolidacion/entregas/C02/RELEVO_ABACUS.md`

---

# CONTINUACIÓN FUNCIONAL — PUNTO 3 (2026-10-28, encargo del propietario)

Objetivo: conocimiento editable con carga de documentos, importación de inventario por
Excel/CSV y chat interno con adaptador IA inyectable, conectado al conocimiento publicado y a
datos autorizados del negocio. SEL-01/punto 2/configuración aprobados; no se rehacen.

## Alcance y decisiones de modelo (documentadas)

- **Inventario CONTADO = absoluto**: el modelo actual no tiene movimientos de stock (entradas/
  salidas); la importación sólo actualiza `stock` como conteo. Una columna de entradas/salidas
  no se interpreta ni se convierte: se ignora con explicación, no se extiende el modelo (la fase
  de ventas/operaciones lo hará si corresponde). Documentado antes de tocar el esquema.
- **Identificación estable por `code`**: nunca por nombre; code repetido en archivo = duplicado.
- **Servicios**: `stock_na=1` (no aplica). Stock numérico en fila de servicio se ignora con aviso.
- **Documentos como FUENTES**: se extrae sólo texto; macros VBA rechazadas; las instrucciones del
  documento nunca sustituyen reglas del sistema (probado con documento "malicioso").
- **PDF escaneado sin OCR** → identificado ("contenido NO leído"); no se guarda como leído.
- **Fórmulas sin valor cacheado** en .xlsx → "valor no disponible": no se adivina.
- **Chat SOLO consulta** (esta entrega): nada de creación/edición de citas ni inventario desde una
  respuesta generada.

## A. Conocimiento editable (hecho en esta sesión)

Extracción stdlib (sin pypdf/openpyxl): .docx (párrafos+tablas), .xlsx (hojas/celdas), .csv
(`,`/`;`, UTF-8/cp1252), .pdf (flujos de texto simple), .txt/.md. Procedencia por página, párrafo,
tabla/hoja/fila. Migración v12: rebuild de `crm_kb_documents` (CHECK kind ampliado + columnas
`procedencia`/`extract_error`/`uploaded_by`) + tabla `crm_inventory_imports` (UNIQUE sha256+hoja).
Rutas admin+CSRF (`/api/c02/knowledge/upload` devuelve preview SIN guardar). UI: carga→preview→
guardar borrador→publicar→desactivar con origen/procedencia.

## B. Importación de inventario (hecho en esta sesión)

`crm/c02_inventory.py`: subir (xlsx/csv) → hoja → mapeo → preview (nuevas/actualizaciones/
duplicados/errores/avisos) → confirmación explícita → aplicar (transacción única con rollback
completo ante cualquier error) → registro en `crm_inventory_imports` (archivo, hoja, sha256,
mapeo, resumen, usuario, fecha). Repetir la misma importación → `ya_aplicada`, sin cambios.
Wizard de UI completo (`crm_c02_inventory.js`).

### B1. MODO-01 (2026-10-28): mapeo a columnas reales de la hoja

`crm/static/crm_c02_inventory.js` (paso1/paso2): el asistente conserva las columnas reales
devueltas por `/api/c02/inventory/upload` para cada hoja, genera las opciones de mapeo sólo
desde la hoja seleccionada (sin lista fija A..H), sugiere únicamente columnas existentes,
deja los opcionales ausentes «(sin usar)», recalcula y elimina asociaciones al cambiar de
hoja y permite revisar el mapeo antes de confirmar. La validación del backend se conserva
(rechaza mapeo a columna inexistente). Verificado en navegador (13 checks, exit 0), E2E
completo (`scripts/e2e_crm_c02.py`, exit 0, 5 fases), suite de inventario (17 passed) y
regresión C02 (155 passed). Detalles en EVIDENCIA (§ MODO-01) y REGISTRO_EJECUCIONES.

## C. Chat interno con adaptador (hecho en esta sesión)

`crm/chat_adapter.py` — contrato `ChatAdapter` inyectable, `AdaptadorSimulado` (heurística
determinista, sin red) y `AdaptadorRemotoConfigurable` (dry-run SIN credenciales; modo queda
`remoto_no_validado`, ninguna llamada real). `responder_chat_internal` ahora orquesta sobre el
adaptador con fuentes identificables (documento/ID/versión/procedencia o registro), abstención
honesta, reflejo inmediato de publicar/desactivar, stock SIEMPRE desde la BD (no del Excel),
filtro por rol (privado sólo equipo autorizado), solo consulta. Fix del bug preexistente
`_catalog_search` (`scored=dict(r)` rompía la puntuación). `kb_search` devuelve `doc_version` y
`procedencia` para las fuentes. UI del chat muestra fuente/versión/procedencia/modo.

## Pendiente (NO iniciado)

- Proveedor remoto real del chat: contrato de API validado + credenciales (requiere encargo
  específico; sin credenciales no hay llamadas ni consumo de crédito).
- C03 (según plan): no iniciado.

## Evidencia

- `docs/producto/consolidacion/entregas/C02/EVIDENCIA_CONTINUACION_FUNCIONAL.md` (§ Punto 3)
- `docs/producto/consolidacion/entregas/C02/RELEVO_ABACUS.md`
- `docs/producto/consolidacion/REGISTRO_EJECUCIONES.md` (EX-030)
