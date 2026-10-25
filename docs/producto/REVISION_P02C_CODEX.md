# Revisión P02C — Codex

Fecha: 23-10-2026. Dictamen: **P02C aceptada; P02 queda aceptada**.
P01 permanece aceptada. Con esta decisión se habilita especificar P03
(Google confiable y conexión administrable); no iniciarla sin su prompt.

La aceptación cubre el alcance de P02 (agenda visual día/semana/mes, estados
operativos, asistencia, observaciones internas, historial, diseño adaptable con
recursos locales). No certifica el producto completo, la sincronización con
cuentas Google/WhatsApp reales ni el despliegue: siguen en fases posteriores.

## Correcciones verificadas

### R1 — El formulario representa el intervalo completo

- `crm/templates/agenda.html` expone cuatro campos: `start_date`, `start_time`,
  `end_date`, `end_time`.
- `openReprogramForm` copia fecha y hora de ambos extremos; `submitAppointmentForm`
  compara la pared completa (`endLocal <= startLocal`) y admite horas de reloj
  iguales en fechas distintas. Reproducción independiente del escenario de la
  devolución (cita 10:00 → dos días después 11:00, reprogramada con el payload
  que construye el formulario): duración 49 h antes y después; sin acortamiento.
- La celda de 23:00 preselecciona fin 00:00 con `end_date` del día siguiente
  (`openCreateFromCell`); nunca se escribe 24:00. Confirmado en `form-23-360.png`.
- El alta desde Mes conserva la fecha pulsada en ambos extremos y deja las horas
  vacías (`openCreateForDay`), sin inventar hora ni cambiar el día.
- Inspección visual de `form-49h-1440.png` (inicio 25/10 10:00, fin 27/10 11:00)
  y `form-23-360.png` (inicio 30/10 23:00, fin 31/10 00:00): campos legibles y
  correctos en escritorio y móvil.

### R2 — Prueba estable y medianoche aparte

- `test_api_lifecycle_filters_and_security` usa hora local fija 10:00 en fecha
  futura (+30 días); `+2 h` no cambia de día local. Sin cambios en producción
  para acomodar la expectativa.
- `tests/test_p02c.py` (2 pruebas) cubre 49 h, 24 h con igual hora en días
  distintos, 23:00–00:00, 23:00–01:00, fin igual/ anterior rechazado, y el
  filtro por día con cruce de medianoche y expectativas por día.

No se encontraron regresiones nuevas en el código y las pruebas revisadas.
Los hallazgos resueltos en P02B (versión en cambios externos, estado `review`
fuera de reenvíos, citas fuera de ventana, alta desde Mes, carreras de vista)
no se reabrieron: se verificó su presencia en `crm/calendar.py` y la suite.

## Ejecución independiente

Desde la raíz del repositorio, basetemps nuevos dentro del workspace:

```powershell
# Suite completa del workspace (venv, Python 3.12.14, pytest 9.1.1)
./venv/Scripts/python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_p02c.py tests/test_calendar_tool.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/codex-p02c-full
# 82 passed in 139.49s; salida 0

# Entorno mínimo .venv-verify (Python 3.13.1, sin Pydantic/IA/Qdrant/Google)
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_p02c.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/codex-p02c-verify
# 77 passed in 105.25s; salida 0

.\.venv-verify\Scripts\python.exe -m pip check
# No broken requirements found.

git diff --check
# Sin errores de whitespace; avisos LF/CRLF de Git.
```

Recorrido de navegador repetido de forma independiente con
`tools/evidencia_p02c.py` (Playwright/Chromium del sistema, evidencia redirigida
a `.pytest_cache/codex-p02c-evidence-*` para no sobrescribir la entrega):
`failures: []`, consola no esperada 0, recursos >=400 no esperados 0. Cubre
49 h, 24 h, celda 23:00, 23:00–01:00, fin inválido sin POST, alta desde Mes y
zoom 200 %. Coincide con las capturas de `docs/producto/evidencias/p02c/`.

## Límites registrados (no bloquean esta aceptación)

- Google/WhatsApp simulados en pruebas; la red dentro de `BEGIN IMMEDIATE` y la
  resolución asistida de conflictos corresponden a P03.
- Sin aislamiento usuario-profesional (fuera de alcance P02, documentado).
- `requirements.txt` del bot conserva los rangos preexistentes a este plan; no
  se considera reproducible y no fue objeto de esta entrega.
- La valoración estética de esta revisión se limitó a las capturas P02C y al
  recorrido automatizado; el espacio del encabezado global en móvil señalado en
  la revisión de P02B sigue como mejora cosmética no bloqueante.

## Continuidad

No se modificó código de aplicación, `.venv-crm`, `analitica.db`, secretos ni
servicios externos durante esta revisión. Sin commit, push ni despliegue.

Siguiente paso: redactar `PROMPT_03_DEEPSEEK.md` (Google confiable: outbox,
reintentos con retirada, transacción sin red, conflictos administrables y
conexión gestionable), sin reabrir el alcance aceptado de P02.
