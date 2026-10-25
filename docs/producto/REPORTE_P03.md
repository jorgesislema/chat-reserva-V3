# Reporte P03 — Google confiable y conexión administrable

Fecha: 23-10-2026. Rama `actualisacion-dependencias`. Estado: **implementada y
auto-revisada; aceptación condicionada a la prueba real con calendario exclusivo
autorizado** (pendiente del propietario). P01 y P02 siguen aceptadas. Sin commit,
push ni despliegue. Google se simuló en todas las pruebas; no se envió nada a
servicios reales ni se tocaron `analitica.db`, `.venv-crm` ni secretos.

Gobernanza: desde esta fase un único asistente ejerce dirección, implementación
y revisión (autorización del propietario registrada en `ESTADO.md`), conservando
la disciplina por fases y la evidencia ejecutable.

## Objetivo y alcance

Fiabilidad de la sincronización Google Calendar: red fuera de transacciones de
escritura (outbox), reintentos con retirada, conflictos administrables por una
persona, arriendos entre procesos y cola visible/operable en una pestaña de
administración. Diseño detallado en `DISENO_P03.md`; especificación en
`PROMPT_03_DEEPSEEK.md`. No cambian reglas de citas, agenda, notas ni bot.

## Cambios principales

| Archivo | Cambio |
|---|---|
| `crm/store.py` | Migración v3: `sync_attempts`, `sync_next_attempt`, tabla `crm_sync_leases`, índice de cola; ejecutor atómico de P01B conservado. |
| `crm/calendar.py` | Reescritura a outbox: reclamo corto, envío sin transacción, confirmación optimista por `row_version`, descarga fuera de transacción y fusión corta (lógica P02B intacta); arriendos por profesional con expiración; retirada 0→1→5→15→60→360→1440 min; conflicto lógico → `review`; `queue_for_resend` (reenvío manual con historial y versión). |
| `crm/app.py` | Pestaña admin `sync` (cola + estado por profesional) y ruta `POST /appointments/<id>/sync-retry` (admin, CSRF). |
| `crm/templates/sync.html` | **Nuevo.** Cola de sincronización, estado de calendarios y botón «Enviar ahora» con la política explicada. |
| `crm/templates/base.html`, `dashboard.html` | Enlace y inclusión de la pestaña (sólo administración). |
| `tests/test_p03.py` | **Nuevo.** 14 pruebas (ver detalle en DISENO_P03 §7). |
| `tests/test_p01b.py`, `test_p02.py`, `test_reservation_service.py` | Expectativas de versiones `[1,2]` → `[1,2,3]` por la migración v3 (adaptación justificada, sin retirar pruebas). |
| `tests/test_crm.py` | Pestaña `sync` en render de páginas y en 403 para no administradores. |
| `tools/evidencia_p03.py` | **Nuevo.** Escenarios ejecutables + recorrido real de navegador. |
| `docs/producto/` | `PROMPT_03_DEEPSEEK.md`, `DISENO_P03.md`, este reporte, `evidencias/p03/`. |
| `README.md` | Sección de sincronización confiable, CLI periódico y suite actualizada. |

Compatibilidad conservada: firma `sync(path, zone, service_factory)` (nuevo
`clock` opcional inyectable); resultados con `name/events/error` más los nuevos
`sent/failed/conflicts`; semántica P02B de reintento inmediato tras el primer
fallo, `review` excluido de la cola y demo excluido del envío.

## Comandos y resultados reales

```powershell
# Suite completa del workspace (venv: Python 3.12.14, pytest 9.1.1)
./venv/Scripts/python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_p02c.py tests/test_p03.py tests/test_calendar_tool.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/p03-full2
# 97 passed in 191.55s; salida 0

# Entorno mínimo .venv-verify (Python 3.13.1, sin Pydantic/IA/Qdrant/Google)
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_p02c.py tests/test_p03.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/p03-verify2
# 92 passed in 145.15s; salida 0

# Evidencia real con Google simulado y navegador (Python del sistema + Playwright)
python tools/evidencia_p03.py
# failures: []; flows: outbox_sin_bloqueo, retirada_y_recuperacion,
# conflicto_a_revision, arriendo_bloquea, arriendo_expira, reenvio_manual: ok
# consola no esperada: 0; recursos >=400 no esperados: 0
```

Primera ejecución de las suites: 4 fallos por las expectativas `[1,2]` de las
pruebas de migración P01B/P02; corregidas a `[1,2,3]` y re-ejecutadas en verde.
Se registran ambos resultados; no se ocultó el fallo intermedio.

La sonda de bloqueo (`test_network_runs_without_write_lock` y
`outbox_sin_bloqueo`) usa un segundo proceso SQLite que toma `BEGIN IMMEDIATE`
durante la llamada de red: con el diseño anterior habría obtenido `database is
locked`; ahora escribe con éxito.

## Auto-revisión (rol revisor)

- Diff revisado: la fusión de descarga conserva literalmente la lógica aceptada
  en P02B (versión e historial en cambios externos, no resucitar canceladas,
  `review` tras cierre); sólo cambia el orden transaccional, no las reglas.
- Reproducción independiente del estado final de la evidencia: la base temporal
  quedó con la cola esperada (1 `review`, 1 `pending` tras el reenvío manual),
  sin arriendos residuales y con `sync_attempts/next_attempt` en cero/NULL tras
  éxito.
- `pip check` en `.venv-verify` limpio; `git diff --check` sin errores de
  whitespace (avisos LF/CRLF de Git como siempre).
- Verificado que ningún GET muta, que la pestaña y la acción manual exigen
  administración + CSRF (403/400 según corresponda) y que el historial registra
  el reenvío con motivo.

## Límites y pendientes

- **Prueba real pendiente**: calendario exclusivo autorizado por el propietario
  (cuenta de servicio ya soportada). Es el único criterio de aceptación de P03
  que queda abierto; hasta entonces el estado es «aceptación condicionada».
- El reintento vencido ocurre en el próximo ciclo (botón, tarea programada o
  CLI `flask --app crm.app:create_app sync-calendar`); no hay demonio de reloj.
- OAuth sigue siendo decisión pendiente; no se promete atomicidad entre
  sistemas: la política de conflictos es la documentada en `DISENO_P03.md`.
- No se modificaron `requirements*`; Playwright sigue siendo sólo evidencia.

## Criterios de aceptación P03

| Criterio (PLAN.md) | Estado |
|---|---|
| Reintentos y retirada | Cumplido (pruebas + evidencia, simulado) |
| Conflictos administrables | Cumplido (`review` + cola + reenvío manual) |
| Corte de red sin pérdida ni bloqueo | Cumplido (outbox con sonda real de bloqueo) |
| Sin escritura SQLite bloqueada durante la red | Cumplido (sonda + edición concurrente) |
| Prueba real en calendario exclusivo | **Pendiente del propietario** |

## Siguiente paso

Solicitar al propietario el calendario de prueba y la variable de credenciales
para la verificación real de P03. En paralelo (tarea independiente permitida),
especificar P04 (bandeja y transferencia humana), que no depende de Google.
