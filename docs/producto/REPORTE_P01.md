# Reporte P01 — Base reproducible y reservas compartidas

Fecha: 23-10-2026. Rama: `actualisacion-dependencias`. Responsable de implementación: DeepSeek.
Revisor y responsable de aceptación: Codex.
Estado de la entrega inicial: **devuelta para correcciones por Codex** (ver `REVISION_P01_CODEX.md`).
Estado tras P01B: **aceptada por Codex**. Ver `REVISION_P01B_CODEX.md` para el
dictamen independiente y sus ejecuciones de 52 y 57 pruebas. Las secciones
históricas siguientes conservan los resultados y decisiones de cada entrega.

Sin commit, push ni despliegue. No se abrió ni imprimió el contenido de `.env`. No se usaron
datos de clientes ni se llamaron servicios reales de Google/WhatsApp/IA.

## P01B — Correcciones de la revisión

Fecha: 23-10-2026. Alcance: sólo corregir R1, R2 y R3 del dictamen; no se inició P02.

### R1 — Migraciones transaccionales y serializadas

Cambios en `crm/store.py`:

- Se eliminó `executescript` del ejecutor. El esquema se ejecuta como sentencias individuales
  (`_SCHEMA_V1_STATEMENTS`), sin commits implícitos.
- `initialize` usa `isolation_level = None` (autocommit) y controla `BEGIN IMMEDIATE` /
  `COMMIT` / `ROLLBACK` de forma explícita.
- Cada migración y el `INSERT` de su versión ocurren en la **misma transacción**. Un fallo
  posterior a DDL o a una modificación de datos revierte ambos.
- La adopción de una base CRM existente (sin `crm_migrations`) es una transacción atómica que
  registra la versión 1 sin borrar filas, índices ni identidades.
- La consulta y aplicación de versiones se serializa con `BEGIN IMMEDIATE`; la activación de WAL
  reintenta ante bloqueos momentáneos de otra inicialización.
- No se escribe `PRAGMA user_version`; un valor legacy distinto de 0 se conserva.

Evidencia (nuevas pruebas en `tests/test_p01b.py`):

- Fallo después de DDL: `review_partial` no persiste y las versiones quedan `[1]`; al retirar el
  fallo, reintentar aplica la versión 2 (`[1, 2]`).
- Fallo después de modificar datos: el `name` original no cambia; reintento aplica la migración.
- Dos conexiones inicializando a la vez: sin excepciones y versiones `[1]` sin duplicación.
- `PRAGMA user_version=7` se conserva tras `initialize`; una base nueva queda en 0.
- Adopción de base legacy preserva la fila existente.

### R2 — Horas locales inexistentes/ambiguas

Cambios en `crm/reservation_service.py`:

- `to_utc` valida horas locales **sin offset** con `fold` y vuelta de ida y vuelta a la zona:
  - Si ninguna lectura vuelve a la misma hora de pared → `NonexistentLocalTime` (salto de primavera).
  - Si ambas lecturas son válidas con offsets distintos → `AmbiguousLocalTime` (cambio de otoño).
- Los offsets explícitos (`+01:00`, `+02:00`, `Z`) se respetan sin desambiguar (contrato previo).
- Nuevos códigos estructurados: `nonexistent_local_time`, `ambiguous_local_time`, `invalid_zone`.
- La validación vive sólo en el servicio. La web muestra `result['message']`; el bot propaga el
  mensaje específico de `to_utc` sin reimplementar la regla.

Evidencia: `Europe/Madrid` `2030-03-31T02:30:00` se rechaza (inexistente); `2030-10-27T02:30:00`
se rechaza pidiendo offset; ambas ocurrencias con `+02:00`/`+01:00` se aceptan; zona inválida se
rechaza; fechas normales de Guayaquil/Madrid se conservan; la web y el bot no crean citas ante
los rechazos.

### R3 — Fixture y restauración

- `tests/conftest.py`: se sustituyó `pytest.importorskip` por import diferido normal dentro de la
  fixture. Si falta Pydantic, las suites del bot revelan el error de importación en lugar de
  omitirse. El subconjunto mínimo del CRM (que no usa la fixture) sigue pasando sin Pydantic.
- `README.md`: instrucciones de respaldo/restauración corregidas:
  - respaldo consistente con la API `backup`/`VACUUM INTO` (sin depender de WAL/SHM);
  - si se copian archivos, hacerlo con procesos detenidos y con la base + su propio WAL/SHM de la
    misma generación;
  - al restaurar, retirar la base y **cualquier** WAL/SHM ajeno y no mezclar generaciones.
- Ensayo de respaldo/restauración con base ficticia:
  `tests/test_p01b.py::test_sqlite_backup_and_restore_without_foreign_wal` crea una base temporal,
  toma un respaldo consistente, muta la base viva, la retira junto con sus WAL/SHM y restaura el
  respaldo; verifica que quedan exactamente las filas ficticias respaldadas.

### Comandos y resultados P01B (actuales)

```powershell
# 39 pruebas previas + 13 nuevas en el entorno mínimo, basetemp nuevo
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_demo_seed.py tests/test_p01b.py -q --basetemp=.pytest_cache/p01b-verify-1
# 52 passed

# Entorno completo del workspace (incluye calendario)
python -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_calendar_tool.py tests/test_demo_seed.py tests/test_p01b.py -q
# 57 passed

# Concurrencia de inicialización repetida 5 veces
.\.venv-verify\Scripts\python.exe -m pytest tests/test_p01b.py::test_concurrent_initialize_serialized_without_duplicates -q
# 1 passed (x5)

# Revelado de error real en suite del bot (minimal sin Pydantic)
.\.venv-verify\Scripts\python.exe -m pytest tests/test_database.py -q
# ERROR de colección: ModuleNotFoundError: No module named 'pydantic' (esperado: ya no se omite)
```

Versiones del entorno de verificación (sin reinstalar `.venv-crm`): Python 3.13.1, Flask 3.1.2,
pytest 8.1.1, python-dotenv 1.0.1, tzdata 2025.2, Werkzeug 3.1.9.

### Límites P01B

- No se probaron cuentas Google/WhatsApp reales ni la base operativa.
- `requirements.txt` del bot sigue sin considerarse reproducible; no se tocó.
- La suite del bot en el entorno mínimo falla por diseño al faltar Pydantic; debe ejecutarse en un
  entorno con `requirements.txt`.

## Objetivo de la entrega

- Base Python verificable para el CRM comercial sin IA/Qdrant/Google reales.
- Reglas de reserva únicas para la web y el bot antes de la agenda visual.
- Migraciones versionadas propias del CRM sin pisar la versión legacy.
- Instalación mínima y pruebas reproducibles con bases temporales.

## Diagnóstico de entorno (paso 1)

- Punto de entrada del CRM: `run_crm.py` → `crm.app:create_app` (Flask/Jinja, SQLite).
- Punto de entrada del bot: `crm.integration` (sin importar Flask ni la app web).
- Entorno del cliente `.venv-crm` (sólo lectura): Flask 3.1.2, pytest 8.1.1, python-dotenv 1.0.1,
  tzdata 2025.2, google-api-python-client 2.121.0, google-auth-httplib2 0.2.0, Werkzeug 3.1.9.
- Conflicto detectado: `tests/conftest.py` importaba `GestorDB` (→ Pydantic) aun para el CRM.
  Se corrigió con import diferido; el CRM ya no necesita Pydantic.
- `requirements.txt` (bot/Dash/Streamlit) sigue sin resolución reproducible; **no se tocó** y no es
  requisito del CRM. `requirements-crm.txt` se separó en mínimo, pruebas y sync opcional.

## Archivos afectados

| Archivo | Cambio |
|---|---|
| `crm/reservation_service.py` | **Nuevo.** Servicio común `save_appointment` y `cancel_appointment`. |
| `crm/app.py` | Rutas `/appointments` y `/appointments/<id>/cancel` delegan en el servicio. |
| `crm/integration.py` | El adaptador del bot delega en el servicio; ya no reimplementa SQL. |
| `crm/store.py` | Migraciones versionadas en `crm_migrations`; sin `PRAGMA user_version`. |
| `tests/conftest.py` | Import diferido de `GestorDB` (CRM sin Pydantic). |
| `tests/test_reservation_service.py` | **Nuevo.** 12 pruebas P01. |
| `requirements-crm.txt` | Instalación mínima (Flask, python-dotenv, tzdata). |
| `requirements-crm-test.txt` | **Nuevo.** Mínimo + pytest. |
| `requirements-crm-sync.txt` | **Nuevo.** Extra opcional de Google Calendar. |
| `.gitignore` | Ignora entornos de verificación `.venv-*/`. |
| `README.md` | Instalación con `.venv-crm`, entorno de verificación y pruebas actualizadas. |
| `docs/producto/ESTADO.md` | Estado P01 «lista para revisión». |
| `docs/producto/REPORTE_P01.md` | Este reporte. |

Archivos preexistentes modificados que **no** forman parte de P01 y se conservaron:
`README.md` (se amplió sin revertir cambios previos), `crm/calendar.py`, `requirements.txt`,
`seed_demo_crm.py`, `tests/test_demo_seed.py`. No se revirtió ninguno.

## Decisiones y desviaciones

1. **Un solo servicio para alta y reprogramación.** `save_appointment` recibe
   `appointment_id=None` para crear y un id para reprogramar. Así web y bot comparten validación,
   SQL, transacción y auditoría; la reprogramación excluye la propia cita y conserva `event_id`
   y `origin`.
2. **Actor explícito.** Un `int` representa un usuario humano (validado por FK en `crm_audit`);
   una cadena (por ejemplo `bot` o `system`) registra auditoría con `user_id=NULL` y etiqueta.
   Esto satisface «actor humano o sistema/bot» y permite probar el rollback por FK.
3. **Reloj inyectable.** `clock=` permite pruebas deterministas de pasado/futuro sin depender
   del reloj real. La web y el bot usan el reloj real y rechazan el pasado de forma coherente.
4. **Zona IANA explícita.** `to_utc` interpreta fechas sin offset en la zona indicada y respeta
   el offset cuando la cadena lo trae, normalizando siempre a UTC.
5. **Migraciones propias.** Se usa `crm_migrations`, no `PRAGMA user_version`, porque otras tablas
   legacy comparten el archivo SQLite. La adopción de una base ya existente registra la versión 1
   como línea base reejecutando sentencias `CREATE ... IF NOT EXISTS` (sin borrar filas ni índices).
6. **Dependencias separadas.** El CRM mínimo no instala Google; la sincronización se habilita con
   `requirements-crm-sync.txt`. El bot conserva `requirements.txt`.
7. **Horarios dentales.** No se trasladaron al servicio común; siguen fuera de él, para la fase de
   configuración de horarios. El adaptador del bot conserva temporalmente su validación de entrada.
8. **Estados.** Se mantienen `active`/`cancelled`; P02 añadirá asistencia con migración separada.

### Desviaciones

- El adaptador del bot calcula el fin a partir de `minutes` y valida nombre/teléfono antes de
  delegar; se consideró validación de entrada propia del bot, no regla de reserva duplicada.
- `tests/conftest.py` usa `pytest.importorskip` para `GestorDB`: en el entorno mínimo las pruebas
  que dependen del bot se omiten en lugar de fallar por Pydantic.

## Dependencias verificadas

Entorno de verificación **nuevo** `.venv-verify` (Python 3.13.1), creado dentro del workspace.
No se modificó el entorno del cliente `.venv-crm`.

```
Flask         3.1.2
pytest        8.1.1
python-dotenv 1.0.1
tzdata        2025.2
Werkzeug      3.1.9
```

Sin `google-*`, `pydantic`, `qdrant-client`, `dash`, `streamlit`, `langchain`.

Comando de instalación (tuvo que fijarse un CA válido; ver limitaciones):

```powershell
python -m venv .venv-verify
$env:PIP_CERT="C:\...\site-packages\certifi\cacert.pem"
$env:REQUESTS_CA_BUNDLE=$env:PIP_CERT
$env:SSL_CERT_FILE=$env:PIP_CERT
.\.venv-verify\Scripts\python.exe -m pip install -r requirements-crm-test.txt
```

### Limitación registrada

El proceso de pip heredaba una ruta CA inválida
(`C:\Program Files\PostgreSQL\18\ssl\certs\ca-bundle.crt`). Se resolvió apuntando
`PIP_CERT`/`REQUESTS_CA_BUNDLE`/`SSL_CERT_FILE` a `certifi` **sólo** para ese comando; no se
cambiaron variables del sistema ni la configuración del cliente. Queda como nota de entorno.

## Comandos y resultados reales

Todos ejecutados en esta entrega. No se reutilizan conteos históricos.

1. Suite relevante en el entorno completo del workspace:

```powershell
python -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_calendar_tool.py tests/test_demo_seed.py -q
# 44 passed
```

2. Suite CRM + reservas + demo en el entorno mínimo `.venv-verify`:

```powershell
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/verify-tmp
# 39 passed
```

3. Arranque del CRM en entorno mínimo sin integraciones pesadas:

```powershell
.\.venv-verify\Scripts\python.exe -c "from crm.app import create_app; app=create_app({'TESTING':True,'DATABASE':r'.pytest_cache/smoke.db','SECRET_KEY':'x'}); print(app.name)"
# crm.app  (heavy modules: [])
```

4. Prueba de concurrencia repetida 5 veces para descartar flakiness:

```powershell
for i in 1..5: python -m pytest tests/test_reservation_service.py::test_concurrent_same_slot_single_reservation -q
# 1 passed (x5)
```

Las 12 pruebas nuevas cubren: solape web/bot y citas contiguas; concurrencia con dos conexiones;
profesionales distintos e inactivo; fecha inválida/fin/pasado/offset/zona con reloj inyectable;
reprogramación con `event_id` y doble cancelación idempotente; rollback por FK/auditoría;
`origin=demo` conservado y excluido de Google; bot sin identidad de administrador; migraciones
idempotentes y equivalencia base nueva vs. base adoptada; importación sin IA/Qdrant/Google.

## Migración y restauración

- Tabla de versiones: `crm_migrations(version INTEGER PRIMARY KEY, applied_at TEXT)`.
- Base vacía: `initialize` crea tablas y registra la versión 1.
- Base existente con tablas `crm_*` y sin `crm_migrations`: se registra la versión 1 como línea
  base; las sentencias son `CREATE ... IF NOT EXISTS`, por lo que se preservan filas, índices e
  identidades. No se borran ni resiembran datos demo.
- Ejecutar `initialize` dos o tres veces es idempotente (probado).
- `PRAGMA user_version` no se modifica (probado que sigue en 0 en la base legacy de prueba).
- Para restaurar: detener procesos, reponer el archivo SQLite (y `-wal`/`-shm` si existen) y
  reiniciar. La migración se reaplica de forma idempotente sin recrear datos.

## Recursos de prueba

- Bases SQLite temporales bajo `tmp_path`/`.pytest_cache`; nunca `analitica.db`.
- Google simulado con factorías/clases falsas; sin red ni credenciales.
- Sin mensajes, citas ni datos personales reales.

## Fallos pendientes

- Ninguno detectado en las pruebas ejecutadas.
- Fuera de alcance de P01 y no verificados: cuentas Google reales, WhatsApp real, rendimiento de
  la sincronización y agenda visual. La sincronización con Google sigue usando red dentro de
  `BEGIN IMMEDIATE`; P03 debe abordarlo.
- La instalación del bot (`requirements.txt`) sigue sin considerarse reproducible; no se tocó.

## Criterios de aceptación

| Criterio P01 | Estado |
|---|---|
| Instalación limpia con entorno mínimo | Cumplido (`.venv-verify`, 39 pruebas) |
| Migración idempotente y preservación | Cumplido (prueba dedicada) |
| Web y bot con las mismas reglas | Cumplido (servicio común + pruebas) |
| Pruebas de concurrencia | Cumplido (dos conexiones reales, 5 repeticiones) |
| Sin dependencias IA/Qdrant/Google en el mínimo | Cumplido |
| Rollback por FK/auditoría | Cumplido |
| `origin=demo` excluido de Google | Cumplido |
| Permisos/CSRF existentes intactos | Cumplido (suite `test_crm.py`) |

Pendiente de decisión de Codex: aceptar P01 o devolver observaciones. No iniciar P02.
