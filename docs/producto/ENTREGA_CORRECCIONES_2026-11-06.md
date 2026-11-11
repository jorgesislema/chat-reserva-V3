# Correcciones de la auditoría del 5 de noviembre de 2026

Fecha: 6 de noviembre de 2026. Alcance: corregir los nueve hallazgos confirmados
(R1–R9) en `chat-reserva-V3`, con regresiones propias y sin tocar la base
operativa, los secretos ni los servicios externos.

Informe de origen: `docs/producto/AUDITORIA_REPO_2026-11-05.md`.
Evidencia de reproducción previa: `docs/producto/evidencias/auditoria-20261105/`.

## Resumen

| # | Hallazgo | Estado | Dónde se corrige |
|---|---|---|---|
| R1 | Respuesta humana entregada dos veces tras recuperación | Corregido | `crm/egress.py`, `crm/c02_services.py` |
| R2 | Memoria del chat compartida entre usuarios del mismo rol | Corregido | `crm/c02_services.py`, `crm/app.py`, migración v24 |
| R3 | Guardar un borrador retira el conocimiento publicado | Corregido | `crm/c02_services.py`, migración v23 |
| R4 | Dependencias de prueba incompatibles | Corregido | `requirements-crm*.txt`, `README.md` |
| R5 | Verificación dependiente de Temp y de la configuración de IA | Corregido | `tests/conftest.py` |
| R6 | Baja de profesional que termina cancelando citas reasignadas | Corregido | `crm/app.py`, `crm/calendar.py`, migración v25 |
| R7 | Reactivar un profesional supera el límite de tres | Corregido | `crm/app.py` |
| R8 | El asistente informa cero atenciones y cancelaciones | Corregido | `crm/c02_services.py` |
| R9 | Zona horaria distinta entre agenda, alta, detalle y resúmenes | Corregido | `crm/app.py`, `crm/business_config.py`, `crm/c02_services.py` |

Regresiones nuevas: `tests/test_regresiones_auditoria.py` (16 casos, uno o más
por hallazgo).

## R1 — Una respuesta humana no puede enviarse dos veces

La rama humana (y la de origen `sistema`) llamaba al transporte **sin** la marca
durable de comienzo. Durante la llamada la fila seguía en `autorizado` con
`began_at` NULL, así que `outbox_recover_stale` la clasificaba como abandono
cierto y `outbox_requeue` la volvía a encolar: una sola tarea producía dos
entregas reales.

Corrección:

* Toda salida pasa por `outbox_mark_sending` (CAS sobre `began_at`, con control
  de propiedad del intento) antes de tocar el transporte, sea IA, humana o de
  sistema; la llamada usa el mismo tiempo de espera acotado.
* Si el CAS ya estaba fijado (`ya`), el consumidor informa `ya_en_curso` y **no
  vuelve a entregar** (antes la rama IA podía repetir la llamada).
* Una tarea `diferido` (no hubo llamada al proveedor) libera su marca con
  `outbox_release_send`, de modo que pueda entregarse cuando se cumpla la
  condición en lugar de quedar "en vuelo" para siempre.

Verificación: `test_r1_respuesta_humana_no_se_duplica_tras_recuperacion`
(reproduce la recuperación con reloj adelantado y un segundo consumidor durante
la entrega: una sola recepción) y `test_r1_envio_humano_usa_tiempo_de_espera_acotado`.

## R2 — Memoria del chat aislada por usuario

La memoria se filtraba por `conversation_id` y rol, no por usuario: dos
administradores con el mismo identificador compartían contexto.

Corrección (migración v24):

* `crm_c02_chat_memory` incorpora `owner` (`u:<id>` o `''` sin usuario) y la
  unicidad pasa a `(conversation_id, owner, turno)`. Lectura, escritura y poda
  se filtran por dueño **y** rol.
* `crm_c02_chat_conversations` registra qué usuario reclamó cada identificador;
  un identificador ajeno se rechaza (`403`) sin cargar historial ni escribir.
* El endpoint `/api/c02/chat` resuelve la conversación **desde la sesión** e
  ignora cualquier identificador enviado por el cliente.
* Las filas existentes se atribuyen a su `user_id` cuando lo tienen; las que no,
  quedan en el espacio sin usuario (nunca se entregan a una cuenta autenticada).

Verificación: tres casos en `tests/test_regresiones_auditoria.py`, incluido el
recorrido HTTP con dos sesiones de administrador y colisión de identificador.

## R3 — Borrador que no retira lo publicado

`kb_upsert` borraba los fragmentos y sobrescribía cuerpo, versión y estado en la
misma fila: al guardar un borrador, el bot perdía inmediatamente la versión que
estaba respondiendo.

Corrección (migración v23):

* `crm_kb_versions` guarda revisiones **inmutables** (nombre, cuerpo, tipo,
  visibilidad, procedencia, error de extracción) por documento y versión.
* `crm_kb_documents.published_version` es el puntero a la publicación activa.
  Guardar un borrador crea una revisión y no mueve el puntero.
* `kb_publish` reconstruye los fragmentos desde la revisión publicada y mueve el
  puntero en una sola transacción; `kb_deactivate` es la única retirada
  explícita; `kb_restore` republica una revisión anterior como versión nueva
  (con rastro de quién y cuándo).
* La recuperación pública (`kb_retrieve_public`) y la del chat interno
  (`kb_search`) leen la revisión publicada, no la de trabajo.
* La migración rellena la revisión vigente de cada documento existente y marca
  como publicados los que ya lo estaban: nadie pierde conocimiento al migrar.

Verificación: `test_r3_borrador_conserva_publicacion_y_permite_revertir`,
`test_r3_el_listado_publico_no_oculta_lo_publicado` y una prueba de actualización
real (base creada con el esquema anterior y abierta con el nuevo).

## R4 — Dependencias de prueba

`requirements-crm-test.txt` incluía `requirements-crm.txt` (que exigía
`pytest>=9.1.1,<10.0`) y añadía `pytest==8.1.1`: no existía versión que
satisficiera ambas. El extra de Google fijaba además versiones por debajo de los
mínimos del runtime.

Corrección:

* `requirements-crm.txt` es sólo runtime (sin pytest).
* `requirements-crm-test.txt` = runtime + `pytest==9.2.0` (la versión del
  `requirements-crm.lock.txt` de cierre).
* `requirements-crm-sync.txt` usa los mismos rangos que el runtime.
* `README.md` describe la separación.

Verificación real: `pip install --dry-run --ignore-installed -r` sobre
`requirements-crm-test.txt`, `requirements-crm-sync.txt` y `requirements.txt` en
Python 3.13 resolvió e imprimió el conjunto "Would install" sin conflictos
(pytest 9.2.0 incluido).

## R5 — Verificación reproducible

* `tests/conftest.py` fija `tempfile.tempdir` a `tmp_path` en cada prueba: las
  llamadas a `tempfile.mkdtemp`/`mktemp` dejan de escribir en el TEMP del equipo,
  se limpian solas y `--basetemp` las redirige.
* Las claves `CRM_CHAT_*` y `META_*` se neutralizan **antes** de importar la
  aplicación (dotenv no sobrescribe variables existentes) y se limpian en cada
  prueba: el `.env` del desarrollador ya no puede seleccionar un proveedor real.
* Se deniega por defecto cualquier conexión saliente que no sea loopback: una
  prueba que olvide sustituir el transporte falla en lugar de salir a Internet.
* No se borran claves del usuario ni se modifica su `.env`.

## R6 — Baja de profesional con migración de calendario

La baja cambiaba `professional_id` sin versión, sin estado de sincronización y
sin preparar el cambio de calendario: la siguiente descarga del calendario de
destino interpretaba la ausencia del evento como cancelación.

Corrección (migración v25):

* La reasignación es una operación de dominio dentro de `BEGIN IMMEDIATE`:
  incrementa `row_version`, deja `sync_status='pending'`, limpia el error y
  guarda la identidad anterior en `sync_origin_calendar_id/_account_id`.
* La sincronización crea el evento en el destino y **después** retira el del
  calendario anterior (404/410 tolerados); si el origen no se puede abrir, la
  cita pasa a `review` para decisión humana en lugar de duplicarse.
* Al confirmarse el envío se limpian las marcas de origen.
* Si el destino es un profesional **sin** calendario, un barrido acotado retira
  el evento del calendario anterior y no deja huérfanos.
* Historial con calendario de origen y destino.

Verificación: tres casos (HTTP de baja + descarga vacía del destino que ya no
cancela; sincronización que sube al destino y retira del origen; barrido cuando
el destino es local).

## R7 — Límite de profesionales al reactivar

El tope de tres sólo se comprobaba al crear. Ahora se valida toda transición
inactivo→activo y el alta, con el conteo y la escritura en la misma transacción
`BEGIN IMMEDIATE` (dos solicitudes simultáneas no pueden pasar ambas). Editar un
profesional que ya está activo no se bloquea.

Verificación: `test_r7_reactivar_un_cuarto_profesional_es_rechazado` y
`test_r7_editar_manteniendo_activo_no_es_un_reactivado`.

## R8 — Métricas del asistente

El resumen buscaba `operational_status='atendida'/'cancelada'` (etiquetas en
español que el dominio nunca persiste) y además exigía `status='active'`, lo que
excluía cualquier cancelación.

Corrección: las métricas usan los estados canónicos (`attended`, `cancelled`,
`no_show`, `pending`, `confirmed`) sin el filtro heredado; el cálculo semanal de
atendidas usa la misma regla y los límites de día se convierten desde la zona
efectiva.

Verificación: `test_r8_resumen_cuenta_atendidas_y_canceladas` y el caso
actualizado de `tests/test_c02_agenda_y_ficha.py` (que además deja de depender
del día de la semana en que se ejecuta).

## R9 — Una sola zona horaria efectiva

La configuración administrativa guardaba `negocio_zona` y las altas la usaban,
pero la agenda, el detalle, la sincronización y los resúmenes seguían con
`app.config['TIMEZONE']` (valor de arranque), y los resúmenes leían otra clave
(`timezone`) con Guayaquil por defecto.

Corrección:

* `business_config` resuelve la configuración efectiva partiendo del perfil con
  el que arrancó **esa** base (`set_active_profile`) y aplicando `crm_settings`.
* `app.py` resuelve `zona_efectiva()` en cada petición y la usa en agenda,
  serialización, detalle, resumen del panel, simulador, analítica y
  sincronización web/CLI. Al cambiar `negocio_zona` se refresca además el valor
  del proceso para que la interfaz lo muestre de inmediato.
* Los resúmenes del chat (`_agenda_summary`, `agenda_dia`) y los listados por día
  usan la misma zona; ya no existe la clave `timezone` paralela.
* No se desplazan las citas guardadas: siguen en UTC y sólo cambia su lectura
  local.

Verificación: `test_r9_cambio_de_zona_alcanza_agenda_alta_y_detalle` (cambio en
caliente → agenda en Madrid → alta 10:00 → 09:00 UTC → detalle 10:00) y las
pruebas de perfil existentes que antes fallaban.

## Verificación ejecutada

Entorno: `.venv-op` (Python 3.13.1, pytest 9.2.0), `--basetemp` local,
`-p no:cacheprovider`. Sin red externa, sin mensajes ni citas reales.

Resultados y fallos preexistentes: ver la sección "Resultados" al final de este
documento y `docs/producto/ESTADO.md`.

## Resultados (ejecutados, no estimados)

Entorno: `.venv-op` (Python 3.13.1, pytest 9.2.0). Todas las órdenes con
`-p no:cacheprovider` y `--basetemp` dentro de `.pytest_cache`, sin red externa
(la propia suite la bloquea) y sin bases ni servicios reales.

| Conjunto | Comando (resumen) | Resultado |
|---|---|---|
| Regresiones R1–R9 | `pytest tests/test_regresiones_auditoria.py` | **16 passed** |
| Canal y outbox | `test_c02_services`, `test_c02_control_humano`, `test_c02_outbox_cancelar`, `test_c02_revision_control_humano`, `test_c02_revision_control_humano_3ra`, `test_c02_webhook_http`, `test_c02_whatsapp_real`, regresiones | **97 passed, 1 failed** (preexistente) |
| Conocimiento, agenda y reservas | regresiones, `test_c02_docs`, `test_c02_biblioteca`, `test_c02_canal_rag`, `test_c02_chat`, `test_c02_chat_multi_turno`, `test_calendar_tool`, `test_crm`, `test_g01_reservas`, `test_reservation_service` | **133 passed** |
| Barrido amplio C02 | 21 módulos (chat, canal, catálogo, inventario, frontend, agenda, analítica, reservas) | **251 passed, 4 skipped, 3 failed** (preexistentes) |
| Reproducción de la auditoría | `docs/producto/evidencias/auditoria-20261105/repro_local.py` | una entrega, `public_hits_after_draft_edit 1`, `other_user_receives_history_entries 0` |
| Reproducción R6–R9 | `docs/producto/evidencias/auditoria-20261105/repro_reservas.py` | **4 failed**: cada caso falla porque ahora observa la conducta corregida (`row_version 2`/`pending`, 3 activos, `atendidas_hoy 1`, zona `Europe/Madrid`) |
| Dependencias | `pip install --dry-run --ignore-installed -r requirements-crm-test.txt` (y `-sync`, `requirements.txt`) | resuelven; `Would install … pytest-9.2.0` |

### Fallos preexistentes (no introducidos aquí, conservados sin tocar)

Comprobados ejecutando los mismos casos sobre `HEAD` (copia de trabajo aparte):

* `tests/test_c02_control_humano.py::test_hum04_toma_entre_generacion_y_escritura_cerrada_por_guardia`
  — el hook `pre_escritura` no se alcanza en el turno de confirmación.
* `tests/test_c02_canal.py::test_worker_reserva_crea_cita_real`,
  `::test_worker_dialogo_multiturno_reserva`,
  `::test_worker_cancelacion_confirmada` — el motor simulado no llega a crear la
  cita en esos recorridos.

Ninguno pertenece a R1–R9; se dejan documentados para una entrega aparte.

### Pruebas ajustadas porque fijaban el contrato defectuoso

No se debilitó ninguna aserción: se corrigió lo que afirmaban.

* `tests/test_c02_docs.py::test_kb_edicion_sube_version_y_reindexa` afirmaba que
  editar desindexaba lo publicado (el defecto R3). Ahora exige lo contrario y que
  publicar mueva el puntero.
* `tests/test_c02_agenda_y_ficha.py::test_resumen_cuenta_hoy_con_estados_canonicos`
  sembraba estados en español (`'confirmada'`, `'atendida'`) y usaba «mañana
  laborable», por lo que fallaba según el día de la semana. Ahora usa estados
  canónicos y el día real.
* `tests/test_reservation_service.py` y `tests/test_g01_reservas.py` comparaban la
  lista de migraciones con literales `[1..11]` / `[1, 2, 3, 4]`; ahora comparan
  con `store.MIGRATIONS` (la lista real declarada).

### Límites

* Sin pruebas reales de Meta/WhatsApp ni Google Calendar: todo es simulado.
* Sin migración ni escritura sobre la base operativa; la actualización se verificó
  sobre una base creada con el esquema anterior en `.pytest_cache`.
* No se declara cerrado C02 ni operativo el canal.
