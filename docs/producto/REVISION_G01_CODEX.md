# Revisión G01 — Codex

Fecha: 23-10-2026. Dictamen: **devuelta para correcciones; no aceptada**.
Se conserva el alcance G01; P04 y Google real no se implementan en esta revisión.

## R1 — El perfil no gobierna la zona en todos los adaptadores (alta)

crm/app.py carga PROFILE, pero TIMEZONE sigue viniendo de CRM_TIMEZONE o Ecuador.
crm/integration.py:reserve/local_availability y la consulta remota en api/agent.py
también usan esa variable antigua/default. El prompt del agente y check_window
usan, en cambio, profile.zone. Seleccionar sólo el perfil Madrid no adapta el
negocio coherentemente; una variable heredada puede producir otro resultado.

Reproducción con base ficticia única y profesional local, perfil de ejemplo
servicios/Madrid y CRM_TIMEZONE ausente en el proceso de prueba:

```text
reserve(..., '2030-01-07T10:00:00', 60)
Madrid_profile_10_local_stored 2030-01-07T15:00:00+00:00
expected_Madrid_UTC 2030-01-07T09:00:00+00:00
```

La reserva se desplazó seis horas. Unificar resolución de zona para formularios,
bot, disponibilidad, sync y analítica. Documentar precedencia de variables legacy;
un conflicto no debe aceptarse silenciosamente. Las pruebas actuales inyectan
TIMEZONE y CRM_TIMEZONE coincidentes: no prueban seleccionar sólo el perfil.

## R2 — Se pueden enviar mensajes humanos o de herramientas (alta)

api/procesamiento.py:_extraer toma el último mensaje no vacío sin filtrar tipo;
el código anterior limitaba la extracción a AIMessage. Al quedar vacía la última
respuesta IA se retrocede a texto humano, de herramienta o una respuesta vieja.

Reproducción con dobles que conservan type/content y envío/registro simulados:

```text
[human('USER_PRIVATE_TEXT'), ai('')] -> envío USER_PRIVATE_TEXT
[tool('INTERNAL_TOOL_DATA'), ai('')] -> envío INTERNAL_TOOL_DATA
Ambos casos: un registro (la duplicación sí se corrigió).
```

Sólo una respuesta final válida de asistente puede salir al cliente. No enviar
ToolMessage, HumanMessage, SystemMessage ni contenido anterior como sustitución
de una respuesta vacía. Probar clases reales de LangChain y ambos adaptadores.
La fixture actual usa AIMessage para representar «pregunta», ocultando este caso.

## R3 — La política de horarios aún compara mal durante DST (media)

BusinessProfile.check_window convierte ambos extremos a la misma ZoneInfo y
compara reloj local, y además trunca segundos al comprobar cierre. Reproducción:

```text
Madrid, domingo con apertura 00:00–04:00:
2030-10-27T02:45:00+02:00 -> 2030-10-27T02:15:00+01:00
real_minutes 30.0
window_rejection El fin es anterior al inicio

Madrid, lunes 09:00–19:00:
18:30:00 -> 19:00:30 -> check_window devuelve None (acepta 30s tras cierre)
```

La duración BI ya usa UTC correctamente, pero la nueva política puede rechazar
intervalos válidos o aceptar fuera de jornada. Validar orden entre instantes y
límites completos con una política explícita para cambios estacionales.

## Qué se comprobó favorablemente

Perfil externo y regla compartida existen; excepciones de horario comprueban rol
y motivo en servidor; canal separado de origin y protección demo se mantienen;
ETL usa snapshot y duración UTC; source=target se rechaza; el registro único de
HANDOFF está implementado. No se pidió rehacer esas partes ni la arquitectura.

## Pruebas y recursos

Reproducciones R1/R2/R3 ejecutadas con Python .venv-verify, datos ficticios,
env sólo del proceso y base `.pytest_cache/review-g01-<uuid>.db`. No hubo red.
No se modificaron aplicación, .venv-crm, analitica.db ni secretos.
Ejecución independiente terminada:

```powershell
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_p02c.py tests/test_p03.py tests/test_analytics.py tests/test_demo_seed.py tests/test_business_profile.py tests/test_g01_reservas.py -q --basetemp=.pytest_cache/codex-g01-min
# 122 passed in 136.44s; salida 0
```

También se lanzó `venv/Scripts/python.exe -m pytest tests/test_agent.py
tests/test_api.py tests/test_g01_handoff.py -q
--basetemp=.pytest_cache/codex-g01-bot`. Mostró dos puntos de avance y quedó sin
resultado final durante la revisión; se interrumpió. No se atribuye la causa a
un defecto de G01 sin diagnóstico ni se declara aprobado ese subconjunto.
Los 140 tests informados por GLM no se reprodujeron completamente.
git diff --check sin errores, avisos LF/CRLF.

Siguiente paso: PROMPT_GLM_01B_CORRECCIONES.md. No iniciar otras fases.
