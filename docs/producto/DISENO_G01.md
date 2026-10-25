# Diseño G01 — Estabilización: configuración compartida, métricas y un registro por interacción

Fecha: 23-10-2026. Correcciones G01B (R1–R3) añadidas al final, sección 9.
Alcance G01 de `PROMPT_GLM_01_ESTABILIZACION.md`: corrige
A1, el registro duplicado de A2 y A5 de `AUDITORIA_REPO_2026-10-23.md`.
Implementador: GLM. Revisión: Codex. No autoaceptación.

## Paso 1 — Diagnóstico (causas comprobadas en el código, no repetición del reporte)

### A1. Horarios duplicados en tres sitios y ausentes del servicio

`api/agent.py` contiene la política TRES veces con constantes propias:
`consultar_horarios` (texto fijo L–V 08–18 UTC-5), el «escudo» de
`wrapper_verificar_disponibilidad` (líneas 97–126, `HORARIO_INICIO/FIN`,
`ZONA_HORARIA_ECUADOR = timezone(-5h)` fija, no IANA) y la validación de
`wrapper_agendar_cita` (líneas 162–190), además del prompt de `call_model`.
`crm/reservation_service.py` no tiene política operativa alguna: la web acepta
cualquier intervalo futuro. Causa raíz: la regla vive en la capa de
presentación del bot en lugar del servicio compartido; compartir solapes no
comparte horarios. Además el escudo del bot valida sólo la hora inicial
(`hora < 8 or hora >= 18`) mientras agendar valida el intervalo completo contra
un cierre calculado con reloj de pared — dos reglas distintas en el mismo canal.

### A2. Doble registro de HANDOFF

`api/main.py::procesar_mensaje_langgraph` (y su variante async): al detectar
`[HANDOFF]` ejecuta `registrar_interaccion(handoff_activado=True)` y `return`
dentro del `try`; el `finally` se ejecuta igual y registra una segunda fila con
`handoff_activado=False` y `error=None`. Causa: el retorno anticipado no
suspende `finally`. El recorrido por el worker llama a esta función, por lo que
el defecto está en el flujo real, no sólo en la función de registro.

### A5.1. Duración con reloj de pared

`crm/analytics.py` calcula `duracion_min` restando `end_local - start_local`
(dos datetimes convertidos a la misma ZoneInfo): mide pared, no tiempo
transcurrido. En el salto de primavera de Madrid la pared avanza 2 h en 1 h
real. Corrección: restar instantes UTC y usar la zona local sólo para las
dimensiones (fecha/hora), como ya hace para las claves.

### A5.2. Procedencia del bot invisible

`save_appointment` inserta `origin='local'` para toda creación (línea del
INSERT, P01) y no existe concepto de canal: la reserva del bot (`actor='bot'`
en auditoría) y la de la web son indistinguibles. El ETL mapea `origin` a
`dim_origen`, así que el bot aparece como «local». No puede inferirse del
título (frágil y suplantable) ni atribuir en bloque el histórico.

### ETL sin instantánea común

Las tres lecturas del ETL corren en autocommit (el conector sólo abre
transacción implícita con DML): cada SELECT ve una fotografía distinta. Con
escritura concurrente pueden entrar un lead nuevo y una cita que lo referencia
en instantes distintos. Corrección: `BEGIN` de lectura explícito (deferred;
en WAL no bloquea escritores) alrededor de las tres lecturas.

## Paso 2 — Perfil de negocio y regla compartida

**Nuevo módulo `crm/business_profile.py`** (sólo stdlib; usable por web, bot y
pruebas mínimas). `BusinessProfile` validado en construcción:

- `name`, `industry` (clave de rubro), `industry_label`, `zone` (IANA
  validada), `currency`, `terminology` (sustantivo de paciente, ejemplos de
  urgencia) y `hours`: mapa día→[apertura, cierre] en minutos `HH:MM`;
  día ausente = cerrado. Al menos un día abierto; apertura < cierre.
- `load_profile(path)` lee JSON; cualquier defecto → `ProfileError` con mensaje
  claro (no arranca con reglas parciales). `load_configured(env_value)`
  resuelve `CRM_PERFIL_NEGOCIO`; sin variable usa el perfil interno por
  defecto (equivalente al comportamiento actual: L–V 08–18,
  `America/Guayaquil`, dental, USD) para no romper instalaciones existentes.
  El perfil se cambia con la variable o el archivo, sin editar Python.
- `check_window(start_utc, end_utc) -> motivo|None` — la regla única:
  - Intervalo de un día local: inicio ≥ apertura y fin ≤ cierre del día.
  - Intervalo multi-día: sólo válido si todos los días implicados están
    abiertos 00:00–24:00 (disponibilidad continua); si no, se rechaza con
    motivo explícito. Así una instalación 24×7 acepta 49 h y un perfil
    restringido las rechaza, con la misma función.
  - Trabaja sobre instantes UTC convertidos a la zona del perfil (respeta DST
    para la pared, sin aritmética de reloj).

**Integración en el servicio** (`crm/reservation_service.py`):
`save_appointment(..., channel=None, window_policy=None)`:
- Si `window_policy` rechaza: se devuelve el código nuevo
  `outside_business_hours` (400 en API) salvo excepción administrativa:
  `role='admin'` con motivo no vacío; el motivo queda en historial/auditoría
  marcado como excepción. El bot llama con rol de usuario: no puede pedir la
  excepción. Se aplica sólo a altas/reprogramaciones: ninguna cita existente
  se cancela ni modifica por la adopción.
- `channel`: procedencia de creación (`web`|`bot`|`google`), explícita y
  validada; NULL = histórico desconocido. Reprogramar conserva el canal.
  Separado de `origin` (que gobierna sincronización y protección demo, que se
  conserva intacta).

**Web** (`crm/app.py`): carga el perfil en `create_app` y pasa
`window_policy=profile.check_window` en alta web, API y reprogramaciones.

**Bot** (`crm/integration.py` + `api/agent.py`): `reserve()` pasa
`channel='bot'` y la misma política del mismo perfil; los textos de
`consultar_horarios`, el escudo de disponibilidad, la validación de
`wrapper_agendar_cita` y el prompt del sistema se generan desde el perfil
(nombre, rubro, días/horas, zona IANA real en vez de UTC-5 fijo). Una sola
fuente para humanos y máquina.

**Perfiles de ejemplo** (`perfiles/*.json`, ficticios): consultorio dental
(L–V 08–18, `America/Guayaquil`, USD) y servicios con citas
(L–V 09–19, S 09–13, `Europe/Madrid`, EUR). Mismo código, cero edición Python.

**Contrato futuro documentado** (no se construye en G01): pantalla de horarios
= editar el JSON/campos del perfil; feriados/excepciones y catálogo de
servicios con duraciones serán campos adicionales del mismo perfil con sus
propias reglas; no hay editor de marca (logo/colores siguen a cargo del
instalador). Una instalación, un perfil; no es multiempresa.

## Paso 3 — Métricas y ETL

- Duración entre instantes UTC; dimensiones locales (ya correctas). Caso
  obligatorio Madrid 2030-03-31 01:30+01→03:30+02 = 60 min; también otoño.
- Estrella: `dim_origen` se sustituye por `dim_canal` (web/bot/google/
  desconocido) + columna `es_demo` en `fact_citas` (origin='demo'). El bot es
  reconocible; el histórico sin canal se muestra como «desconocido» (no se
  inventa). Documentado en REPORTE_G01.
- Migración v4 (`crm/store.py`): `ALTER TABLE crm_appointments ADD COLUMN
  channel TEXT` + backfill `channel='google' WHERE origin='google'` (esa
  procedencia sí es conocida). Atómica e idempotente como v1–v3; conserva
  `event_id`, datos e historial.
- ETL: `BEGIN` de lectura alrededor de las tres SELECT (snapshot único,
  sin bloquear escritores en WAL); rechazo con error claro si
  `source` y `target` resuelven al mismo archivo (realpath/samefile);
  reconstrucción atómica del destino conservada.

## Paso 4 — Una interacción por procesamiento

`api/procesamiento.py` nuevo: `procesar_mensaje(telefono, texto, *,
invocar, registrar, enviar, registrar_envio=None)` — orquestación y telemetría
con **un único** `registrar` en el `finally`, con el flag `handoff` correcto:
respuesta con `[HANDOFF]` → 1 registro `handoff=True` y no se envía nada;
éxito → 1 registro (con envío); respuesta vacía → 1 registro; excepción del
grafo o del envío → 1 registro con `error`. `api/main.py` conserva sus dos
funciones públicas como adaptadores delgados (texto pasa `registrar_envio`
como hoy; audio no) con las dependencias reales inyectadas. La señal de
derivación se conserva; la pausa persistente de IA y su bandeja siguen siendo
P04 (no se construyen aquí).

## Pruebas (antes de implementar, cobertura que exige el prompt)

- `tests/test_business_profile.py` (entorno mínimo): validación, perfil
  inválido con error claro, dos perfiles ejemplo distintos (zona ≠ UTC-5),
  ventana: día cerrado, antes de apertura, fin después del cierre, multi-día
  en 24×7 y rechazo en restringido, Madrid DST.
- `tests/test_g01_reservas.py` (entorno mínimo): mismo intervalo
  aceptado/rechazado idéntico por web (Flask) y bot (`integration.reserve`)
  contra el perfil restringido; 49 h aceptada en fixture 24×7 (consistencia
  temporal separada de horario); excepción admin fuera de horario con motivo,
  auditoría y negación al bot; citas existentes intactas tras adoptar perfil;
  canal web/bot/google + histórico NULL; migración v4 idempotente.
- `tests/test_analytics.py` (adaptar + ampliar): duración UTC en primavera y
  otoño de Madrid; dim_canal/es_demo; reconstrucción con escritura concurrente
  (FK completos, conteos dentro del rango antes/después); source=target
  rechazado; idempotencia conservada.
- `tests/test_g01_handoff.py` (entorno del bot, dobles de prueba, sin IA ni
  WhatsApp): texto y audio, éxito, HANDOFF, vacío y error del grafo/envío →
  exactamente un registro coherente cada uno, recorriendo las funciones
  públicas de `api/main.py` (no sólo la función de registro), sin arrancar
  workers ni tocar `analitica.db` (dependencias inyectadas/monkeypatcheadas).
- Regresiones: suites mínima y completa habituales + `test_agent`/`test_api`
  en el entorno del bot. No se retira cobertura; adaptaciones justificadas en
  el reporte (p. ej. `dim_origen`→`dim_canal`).

## Política de compatibilidad

- Nuevos parámetros opcionales en `save_appointment` (canal, política):
  firmas anteriores siguen funcionando; todas las pruebas P01–P03 existentes
  deben pasar sin cambios salvo adaptación documentada.
- La regla de horario sólo filtra altas/reprogramaciones nuevas; nada cancela
  o modifica citas históricas. `origin='demo'` y su exclusión de Google se
  conservan literalmente.
- Sin pantalla de horarios/feriados/catálogo (contrato documentado), sin
  multiempresa, sin P04/P05.

## 9. Correcciones G01B (revisión Codex, R1–R3)

### R1 — Una sola autoridad de zona

`business_profile.resolve_profile(legacy_zone)` es el único punto de resolución:

- Con `CRM_PERFIL_NEGOCIO`: la `zona` del perfil manda para web, bot,
  disponibilidad, sync y analítica. Si `CRM_TIMEZONE` indica otra zona, el
  arranque se **rechaza** con `ProfileError` («Conflicto de zona... nunca dos
  autoridades»). No hay aceptación silenciosa.
- Sin perfil: el perfil interno por defecto **adopta** `CRM_TIMEZONE`
  (compatibilidad); la variable alimenta al perfil, no compite con él.
- `crm/app.py`: `TIMEZONE` se **deriva** del perfil (ya no se lee
  independientemente); `BUSINESS_NAME` por defecto sale de `profile.name`
  (`CRM_BUSINESS_NAME` sigue como sobrescritura del instalador). En pruebas,
  `TIMEZONE` inyectada debe coincidir con el perfil inyectado o se rechaza.
- `crm/integration.py` (`reserve`, `local_availability`), `api/agent.py`
  (consulta remota) y la CLI de `crm/analytics.py` usan
  `configured_profile().zone`; nadie lee `CRM_TIMEZONE` por su cuenta.

Prueba clave (reproducción Codex corregida): perfil servicios/Madrid,
`CRM_TIMEZONE` ausente, reserva web y bot con `2030-01-07T10:00:00` sin
offset → UTC persistido `09:00:00+00:00` (CET) y no el −05 histórico; consulta
`view=day&date=2030-01-07` devuelve pared Madrid; Google simulado recibe
`timeZone: Europe/Madrid` en el cuerpo del evento.

### R2 — Sólo salida final válida del asistente

`api/procesamiento.py`:

- La respuesta es el texto del **último** mensaje **sólo si es `AIMessage`**;
  en cualquier otro caso (humano, sistema, herramienta, grafo cortado) la
  respuesta es vacía. No se retrocede a respuestas anteriores del asistente.
- `_texto_de_contenido` normaliza contenido cadena o por bloques: sólo bloques
  `{'type':'text'}`; **nunca** `str(objeto)` (evita filtrar `tool_use`,
  llamadas y metadatos al canal).
- HANDOFF y el registro único se conservan intactos. La fixture de pruebas ya
  representa la pregunta con `HumanMessage` real. Pruebas con clases reales
  de LangChain: humano, sistema, herramienta, asistente vacío, asistente con
  bloques (texto autorizado sale; estructuras no), texto y audio.

### R3 — Política de horario precisa

`BusinessProfile.check_window` reescrita:

- **Orden temporal por instantes UTC**: Madrid domingo 2030-10-27
  02:45+02 → 02:15+01 (30 minutos reales) es válido dentro de 00:00–04:00.
- **Pared local con precisión de segundos/microsegundos** sólo para los
  límites de jornada: 18:30→19:00:00 vale, 18:30→19:00:30 se rechaza; no se
  trunca nada para autorizar un intervalo inválido.
- **Límites semiabiertos**: jornada `[apertura, cierre]`; `fin == cierre`
  válido; **fin a las 00:00 del día siguiente cierra el día de inicio** (no
  ocupa un día extra; una cita 23:00–00:00 se evalúa contra el cierre 24:00
  del día de inicio y no dispara la regla multi-día).
- La validación DST existente del servicio (horas locales inexistentes o
  ambiguas sin offset) permanece: `check_window` recibe instantes UTC ya
  resueltos por `to_utc`.
