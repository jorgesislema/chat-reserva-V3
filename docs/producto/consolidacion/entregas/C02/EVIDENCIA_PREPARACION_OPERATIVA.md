# Evidencia de preparación operativa — A/B/C/D (2026-10-28)

Comandos y resultados REALES de esta sesión (Git Bash, Windows, Python 3.13.1).
No se sustituyen por conteos históricos. Bases temporales y datos sintéticos;
sin secretos, sin datos de clientes, sin proveedores externos, sin commit/push,
sin despliegue. deploy.yml NO activado.

## Paso A — Disponibilidad y arranque

Código: `crm/health.py` (nuevo), `crm/app.py` (`/health`, `/ready`, 503 claro),
`serve_crm.py` (nuevo, waitress), `run_crm.py` (doc: desarrollo), `requirements-crm.txt`
(+waitress).

- Prueba nueva: `python -m pytest tests/test_c02_health.py -q -p no:cacheprovider
  --basetemp /tmp/healthA` → **5 passed, 2.56s, exit 0**
  (liveness vivo sin BD; ready 503 `base_datos_no_accesible`; ready 200 con IA
  `no_configurada`; `esquema_incompleto` v5; `esquema_posterior_al_codigo`; sin sesión).
- Regresión pegada a app.py: `tests/test_crm.py` → **26 passed, 66.61s, exit 0** (ver
  hallazgo); `tests/test_c02_config_funcional.py` → PASS (30 passed compartidos en la
  corrida combinada previa a la corrección del fixture).
- Comprobación de arranque operativo: `serve_crm.py` levanta waitress (verificado dentro
  de la verificación del paso C, cabecera `Server: waitress`).

### Hallazgo real corregido (preexistente, sólo en el fixture de test)

- `tests/test_crm.py` era dependiente de la HORA: 3 fallos tras ~16:30 local, con Flask
  3.1.2/pytest 8.1.1 (`.venv-verify`) y Flask 3.1.3/pytest 9.1.1 (`venv`) por igual.
- Causa: `crm/business_config.py:check_window` resuelve el horario efectivo desde
  `crm_settings` + perfil por defecto (lun–vie 08:00–18:00), NO desde
  `app.config['PROFILE']` que fija el fixture 24×7. Prueba decisiva: cita a las 09:00
  del día siguiente se crea (citas=1); cita a las 17:02 se rechaza «...terminar antes
  del cierre (18:00)».
- Corrección: sembrar `crm_settings` (`negocio_horarios` 24×7 + `negocio_zona`) en el
  FIXTURE de `tests/test_crm.py` — es lo que `check_window` realmente lee. CERO cambios
  de producto. Resultado: **26 passed, exit 0**.

## Paso B — Migración desde versión anterior REAL con contenido

Código: sin cambios (se usa `crm.store.initialize` y las migraciones v1..v12 existentes).

- Prueba nueva: `tests/test_c02_migracion_contenido.py::
  test_migracion_v5_con_contenido_respaldo_recuperacion` → **1 passed, 3.18s, exit 0**
  (`.venv-op`, Flask 3.1.3). Recorrido verificado:
  1. Base v5 REAL (migraciones genuinas 1..5) con datos sintéticos en 17 tablas.
  2. Respaldo PREVIO `sqlite3.Connection.backup()` en un solo archivo.
  3. `initialize` aplica v6..v12; `crm_migrations` = {1..12}.
  4. Conservación EXACTA: conteos idénticos, `integrity_check=ok`,
     `foreign_key_check` sin violaciones; canal histórico NULL; `origin='ia'`,
     `generation=0`; documento conserva nombre/versión/estado/cuerpo; stock 15
     conservado; 0 filas inventadas en `crm_settings`/`crm_inventory_imports`.
  5. La app lee: `/api/c02/knowledge` (doc publicado), `/api/c02/catalog`
     (MIG-S, MIG-P), `/api/appointments/1` (título); `probe_database` ok v12.
  6. SEGUNDA `initialize`: mismas versiones y mismos conteos (sin duplicados ni pérdidas).
  7. Recuperación del respaldo en otra ruta: esquema v5 intacto (sin columnas nuevas),
     probe = `esquema_incompleto`; restaurar+arrancar migra a v12 preservando datos y
     la app vuelve a leer.
- No se detectó defecto de migración: no se corrigió nada de producto en este paso.

## Paso C — Instalación reproducible en entorno nuevo y aislado

- Entorno: `.venv-op` creado con `py -3.13 -m venv .venv-op` (py 3.13.1, pip 24.3.1).
  NO se modificó ningún entorno existente (`.venv-verify`, `venv` intactos; nota:
  `.venv-verify` no tiene waitress — `import waitress` → exit 1 — es un entorno de
  pruebas, no operativo).
- Resolución: `pip install --dry-run --report ... -r requirements-crm.txt` → **exit 0**
  (índice accesible; 38 paquetes).
- Archivo nuevo `requirements-crm.lock.txt`: versiones EXACTAS del cierre
  (Flask 3.1.3, waitress 3.0.2, python-dotenv 1.2.4, google-api-python-client 2.201.0,
  pytest 9.2.0, tzdata 2026.6, ...).
- Instalación desde el archivo declarado: `pip install -r requirements-crm.lock.txt`
  → **exit 0**; importaciones del producto OK (flask/waitress/dotenv/googleapiclient/
  pytest + módulos `crm.app`, `crm.c02_docs`, `crm.c02_inventory`, `crm.chat_adapter`,
  `crm.health`). Documentos e inventario: sólo stdlib; cliente IA: urllib (stdlib).
- Verificación operativa autocontenida:
  `python scripts/verificar_instalacion_operativa.py` → **INSTALACION_OPERATIVA_VERIFICADA,
  exit 0**:
  - `OK /health 200 (liveness, sin BD)`
  - `OK /ready 200 (BD + esquema v12; IA no_configurada declarada)`
  - `OK servidor operativo waitress: waitress` (NO el servidor de desarrollo)
  - `OK datos sintéticos sembrados (doc publicado, catálogo, cita)`
  - `OK lectura funcional: /api/c02/knowledge, /api/c02/catalog, /api/appointments/1`
  Servidor temporal detenido siempre (éxito o fallo); configuración 100 % sintética.

## Documentación

- `GUIA_OPERACION_Y_RECUPERACION.md` (nueva): instalación, variables (sólo nombres),
  arranque, liveness/readiness y acciones por `reason`, respaldo previo, actualización,
  recuperación; política de copias PROPUESTA claramente separada del mecanismo manual
  (la copia PROGRAMADA NO está implementada).
- `LISTA_SALIDA_PRODUCCION.md`, `ESTADO.md`, `MATRIZ_TRAZABILIDAD.md`,
  `REGISTRO_EJECUCIONES.md`, `ENTREGA.md` y `RELEVO_ABACUS.md` actualizados con estos
  resultados.

## Alcance exacto de la regresión ejecutada en esta sesión

| Comando | Resultado |
|---|---|
| `pytest tests/test_c02_health.py` (2 corridas, antes/después de arreglos menores del propio test) | 5 passed, exit 0 |
| `pytest tests/test_crm.py tests/test_c02_config_funcional.py` (con fixture sin corregir) | 3 failed (sólo test_crm, hora del día) + 30 passed |
| `pytest tests/test_crm.py` (fixture corregido) | 26 passed, 66.61s, exit 0 |
| `pytest tests/test_c02_migracion_contenido.py` | 1 passed, 3.18s, exit 0 |
| `scripts/verificar_instalacion_operativa.py` (con .venv-op) | INSTALACION_OPERATIVA_VERIFICADA, exit 0 |
| `pip install -r requirements-crm.lock.txt` (en .venv-op) | exit 0 |

No se ejecutó la suite C02 completa en esta sesión (los pasos A/B/C añadieron módulos
nuevos y no tocaron lógica de producto existente salvo `app.py`, cubierto por
test_crm.py + config_funcional + test_c02_health). Los conteos previos (155/317) NO se
repiten ni se heredan.

## Estado final

A/B/C/D terminados y verificados. Quedan PENDIENTES para producción (no cerrados en
LISTA_SALIDA_PRODUCCION): validación externa del proveedor IA, WhatsApp/Google/
recordatorios reales, copias PROGRAMADAS, despliegue. NO se declara C02 cerrado ni
producción aprobada.


## Actualización 2026-10-28 — Cierre documental (reproducción propia de A y C)

La guía fue contrastada contra el código actual (sin cambios de producto): comandos,
variables y endpoints coinciden; el comando de respaldo de la guía crea ahora la carpeta
`backups` (hueco real de instalación limpia) y el alcance §0 distingue lo ejecutado por
implementador/revisor/este cierre de los pasos del operador sobre la base real. Se
reprodujeron ambas comprobaciones en `.venv-op` con las mismas bases temporales
sintéticas:

- `pytest tests/test_c02_health.py tests/test_c02_migracion_contenido.py -q
  -p no:cacheprovider` → **6 passed in 3.20s, exit 0**.
- `python scripts/verificar_instalacion_operativa.py` →
  **INSTALACION_OPERATIVA_VERIFICADA, exit 0** (waitress, /health, /ready BD v12 + IA
  no_configurada, siembra y lectura HTTP con sesión admin; servidor temporal cerrado).

Detalles y coherencia de los seis documentos en `REGISTRO_EJECUCIONES.md`
(CIERRE-DOC-OP-20261028) y `RELEVO_ABACUS.md` (CIERRE DOCUMENTAL). Sin commit/push;
producción NO aprobada; entrega lista para la revisión final operativa.


## Revisión independiente del cierre documental — 2026-10-28
Cierre aprobado en APROBACION_CIERRE_PREPARACION_OPERATIVA_CODEX.md. Sin suites/instalación limpia repetidas. Revisor corrigió sólo comando de guía §4: cargar .env, exigir origen existente/read-only y destino nuevo. Probe sintético real: carga .env y conserva fila; rechaza destino existente y origen ausente, exit0. No configuración operativa ni datos reales. Producción/integraciones externas no aprobadas.
