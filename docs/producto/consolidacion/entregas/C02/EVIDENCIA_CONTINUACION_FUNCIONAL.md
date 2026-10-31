# EVIDENCIA_CONTINUACION_FUNCIONAL — Configuración operativa del negocio

Fecha: 2026-10-28 (UTC). HEAD: db6194c (+ cambios locales no comprometidos de esta sesión).
Entorno: `.venv-verify`, bases sintéticas temporales, transporte simulado, datos de
fixture E2E. Sin proveedores reales, sin datos de clientes, sin lectura de secretos,
sin commit/push/despliegue.

## 1. Suite pytest de configuración funcional (nueva)

Archivo: `tests/test_c02_config_funcional.py` (7 tests).

Comando:
```
.venv-verify/Scripts/python.exe -m pytest tests/test_c02_config_funcional.py -q -p no:cacheprovider --basetemp <TEMP>
```
Resultado real: **7 passed, exit 0, ~13.9s**.

| Test | Verifica |
|---|---|
| `test_config_perfil_horarios_excepciones_persisten` | nombre/zona/horarios semanales/excepción se guardan y se leen de nuevo (persistencia) |
| `test_config_valores_invalidos_se_rechazan_con_mensaje` | 8 casos inválidos rechazados con mensaje claro (incl. horario apertura≥cierre, excepción con fecha/estado inválido, especialista sin nombre, clave no admitida) |
| `test_saludo_guardado_se_usa_en_conversacion_nueva` | saludo configurado emitido en primera interacción (outbox) |
| `test_fecha_cerrada_rechaza_misma_reserva_panel_y_canal` | fecha cerrada: canal `citas_creadas=0` + mensaje de cerrado; panel POST → 400 |
| `test_horario_semanal_misma_regla_panel_y_canal` | ventana estrecha: 13:00 rechazado en canal y panel; 10:30 aceptado en ambos |
| `test_especialistas_disponibilidad_afecta_panel_y_desde_gestion` | guardar `activo=false` actualiza `crm_professionals.active` y el panel rechaza al inactivo |
| `test_config_permisos_y_csrf` | POST sin CSRF → 400 `csrf`; usuario no admin → 403 |

## 2. Regresión pertinente

Comando:
```
.venv-verify/Scripts/python.exe -m pytest tests/test_c02_config_funcional.py tests/test_c02_canal.py tests/test_c02_frontend.py tests/test_c02_services.py -q -p no:cacheprovider --basetemp <TEMP>
```
Resultado real: **33 passed, exit 0, ~65s** (canal, frontend y servicios C02 intactos).

## 3. E2E navegador (Playwright + runner existente)

Comando:
```
.venv-verify/Scripts/python.exe scripts/e2e_crm_c02.py
```
Resultado real: **exit 0**; `E2E C02 (cat): TODOS LOS CHECKS OK`; `E2E C02 (bandeja): TODOS LOS CHECKS OK`; `VERIFY_OK` en ambas fases.

Recorrido de configuración ejecutado en el navegador (fase cat):
1. Editar nombre (`#c02-cfg-nombre` → "Clínica Fixture E2E"), saludo (`#c02-cfg-saludo`),
   horario del lunes 09:00–12:00 y excepción de fecha futura (estado cerrado).
2. Guardar (`#c02-cfg-save`) → mensaje "Guardado."
3. Recargar la página y comprobar persistencia → `TRACE recarga: nombre="Clínica Fixture E2E"
   saludo="Hola, ¿en qué le ayudo?" lunA="09:00" exc="2026-11-04"` (cheque con error si alguno no persiste).
4. Captura: `docs/producto/consolidacion/evidencias/c02/config-persistencia.png` (62062 bytes, 2026-10-28 09:06).
5. La DB de fixtures tras el recorrido quedó con `crm_settings` = {
   `negocio_nombre`, `negocio_zona`, `negocio_moneda`, `negocio_saludo`,
   `negocio_mensaje_fuera`, `negocio_horarios` (lunes 09:00–12:00),
   `negocio_excepciones` (2026-11-04 cerrado), `negocio_especialistas` } — persisted.

## 4. Nota de trazabilidad: verificador del runner corregido

`scripts/e2e_crm_c02.py` verificaba `settings.get("saludo")`, pero el backend persiste la
clave como `negocio_saludo`; el E2E de navegador ya pasaba todos los checks, pero el
verificador post-hoc daba `VERIFY_FAIL saludo no guardado`. Antes de la corrección, la
primera ejecución de esta sesión fue: navegador TODOS LOS CHECKS OK + `VERIFY_FAIL` por esa
clave. Corregido a `negocio_saludo`; la segunda ejecución quedó en `VERIFY_OK` (evidencia
arriba). Es un desajuste de nombre de clave en el verificador preexistente, no una
regresión: la persistencia se confirmó tanto por la recarga del navegador como por el
contenido real de `crm_settings`.

## 5. Capturas del recorrido real

`docs/producto/consolidacion/evidencias/c02/`:
- `config-persistencia.png` — pantalla de configuración tras recargar (nombre/saludo/horario/excepción visibles).
- Otras capturas intactas de la misma fase: `catalogo.png`, `conocimiento-doc-publicado.png`,
  `chat-interno-respuesta.png`, `catalogo-articulo-creado.png`, `bandeja-respuesta.png`,
  más `revision_canonica_codex/` (revisor, intactas).

## 6. Hallazgos funcionales corregidos en esta sesión

- **Bug real (canal)**: las excepciones por fecha (cerrado/horario especial) NO se aplicaban
  en el canal: `window_policy=profz.check_window` solo evaluaba los horarios semanales y una
  reserva en día cerrado se creaba. Corregido en `crm/canal.py` (`_reservar_conn` + reagendar)
  usando `business_config.check_window(path, s, e)`. El panel ya lo usaba.
- **Bug latente (frontend)**: `config_get_extended` devolvía horarios en minutos enteros;
  corregido a HH:MM (`_hhmm`), requisito del editor.
- **Bug latente (runner E2E)**: clave `saludo` vs `negocio_saludo` en el verificador (ver §4).

# EVIDENCIA — Punto 2: selección explícita de servicio, profesional, duración y cita (2026-10-28)

Misma política de evidencia: bases sintéticas temporales, transporte simulado, datos de
fixture, sin proveedores reales ni datos de clientes. HEAD db6194c + cambios locales.

## 1. Suite pytest del punto 2 (nueva)

Archivo: `tests/test_c02_seleccion_cita.py` (9 verificaciones obligatorias → 10 tests).

Comando:
```
.venv-verify/Scripts/python.exe -m pytest tests/test_c02_seleccion_cita.py -q -p no:cacheprovider --basetemp <TEMP>
```
Resultado real: **10 passed, exit 0, ~44s**.

| Test | Verifica (requisito) |
|---|---|
| `test_duracion_procede_del_servicio_seleccionado` | requisito 1: seleccionar el 2º servicio (45 min) → duración real 45 min en BD (end−start) |
| `test_profesional_seleccionado_por_numero_en_bd` | requisito 2: seleccionar el 2º profesional → `professional_id=2` en BD |
| `test_cancelar_segunda_cita_y_primera_intacta` | requisito 3: cancelar la 2ª de dos citas; la 1ª queda intacta |
| `test_reagendar_segunda_cita_y_primera_intacta` | requisito 4: reagendar la 2ª; la 1ª intacta; conserva su duración (60 min) |
| `test_seleccion_ambigua_inexistente_o_ajena_no_muta` | requisito 5: ambigua/inexistente/ajena → ninguna mutación incorrecta |
| `test_selecciones_conservadas_entre_mensajes` | requisito 6: 4 turnos (servicio→profesional→fecha/hora) conservan las selecciones |
| `test_servicio_desactivado_antes_de_guardar_se_rechaza` | requisito 7a: servicio desactivado antes de guardar → rechazo, 0 citas |
| `test_profesional_desactivado_antes_de_guardar_se_rechaza` | requisito 7b: profesional desactivado → rechazo, 0 citas |
| `test_horario_cerrado_y_conflicto_respetan_dominio` | requisito 8: fecha cerrada (configuración) y solapamiento (dominio) rechazados |
| `test_recorrido_http_canal_y_misma_cita_desde_panel` | requisito 9: webhook HTTP → worker → GET `/api/appointments/<id>` muestra la misma cita (professional/title/start/end/lead idénticos) |

## 2. Confirmación real en BD (extracto de la ejecución)

Recorrido 'dos servicios, elegir el 2º y Dra. Ana':
```
T0 'quiero reservar 2026-10-30 a las 10:30' => '¿Qué servicio desea reservar?\n1. Limpieza dental (30 min)\n2. Blanqueamiento (45 min)\nIndique el número.'
T1 '2' => '¿Con qué profesional desea la cita?\n1. Dra. Ana\n2. Dr. Luis\nIndique el número.'
T2 '1' => 'Reservé Reserva: Blanqueamiento con Dra. Ana para 2026-10-30 a las 10:30 (45 min). ¿Le sirve o prefiere otro horario?'
citas en BD: [(1, 'Dra. Ana'..., start 2026-10-30T15:30:00+00:00, end 2026-10-30T16:15:00+00:00, title 'Reserva: Blanqueamiento')]
```

## 3. Regresión pertinente

Comando:
```
.venv-verify/Scripts/python.exe -m pytest tests/test_c02_seleccion_cita.py tests/test_c02_canal.py tests/test_c02_config_funcional.py tests/test_c02_services.py tests/test_c02_frontend.py tests/test_c02_webhook_http.py tests/test_reservation_service.py -q -p no:cacheprovider --basetemp <TEMP>
```
Resultado real: **ver task d6423593 (se informa al terminar; no se declara PASS sin el exit)**.
Previo: `tests/test_c02_canal.py + tests/test_c02_config_funcional.py` → **16 passed** (exit 0)
con los seeds adaptados (servicio publicado con duración).

## 4. Fallos y hallazgos de la sesión (punto 2)

- **`crm/store.py::use`** rompía en Python 3.13 al reutilizar el uow dos veces
  (`reprogram_appointment`): `AttributeError: '_GeneratorContextManager' object has no
  attribute 'args'`. Fix: clase `_UoW` reutilizable con la misma semántica. El fallo se
  reprodujo en esta sesión (traceback en la salida de depuración); tras el fix, reagendar pasa.
- **Motor**: 'quiero reagendar' se clasificaba como 'reservar' (subcadena 'agendar');
  corregido con límites de palabra en `MotorSimulado.intencion` y orden reagendar→reservar.
- **`_profesionales_activos`**: la BD ahora es la fuente de verdad de `active`; cobertura por
  `test_profesional_desactivado_antes_de_guardar_se_rechaza`.
- **Adaptación honesta de tests heredados**: el canal ya no reserva sin catálogo; los seeds de
  `test_c02_canal.py` y `test_c02_config_funcional.py` ahora siembran un servicio publicado con
  duración, y el título esperado cambió de 'Reserva por WhatsApp' a 'Reserva: <servicio>'. Es el
  contrato nuevo del punto 2 (duración del servicio), no un debilitamiento.

# EVIDENCIA — SEL-01: revalidación transaccional de la asociación servicio→profesional (2026-10-28)

Misma política de evidencia: bases sintéticas temporales (`--basetemp` único por ejecución),
transporte simulado, sin proveedores reales ni datos de clientes. HEAD db6194c + cambios
locales no comprometidos.

## 1. Regresión SEL-01 (red → green)

Test nuevo `tests/test_c02_seleccion_cita.py::test_sel01_reasignacion_servicio_en_pre_escritura`
(basado en la reproducción del revisor `revision_seleccion_codex/repro_compatibilidad.py`): el
cliente elige al profesional 1 y el hook `pre_escritura` reasigna el servicio al profesional 2
antes del INSERT; el comportamiento correcto exige 0 citas incompatibles.

Comando (red, código anterior al fix):
```
PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_seleccion_cita.py::test_sel01_reasignacion_servicio_en_pre_escritura tests/test_c02_seleccion_cita.py::test_sel01_servicio_sin_restriccion_conserva_flujo -q -p no:cacheprovider --basetemp /tmp/sel01red
```
Resultado real: **1 failed, 1 passed, 7.45s** — el fallo esperado:
`assert out['citas_creadas'] == 0` → `assert 1 == 0` (la cita incompatible con el profesional 1
se creaba). `--basetemp /tmp/sel01red` (bases temporales, no artefactos).

Comando (green, tras el fix en `crm/canal.py`; `py_compile` de `crm/canal.py` exit 0):
```
PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_seleccion_cita.py::test_sel01_reasignacion_servicio_en_pre_escritura tests/test_c02_seleccion_cita.py::test_sel01_servicio_sin_restriccion_conserva_flujo -q -p no:cacheprovider --basetemp /tmp/sel01green
```
Resultado real: **2 passed, 7.41s**.

## 2. Suite de selección completa

Comando:
```
PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_seleccion_cita.py -q -p no:cacheprovider --basetemp /tmp/sel01full
```
Resultado real: **12 passed, 51.46s** (10 previos del punto 2 + 2 de SEL-01).

## 3. Regresión ampliada (61 + 2 nuevas)

Comando:
```
PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_seleccion_cita.py tests/test_c02_canal.py tests/test_c02_config_funcional.py tests/test_c02_services.py tests/test_c02_frontend.py tests/test_c02_webhook_http.py tests/test_reservation_service.py -q -p no:cacheprovider --basetemp /tmp/sel01reg
```
Resultado real: **63 passed, exit 0, 137.07s** (task 33509417). Las 61 del revisor (64.97s,
pre-SEL-01) siguen pasando con el fix, más las 2 regresiones nuevas.

## 4. Cambio (resumen para la trazabilidad)

- `crm/canal.py:_reservar_conn` — el SELECT de revalidación ahora incluye `professional_id` del
  servicio (además de `active/publish_state/duration_min`) y corre con la MISMA conexión
  transaccional del INSERT; si la restricción vigente no coincide con el profesional
  seleccionado devuelve `{'ok': False, 'code': 'seleccion_caducada', 'profesionales': <opciones
  actuales releídas con la misma conexión>}`; verifica también `crm_professionals.active` del
  profesional (devuelve `code 'invalid'` si el servicio/profesional está inactivo o la duración
  no es válida).
- `crm/canal.py:_run_dialog` (reservar) — maneja `seleccion_caducada` después de la guardia:
  mensaje claro pidiendo otra selección con la lista refrescada; el pending conserva
  servicio/fecha/hora y elimina el `profesional_id` obsoleto (`pend_sin_prof`), de modo que el
  siguiente turno re-interpreta la respuesta contra la lista actual.
- Sin sustitución silenciosa de profesional, sin INSERT ni confirmación en caso incompatible,
  sin pérdida de servicio/fecha/hora; los servicios sin restricción (`professional_id` NULL)
  siguen admitiendo a cualquier profesional activo.

Los 5 puntos del encargo SEL-01 quedan cubiertos por `test_sel01_reasignacion_servicio_en_pre_escritura`
(cambio de asociación en pre_escritura → 0 citas incompatibles; solicitud clara de otra opción;
completar con el profesional 2 sin reiniciar la conversación; `end−start` 45 min; fecha/hora
correctas) y `test_sel01_servicio_sin_restriccion_conserva_flujo` (servicio sin restricción y
profesional compatible conservan el flujo).

---

# EVIDENCIA — PUNTO 3 C02 (2026-10-28, conocimiento editable, inventario y chat con adaptador)

## 1. Paso A — Conocimiento editable y carga documental

Comando: `python -m pytest tests/test_c02_docs.py -q`
Resultado real: **17 passed, 6.58s** (extracción docx/pdf/xlsx-2-hojas/csv, PDF escaneado sin OCR,
.doc/.xls antiguos, macros VBA, instrucciones maliciosas no mutan agenda/stock, CSRF, permisos
admin/no-admin, público/privado, borrador→publicar→desactivar, revisión por edición).

Comando (regresión tangente A+B frente a lo existente):
`python -m pytest tests/test_c02_docs.py tests/test_c02_services.py tests/test_c02_frontend.py -q`
Resultado real: **34 passed, 14.23s** (17 nuevos del paso A + 17 tangentes de KB/catálogo/UI).

## 2. Paso B — Importación de inventario

Comando: `python -m pytest tests/test_c02_inventory.py -q`
Resultado real: **12 passed, 5.17s** (dos hojas xlsx, CSV ';', mapeo de columnas, identificación
estable por code, preview con clasificaciones, confirmación explícita obligatoria, registro en
`crm_inventory_imports`, repetición idempotente sin duplicar, actualización por code con revisión,
filas inválidas rechazadas sin cambios silenciosos, servicios sin stock, publish_state conservado,
rutas HTTP admin/CSRF).

## 3. Paso C — Chat interno con adaptador IA inyectable

Comando: `python -m pytest tests/test_c02_chat.py -q`
Resultado real: **11 passed, 4.92s** (fuentes documento/ID/versión/procedencia, catálogo con stock
desde BD, stock refleja importación de inventario, servicios sin stock, abstención honesta, no
expone borradores/privados/datos de clientes, instrucciones de documento no ejecutadas, solo
consulta sin escrituras, inyección de adaptador falso y modos simulado/remoto_no_validado).

## 4. Regresión C02 completa (punto 3 + suites previas)

Comando:
`python -m pytest tests/test_c02_docs.py tests/test_c02_inventory.py tests/test_c02_chat.py tests/test_c02_services.py tests/test_c02_frontend.py tests/test_c02_canal.py tests/test_c02_webhook_http.py tests/test_c02_config_funcional.py tests/test_c02_control_humano.py tests/test_c02_seleccion_cita.py tests/test_c02_revision_control_humano.py tests/test_c02_revision_control_humano_3ra.py -q`
Resultado real: **128 passed, 86.89s, exit 0** (57 nuevos del punto 3 + 71 previos).

Nota de trazabilidad: `test_hum04_toma_entre_generacion_y_escritura_cerrada_por_guardia` fallaba
por una precondición de test previa al punto 3 (el punto de mutación sólo se alcanza con un
servicio publicado con duración desde el punto 2; el `_seed` no lo creaba). Se corrigió el TEST
(añade un servicio reservable publicado con duración), ningún código de producto del canal cambió.
Control humano completo: `python -m pytest tests/test_c02_control_humano.py -q` → **12 passed**.

## 5. E2E HTTP del punto 3 (cargar → previsualizar → publicar/importar → consultar → recargar)

Script de un disparo sobre la app real con BD temporal (no Playwright; sin UI visual):
1. Cargar `protocolo.docx` → preview OK (kind=docx, 4 entradas de procedencia).
2. Guardar borrador → NO publica al cargar; el chat se abstiene antes de publicar.
3. Publicar → el chat responde con fuente `Protocolo de higiene v1 (id)`, procedencia párrafo.
3b. Desactivar → la consulta posterior se abstiene (el cambio se refleja de inmediato).
4. Importar inventario CSV → preview `nuevas=2`; aplicar con confirmación → 2 creadas;
   repetir la misma importación → `ya_aplicada` (sin duplicar).
5. Chat: stock de gasas=120 leído de la BD; consulta dental → "no aplica".
6. Recarga: el documento permanece desactivado y el inventario con 2 ítems.

## 6. Límites reales declarados

- PDF con Object Streams/cifrado → "contenido no extraído" (sin pypdf); escaneados → no leídos.
- Sin pypdf/openpyxl/python-docx: extracción con stdlib, compatibilidad declarada a ese nivel.
- Adaptador remoto del chat: implementado y probado LOCALMENTE contra servidor local ficticio
  (tests/test_chat_adapter_remoto.py); CONEXIÓN EXTERNA PENDIENTE (requiere autorización y
  credenciales reales del proveedor). Sin llamadas reales ni consumo de crédito. Estados
  «IA no configurada» verificados en esta sesión con las 4 variables CRM_CHAT_* eliminadas.
- Frontend del wizard de inventario IMPLEMENTADO y EJERCITADO en navegador en esta sesión
  (E2E Playwright fases p3: cargar → previsualizar → confirmar → persistir → rechazo de
  inválido; capturas en docs/producto/consolidacion/evidencias/p3-inv-*.png). El auto-mapeo
  por defecto espera el orden típico A=code, B=name, C=kind, D=stock, E=active, F=details;
  un CSV con menos columnas debe mapearse explícitamente en el paso 2 del wizard.


# EVIDENCIA — MODO-01: mapeo de inventario a columnas reales (2026-10-28)

## 1. Corrección implementada
`crm/static/crm_c02_inventory.js` paso1/paso2: el asistente conserva las columnas reales
devueltas por `/api/c02/inventory/upload` por cada hoja, genera las opciones de mapeo sólo
desde la hoja seleccionada (sin lista fija A..H), sugiere columnas existentes, deja los
opcionales ausentes «(sin usar)», recalcula y elimina asociaciones al cambiar de hoja y
permite revisar el mapeo antes de confirmar. La validación del backend se conserva intacta.

## 2. Harness navegador real (13 checks, BD temporal, servidor 127.0.0.1) — exit 0
- `MODO01_details_sin_usar` (CSV A..E: details sin valor y sin opción F)
- `MODO01_code_sugerido_A`, `MODO01_stock_sugerido_D`, `MODO01_active_sugerido_E`
- `MODO01_csv5_preview_ok` (Nuevas: 1), `MODO01_csv5_aplicado`
- `MODO01_xlsx_hoja1_stock_D`, `MODO01_xlsx_hoja1_details_sin_usar`
- `MODO01_xlsx_hoja2_code_A`, `MODO01_xlsx_hoja2_stock_sin_usar`, `MODO01_xlsx_hoja2_kind_sin_usar`
- `MODO01_csv_invalido_preview_errores`, `MODO01_csv_invalido_rechazado`
- `MODO01_WIZARD_OK`. Capturas: `evidencias/modo01-csv5-preview.png`,
  `evidencias/modo01-xlsx-hoja2.png`, `evidencias/modo01-invalido-rechazado.png`.

## 3. E2E completo (scripts/e2e_crm_c02.py) — exit 0
5 fases (cat, p3, p3noconfig x2, bandeja) con `P3_WIZARD_OK` (incluye inventario válido
aplicado e inválido rechazado con CSV A..E), `P3_NOCONFIG_OK` x2 y bandeja OK; VERIFY_OK en
cada fase con comprobación independiente de BD.

## 4. Suite pytest (nueva)
`test_modo01_mapeo_solo_columnas_existentes`: mapeo A..E aplica y persiste (stock 15 en BD);
mapeo con F inexistente → backend rechaza «La columna F (campo details) no existe...».
`tests/test_c02_inventory.py` → **17 passed, 8.56s**, exit 0.

## 5. Regresión C02 completa
`python -m pytest` (13 archivos C02 + test_chat_adapter_remoto) →
**155 passed, 20 warnings, 117.80s, exit 0**.

## 6. Límite declarado
La ausencia de una columna opcional (p. ej. details) deja el campo «(sin usar)» y NO crea
la asociación; si el archivo necesita ese campo, el usuario lo remapea en el paso 2. El
backend sigue rechazando cualquier mapeo a columna inexistente (validación conservada).
