# RELEVO ABACUS — Continuidad entre usuarios del mismo agente

Único punto de continuidad para sesiones de Abacus IA. El siguiente usuario DEBE leer
este archivo, comprobar el estado guardado (git status + ESTADO.md) y ejecutar la
próxima acción concreta. No repetir análisis ni deshacer trabajo anterior.

## Objetivo vigente y alcance

Encargo de continuación funcional, **punto 1 solamente**: completar la configuración
funcional operativa del negocio desde el frontend Flask/Jinja existente
(`crm/templates/config.html` + `crm/static/crm_c02_config.js` + API `/api/c02/config`),
verificando E2E con datos sintéticos.

Campos que debe poder editar el cliente (admin) desde pantalla y persistir:
1. Nombre e información pública del negocio.
2. Saludo inicial (usado en conversación nueva).
3. Especialistas y su disponibilidad, aprovechando la gestión existente (tabla
   `crm_professionals`, pestaña Profesionales).
4. Horarios semanales (reglas operativas, no texto informativo).
5. Fechas cerradas y excepciones por fecha.

Requisitos transversales del encargo: edición con permisos administrativos y CSRF,
rechazo de valores inválidos con mensaje claro, no exponer notas internas/secretos al
cliente, y **los cambios de configuración no reinterpretan silenciosamente citas existentes**.

**EXCLUIDOS de esta sesión** (punto 2 y 3 de la continuación funcional, a documentar para
después, NO iniciar): selección explícita de servicio/profesional/duración/cita, y chat
interno con adaptador IA real, conocimiento editable y fuentes. CH-01 (bloqueos, toma
humana, canonicalización) está APROBADO: no rediseñarlo salvo regresión demostrada causada
por cambios propios.

## Trabajo recibido de agentes anteriores

- CH-01 aprobado por Codex (`APROBACION_CH01_IDENTIDAD_CANONICA_CODEX.md`); no reabrir.
- Revisión del encargo de continuación funcional (`REVISION_CONTINUACION_FUNCIONAL_CODEX.md`):
  dictamen NO CUMPLIDO como entrega completa. Configuración avance PARCIAL: existe
  `crm/business_config.py` con `effective_profile`, `saludo_negocio`, `check_window`,
  `config_get_extended`/`config_set_extended`; `c02_services` delega; `app.py` y `canal.py`
  importan la configuración efectiva. NO descartar ese trabajo.
- `REVISION_CONFIGURACION_02_CODEX.md` (segunda comprobación): NO CUMPLIDO. `config.html`
  conserva el perfil como snapshot y sólo saludo/horario textual/mensaje fuera son editables;
  `crm_c02_config.js` crea inputs con `val.disabled=true`. No hay controles para horarios
  semanales, excepciones, zona y especialistas. No existían `CONTINUACION_FUNCIONAL.md` ni
  `EVIDENCIA_CONTINUACION_FUNCIONAL.md`.

## Archivos modificados en esta sesión y propósito

(Se actualiza a medida que se avanza; el siguiente usuario debe revisar git status.)

- `docs/producto/consolidacion/entregas/C02/RELEVO_ABACUS.md` — este relevo.
- `crm/static/crm_c02_config.js`, `crm/templates/config.html` — frontend de configuración
  con edición real (perfil, saludo, horarios semanales, excepciones, especialistas,
  mensaje fuera) y persistencia vía `POST /api/c02/config`.
- `crm/app.py` — ruta de alta de cita (`api_appointment_create`) y formulario de agenda para
  usar la política de ventana y zona EFECTIVAS (mismas reglas panel y canal).
- `crm/canal.py` — uso del saludo en conversación nueva y respeto de la disponibilidad de
  especialistas (gestión existente) en el canal.
- Documentos de trazabilidad: `CONTINUACION_FUNCIONAL.md`, `EVIDENCIA_CONTINUACION_FUNCIONAL.md`,
  `ESTADO.md`, `MATRIZ_TRAZABILIDAD.md`, `REGISTRO_EJECUCIONES.md`, `ENTREGA.md`,
  `REVISION_CONTINUACION_FUNCIONAL_CODEX.md` NO se toca (informe del revisor, intacto).

## Estado por tarea

| Tarea | Estado |
|---|---|
| RELEVO_ABACUS.md creado | HECHO |
| Backend: especialistas desde gestión existente + sincronización de disponibilidad | HECHO |
| Backend: validaciones estrictas por clave con mensajes claros | HECHO |
| Backend: saludo integrado en conversación nueva (procesar_lote) | HECHO |
| Backend: panel usa window_policy y zona efectivas (app.py 3 rutas) | HECHO |
| Backend: canal usa check_window efectivo (excepciones por fecha también en canal/reagendar) | HECHO |
| Frontend: config.html + crm_c02_config.js con edición real (perfil, saludo, horarios, excepciones, especialistas) | HECHO — verificado en navegador |
| Tests pytest de configuración funcional (7 tests) | HECHO — 7 passed (2026-10-28) |
| E2E navegador con capturas (recarga persistente) | HECHO — exit 0, capture config-persistencia.png |
| Regresión pertinente | HECHO — 33 passed |
| Continuidad docs (CONTINUACION_FUNCIONAL, EVIDENCIA, ESTADO, matriz, registro, ENTREGA) | HECHO — creados/actualizados el 2026-10-28 |
| Revisión del revisor (Codex) de esta entrega parcial | PENDIENTE — el siguiente paso es la revisión, no más implementación |

## Comandos ejecutados en esta sesión

- `.venv-verify/Scripts/python.exe -m py_compile crm/business_config.py crm/canal.py crm/app.py` → COMPILE_OK (2026-10-28).
- `pytest tests/test_c02_config_funcional.py` → inicial 6F/1P; tras corregir canal (excepciones por fecha aplicadas en `_reservar_conn`/reagendar vía `_cfg_check_window`) → **7 passed** (2026-10-28).
- `pytest tests/test_c02_config_funcional.py tests/test_c02_canal.py tests/test_c02_frontend.py tests/test_c02_services.py -q` → **33 passed, exit 0, ~65s** (regresión pertinente).
- `.venv-verify/Scripts/python.exe scripts/e2e_crm_c02.py` → **exit 0**; `E2E C02 (cat): TODOS LOS CHECKS OK` (incl. "editar y guardar configuración; recarga persistente", TRACE recarga: nombre="Clínica Fixture E2E" saludo="Hola, ¿en qué le ayudo?" lunA="09:00" exc="2026-11-04") y `E2E C02 (bandeja): TODOS LOS CHECKS OK`; `VERIFY_OK` en ambas; captura `docs/producto/consolidacion/evidencias/c02/config-persistencia.png`.

## Hallazgos corregidos en esta sesión

- **Bug real**: el canal usaba `window_policy=profz.check_window` (sólo horarios semanales del
  perfil efectivo); las excepciones por fecha (cerrado/horario especial) no se aplicaban y la
  reserva se creaba en un día cerrado. Corregido en `crm/canal.py` (`_reservar_conn`, reagendar)
  usando `business_config.check_window(path, s, e)`. El panel ya lo usaba.
- **Bug latente**: `config_get_extended` devolvía `perfil.horarios` en minutos enteros, no en
  HH:MM, lo que habría roto el frontend; corregido a `_hhmm()`.
- Columna `updated_at` no existe en `crm_professionals`; la sincronización de disponibilidad
  actualiza solo `active`.

## Pruebas fallidas o bloqueos

- 2 tests del canal fallaron en una primera ejecución (mensajes de rechazo sin las palabras
  esperadas) porque el canal NO aplicaba las excepciones por fecha: era un bug funcional
  real, corregido en `crm/canal.py` (ver Hallazgos). Ya no aplica.
- El verificador post-hoc del runner E2E daba `VERIFY_FAIL saludo no guardado` por clave
  `saludo` vs `negocio_saludo`; corregido en `scripts/e2e_crm_c02.py`. Ya no aplica.
- No hay bloqueos abiertos.

## Próxima acción concreta (archivo, función, comportamiento que falta)

1. La implementación del punto 1 (configuración operativa) está completa y verificada en
   simulación (pytest 7/7 + regresión 33/33 + E2E exit 0 con captura). NO iniciar más
   implementación de configuración: detenerse para revisión del revisor.
2. El siguiente usuario debe, en este orden:
   a. Verificar el estado guardado (git status, `RELEVO_ABACUS.md`, `ESTADO.md`).
   b. Entregar a Codex para revisión: `CONTINUACION_FUNCIONAL.md` + `EVIDENCIA_CONTINUACION_FUNCIONAL.md`
      (salto del último dictamen NO CUMPLIDO sobre la UI disabled/3 textos).
   c. Tras la revisión, los pendientes registrados (NO iniciados) son: punto 2 — selección
      explícita de servicio, profesional, duración y cita en la conversación (`crm/canal.py`
      intención de reserva usa hoy el primer profesional y 30 min); punto 3 — chat interno con
      adaptador IA real, conocimiento editable y fuentes.
3. No reabrir CH-01 (aprobado) ni auditar de nuevo configuración sin una regresión nueva.

## Procesos temporales

Ninguno iniciado ni quedó abierto: los servidores del E2E (`run_crm.py` en puertos libres)
se terminan al finalizar cada fase del runner (`scripts/e2e_crm_c02.py`). Sin procesos en
segundo plano al cierre de la sesión (2026-10-28).
