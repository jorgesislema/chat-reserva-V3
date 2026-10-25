# Reporte G01 — Estabilización: configuración compartida, métricas y telemetría única

Estado actual: **G01 aceptada por Codex tras G01B**, 23-10-2026. Ver
`REVISION_G01B_CODEX.md` para ejecuciones independientes, límites y dictamen.
Las secciones siguientes conservan el historial de entrega del implementador.

Fecha: 23-10-2026. Rama `actualisacion-dependencias`. Implementación: GLM
(prompt `PROMPT_GLM_01_ESTABILIZACION.md`). Estado: **G01 lista para revisión**
de Codex; no autoaceptada. Sin commit, push ni despliegue. Datos ficticios,
servicios simulados; no se tocaron `.venv-crm`, `analitica.db` ni secretos.

Corrige A1, el registro duplicado de A2 y A5 de `AUDITORIA_REPO_2026-10-23.md`.
Diseño y diagnóstico de causas: `DISENO_G01.md` (guardado antes de editar).

## Objetivo

Que la web y el bot compartan una única configuración de negocio (zona, horario,
terminología) con la misma regla de aceptación/rechazo; que la analítica mida
duración real y sepa el canal de cada reserva; y que cada interacción del bot
deje exactamente un registro, también en HANDOFF.

## Archivos

| Archivo | Cambio |
|---|---|
| `crm/business_profile.py` | **Nuevo.** Perfil de negocio validado (nombre, rubro, zona IANA, moneda, terminología, horario semanal), `ProfileError` en bloque sin reglas parciales, `check_window` (intervalo completo, multi-día sólo con disponibilidad continua), resolución por `CRM_PERFIL_NEGOCIO` con perfil interno por defecto equivalente al histórico. |
| `perfiles/ejemplo-consultorio.json`, `ejemplo-servicios.json` | **Nuevos.** Perfiles ficticios de ejemplo (Guayaquil/USD L–V 08–18 y Madrid/EUR L–V 09–19 + S 09–13): mismo código, cero edición Python. |
| `perfiles/pruebas-24x7.json` | **Nuevo.** Fixture de disponibilidad continua para pruebas de consistencia temporal (49 h, medianoche), separadas de las de horario. |
| `crm/store.py` | Migración v4: columna `channel` (web/bot/google; NULL=histórico) + backfill de `origin='google'`; atómica e idempotente como v1–v3. |
| `crm/reservation_service.py` | `save_appointment(..., channel, window_policy)`: código `outside_business_hours`; excepción administrativa sólo con rol admin + motivo (queda en historial); reprogramar conserva canal; canales validados. `reprogram_appointment` acepta y propaga la política. |
| `crm/app.py` | Carga el perfil en `create_app` (`PROFILE` inyectable en pruebas); alta web/form/API y reprogramación pasan `channel='web'` + `window_policy`; la API de alta propaga `reason` para la excepción admin. |
| `crm/integration.py` | El bot pasa `channel='bot'` y la misma `check_window` del perfil configurado. |
| `api/agent.py` | Eliminados zona fija UTC-5 y horarios/textos dentales duplicados (3 sitios + prompt): `consultar_horarios`, disponibilidad y agendado usan `check_window` del perfil; prompt del sistema y emergencias usan nombre/rubro/paciente/zona del perfil. |
| `api/procesamiento.py` | **Nuevo.** Orquestación con un único registro por interacción (finally) y flag HANDOFF correcto; dependencias inyectadas. |
| `api/main.py` | Texto y audio son adaptadores delgados de `procesar_mensaje`; se elimina el doble registro (A2). |
| `crm/analytics.py` | Duración entre instantes UTC (A5.1); `dim_canal` + `es_demo` en `fact_citas` (A5.2); lectura con `BEGIN` de lectura (instantánea coherente, sin bloquear escritores); rechazo source=target; vista nueva `vw_citas_por_canal`. |
| `tests/test_business_profile.py`, `tests/test_g01_reservas.py`, `tests/test_g01_handoff.py` | **Nuevos** (10 + 7 + 6 pruebas). |
| `tests/test_analytics.py` | +5 pruebas (DST primavera/otoño, canal, concurrencia, source=target) y adaptación demo (`dim_origen`→`es_demo`). |
| `tests/test_crm.py`, `test_p02.py`, `test_p02c.py` | Fixtures con perfil 24×7: separan consistencia temporal de horario y evitan dependencia del día/hora de ejecución (lección P02B R2). Sin retirar cobertura. |
| `README.md`, `docs/producto/*` | Documentación de perfiles, adaptación y continuidad. |

## Decisiones y desviaciones

1. **Perfil interno por defecto** cuando no hay `CRM_PERFIL_NEGOCIO`: equivale
   al comportamiento histórico del bot (L–V 08–18, `America/Guayaquil`) pero
   con zona IANA. Instalaciones existentes no se rompen; un perfil indicado y
   mal formado **sí** impide arrancar (error claro, sin reglas parciales).
2. **Multi-día**: `check_window` admite intervalos de varios días locales sólo
   si todos los días implicados tienen disponibilidad 00:00–24:00. Un perfil
   restringido los rechaza con motivo; así la misma función sirve a una
   guardia 24×7 y a un consultorio.
3. **Excepción administrativa**: se decide en el servicio (no en la UI), exige
   `role='admin'` + motivo no vacío, y el historial registra
   «Excepción fuera de horario: <motivo>». El bot llama con rol usuario: no
   puede pedirla. No se construyó pantalla: el contrato queda documentado.
4. **Canal separado de origin**: `channel` documenta quién creó la cita
   (web/bot/google); `origin` sigue gobernando sincronización y la protección
   `demo` (intacta: nunca sale por sincronización, sobrevive editar/cancelar).
   El histórico sin canal conocido queda NULL y la estrella lo muestra como
   `desconocido`; no se inventan datos ni se atribuye en bloque al bot.
5. **Duración**: instantes UTC; la zona sólo para dimensiones. Madrid
   2030-03-31 01:30+01→03:30+02 = 60 min (antes 120); otoño con offsets
   explícitos también 60.
6. **ETL**: `BEGIN` de lectura (deferred) alrededor de las tres SELECT: foto
   coherente sin transacción de escritura sobre la operativa (WAL: los
   escritores siguen). Reconstrucción atómica del destino y rollback intactos.
   `source==target` (realpath, sin distinción de mayúsculas en Windows) se
   rechaza antes de tocar nada.
7. **HANDOFF**: la señal se conserva igual (`[HANDOFF]`); no se construye
   pausa persistente ni bandeja (P04). Un solo registro por ejecución para
   éxito, vacío, error de grafo y fallo de envío; texto persiste el envío
   previo como antes, audio no (comportamiento histórico conservado).

## Migraciones

v4 (`_migration_004_channel`): `ALTER TABLE crm_appointments ADD COLUMN channel
TEXT` + backfill `channel='google' WHERE origin='google'`. Probada desde base
v3 con filas locales y de Google: conservadas íntegras (event_id, datos,
historial); idempotente; versiones quedan `[1,2,3,4]`.

## Comandos y resultados reales

```powershell
# Suite mínima (.venv-verify, Python 3.13.1, sin IA/Qdrant/Google)
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_p02c.py tests/test_p03.py tests/test_analytics.py tests/test_demo_seed.py tests/test_business_profile.py tests/test_g01_reservas.py -q --basetemp=.pytest_cache/g01-final-min2
# 122 passed in 170.30s; salida 0

# Suite completa con agente/API (venv del workspace, dependencias del bot ya presentes; nada se instaló)
./venv/Scripts/python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_p02c.py tests/test_p03.py tests/test_analytics.py tests/test_demo_seed.py tests/test_business_profile.py tests/test_g01_reservas.py tests/test_calendar_tool.py tests/test_agent.py tests/test_api.py tests/test_g01_handoff.py -q --basetemp=.pytest_cache/g01-final-bot2
# 140 passed in 233.32s; salida 0 (4 avisos de deprecación de FastAPI on_event)
```

Iteración de desarrollo (registrada, no oculta): las primeras corridas fallaron
en dos rondas. (1) En las pruebas nuevas: FK de profesional ausente en un
fixture, columna ambigua `canal_key`, un test que esperaba excepción donde el
servicio devuelve resultado estructurado, un solape legítimo al reusar el
mismo hueco en dos canales y la API de alta sin propagar `reason`. (2) En la
regresión: las expectativas de versiones `[1,2,3]`→`[1,2,3,4]` por la
migración v4 (misma adaptación que hizo v2 y v3 en su momento) y tres pruebas
de P02 que usaban el bot/hora arbitraria sin perfil de prueba (domingo,
cierre, zona Madrid) ahora fijan `CRM_PERFIL_NEGOCIO=pruebas-24x7` o perfil
24×7 en la app, con comentario. Resultado final: 122 y 140 pasadas, 0 fallos.

## Diferencias frente a pruebas históricas

- Conteos previos (96/101/97/82/77) corresponden a otras ejecuciones y otros
  árboles; no se usan como evidencia. El conteo actual es el de esta sección.
- Pruebas de horario y de consistencia temporal quedaron separadas por diseño:
  las suites P02/P02C/CRM crean ahora bajo perfil 24×7 (fixtures) y el rechazo
  real por horario se prueba en `test_g01_reservas` con el perfil restringido
  del consultorio. No se retiró ninguna aserción; se cambió la fixture con la
  justificación de cada archivo.
- Los scripts de evidencia de navegador de P02/P02C crean citas por el
  formulario real (p. ej. 49 h): si se re-ejecutan en el futuro, requieren
  `CRM_PERFIL_NEGOCIO=perfiles/pruebas-24x7.json`. Registrado como impacto,
  no modificado en G01 (su evidencia es histórica de fases aceptadas).

## Límites y pendientes

- La prueba real pendiente de P03 (calendario exclusivo autorizado) **no** se
  sustituye: G01 no declara P03 aceptada.
- A2 queda resuelto sólo en su parte de telemetría duplicada; el estado
  durable de conversación (pausa de IA), envío e ids persistidos son P04.
- A8 (audio_transcriber ausente) sigue fuera de alcance; las pruebas del
  camino de audio usan la función de procesamiento con texto transcrito, sin
  transcripción real.
- Feriados, catálogo de servicios con duraciones y pantalla de edición del
  perfil: contrato documentado en `DISENO_G01.md`, no implementados.
- OAuth y ciclo automático de sincronización: sin cambios (P03/A7).

## Siguiente paso

Revisión de Codex sobre este reporte, `DISENO_G01.md`, el diff y la repetición
de las dos suites (o del subconjunto que elija). Pendientes del propietario
que no bloquean esta revisión: calendario exclusivo para P03 y decisión de
commits por fase.

---

# G01B — Correcciones de la revisión Codex (R1–R3)

Fecha: 23-10-2026. Estado: **G01B lista para nueva revisión** (no autoaceptada).
Se conservan los cambios G01 y las 122/140 pruebas; correcciones acotadas a
`REVISION_G01_CODEX.md`. Sin commit/push; simulado y datos ficticios; sin tocar
`.venv-crm`, `analitica.db` ni secretos.

## R1 — Zona única (archivos: `crm/business_profile.py`, `crm/app.py`,
`crm/integration.py`, `api/agent.py`, `crm/analytics.py`)

- `resolve_profile(legacy_zone)` con precedencia documentada: perfil manda;
  `CRM_TIMEZONE` contradictoria con perfil externo → `ProfileError` en arranque;
  sin perfil, `CRM_TIMEZONE` alimenta el perfil interno (una sola autoridad).
- `TIMEZONE` de la app **se deriva** del perfil; `BUSINESS_NAME` por defecto
  desde `profile.name` (env sigue teniendo precedencia como sobrescritura).
- Bot (`reserve`, `local_availability`), disponibilidad remota del agente y CLI
  analítica leen `configured_profile().zone`; ningún adaptador consulta
  `CRM_TIMEZONE` por su cuenta.
- Pruebas nuevas (`test_g01_reservas.py`): reproducción Codex corregida (web y
  bot con fecha naive en perfil Madrid sin `CRM_TIMEZONE` → UTC persistido
  `09:00:00+00:00` para 10:00 CET; bot 13:00 → `12:00:00+00:00`); consulta por
  día local con pared Madrid; Google simulado recibe `timeZone: Europe/Madrid`;
  conflicto perfil-Guayaquil + `CRM_TIMEZONE`-Madrid rechazado; sin perfil,
  `CRM_TIMEZONE` Madrid alimenta al interno; nombre operativo del perfil con
  sobrescritura del instalador.

## R2 — Extracción segura (`api/procesamiento.py`, `tests/test_g01_handoff.py`)

- Sólo el **último** mensaje puede responder y sólo si es `AIMessage`; humano,
  sistema, herramienta, grafo cortado o asistente vacío → respuesta vacía, sin
  retroceder a respuestas anteriores. `str(objeto)` eliminado: los bloques se
  normalizan a texto autorizado (`type == 'text'`).
- Pruebas con clases reales de LangChain: `HumanMessage` privado, `ToolMessage`
  interno, `SystemMessage`, asistente vacío tras tool, asistente con bloques
  (texto sale; `tool_use`/metadatos no), y el mismo recorrido por el adaptador
  de audio. En todos: exactamente un registro y cero envíos de datos internos.
- Fixture corregida: la pregunta del paciente es `HumanMessage` (antes
  `AIMessage`, que ocultaba la fuga).

## R3 — Horarios precisos (`crm/business_profile.py`, `tests/test_business_profile.py`)

- `check_window` reescrita: orden por instantes UTC; límites de jornada en
  pared local con segundos/microsegundos (sin truncar); semiabierto
  (`fin == cierre` válido); fin 00:00 cierra el día de inicio (una 23:00–00:00
  no dispara la regla multi-día); multi-día exige continuidad (regresión G01
  conservada); DST de primavera probado también.
- Casos de la revisión verificados en pruebas: Madrid 2030-10-27 02:45+02 →
  02:15+01 aceptado (30 min reales); 18:30→19:00:30 rechazado y 18:30→19:00:00
  aceptado; microsegundo tras cierre rechazado.

## Comandos y resultados reales (G01B)

```powershell
# Suite mínima (.venv-verify, Python 3.13.1)
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_p02c.py tests/test_p03.py tests/test_analytics.py tests/test_demo_seed.py tests/test_business_profile.py tests/test_g01_reservas.py -q --basetemp=.pytest_cache/g01b-min
# 135 passed in 213.83s; salida 0

# Suite del bot (venv del workspace; incluye agente/API/handoff)
./venv/Scripts/python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_p02c.py tests/test_p03.py tests/test_analytics.py tests/test_demo_seed.py tests/test_business_profile.py tests/test_g01_reservas.py tests/test_calendar_tool.py tests/test_agent.py tests/test_api.py tests/test_g01_handoff.py -q --basetemp=.pytest_cache/g01b-bot
# 160 passed in 283.88s; salida 0 (4 avisos de deprecación de FastAPI on_event)
```

Iteración registrada: durante el desarrollo fallaron (a) el nombre de la
fixture nocturno/noturno, (b) la resolución que omitía el chequeo de conflicto
cuando el test no traía TIMEZONE, y (c) dos pruebas propias que inyectaban
`TIMEZONE` Guayaquil junto al perfil Madrid (conflicto ahora intencional).
Corregidas; el resultado final es el de arriba.

## Límites G01B

- La nota del dashboard `/api/chat` acumula mensajes IA con su propia lógica
  (endpoint demo con token privado); la extracción endurecida cubre el canal
  WhatsApp texto/audio. Queda anotado por si Codex quiere extenderlo.
- Sin cambios en P04/Google real; la interrupción de la ejecución bot de Codex
  no se reprodujo aquí: la suite bot completa se ejecutó entera (ver arriba).
