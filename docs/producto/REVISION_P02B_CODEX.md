# Revisión P02B — Codex

Fecha: 23-10-2026. Dictamen: **devuelta para corrección acotada; no aceptada**.
P01 permanece aceptada. No iniciar P03.

## Correcciones anteriores verificadas

El código incorpora versión/historial en cambios remotos relevantes y no cambia
la versión ante descarga idéntica. La cancelación exige versión. El estado review
queda fuera de reenvíos automáticos y las pruebas de ambos recorridos pasan.
La agenda incorpora intersección por día, franja dinámica, profesionales inactivos
con citas y descarte de respuestas antiguas. Mes conserva fecha para el alta.
Se inspeccionaron mobile-first-360.png y detail-history-360.png: el calendario
aparece antes y el historial es legible, aunque persiste espacio prescindible
del encabezado global. Esto último no es un bloqueo de esta corrección.

## R1 — Reprogramación pierde la fecha final (alta)

agenda.js:openReprogramForm conserva startParts[0], pero descarta endParts[0].
El formulario tiene una única fecha. submitAppointmentForm reconstruye el fin
usando el mismo día o, según la hora, el siguiente. Por ello no representa
fielmente citas que duran más de un día ni eventos de día completo de igual hora.

Reproducción independiente del payload (no recorrido de navegador): crear con el
servicio una cita futura 10:00 → dos días después 11:00. Construir el payload
exactamente como hace el formulario al abrir/guardar sin modificar horas y
enviarlo al servicio con la versión vigente. Resultado:

```text
original_duration_hours 49.0
result saved
new_duration_hours 1.0
```

Se usó una base única `.pytest_cache/review-multiday-<uuid>.db`, sin datos reales.
Es una regresión de los campos separados, no un fallo del servicio al recibir
las fechas completas. Añadir fecha final explícita y conservar ambos extremos.
Validar el intervalo completo en vez de prohibir horas iguales sin considerar
fechas. Al seleccionar la celda 23:00, el código además asigna `24:00` a un input
time, valor inválido: debe usar 00:00 del día siguiente. Hallazgo estático adicional.

## R2 — Test dependiente de la hora del día (media)

Ejecución independiente:

```powershell
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/codex-p02b-review
# 1 failed, 74 passed in 83.31s; salida 1
```

Falló tests/test_p02.py::test_api_lifecycle_filters_and_security, línea 325.
Calcula start con ahora+30h, crea otra cita start+2h y consulta ambas en el día
local de la primera. En esta ejecución la base temporal confirmó:

```text
Profesional 1: 2026-10-24T22:03
Profesional 2: 2026-10-25T00:03
```

El filtro vacío es correcto para el día consultado. No alterar producción para
acomodar esa expectativa. Fijar una hora local segura en una fecha futura para
el test de filtros y probar medianoche aparte con expectativas por día.
Los 75/80 informados por DeepSeek corresponden a su ejecución, no a ésta.

## Límites y siguiente paso

Se intentó repetir tools/evidencia_p02b.py con WORK/EVIDENCE únicos dentro del
repositorio, sin sobrescribir evidencia anterior. Imprimió el inicio pero no
produjo resultados verificables; se interrumpió. No se declara recorrido propio
de navegador. Las capturas inspeccionadas provienen de la entrega de DeepSeek.
No se repitió la suite ampliada ni se probaron Google/WhatsApp reales.

git diff --check no detectó errores de whitespace; Git avisó de LF/CRLF.
No se modificaron aplicación, .venv-crm, analitica.db ni secretos; sin commit/push.
Siguiente paso: PROMPT_02C_DEEPSEEK.md. No reabrir los hallazgos ya resueltos ni
ampliar a P03; cerrar estas dos regresiones y entregar nueva evidencia.
