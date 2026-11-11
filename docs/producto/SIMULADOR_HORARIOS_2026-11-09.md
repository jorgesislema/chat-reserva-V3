# Horarios y almuerzos por profesional — evaluación del 9 de noviembre de 2026

Alcance: bot del canal ejecutado en el simulador (`WorkerCanal` +
`MotorSimulado` + `AdaptadorSimulado`), base SQLite sintética. Sin WhatsApp,
sin Google, sin datos de clientes.

Complementa `SIMULADOR_CONVERSACION_2026-11-09.md`.

## 1. Qué se probó

Se cargaron tres profesionales con jornadas y almuerzos distintos:

| Profesional | Días | Horario | Almuerzo |
|---|---|---|---|
| Dra. Ana | lunes a miércoles | 09:00–13:00 | 11:00–12:00 |
| Dr. Luis | jueves y viernes | 14:00–19:00 | 16:00–17:00 |
| Dra. Marta | lunes a viernes | 09:00–18:00 | 13:00–14:00 |

Seis conversaciones reales: cita con una doctora a una hora libre, a la hora
de su almuerzo, con un doctor que no trabaja ese día, pregunta por su horario,
petición sin preferencia y cita en el horario del segundo doctor. Evidencia:
`EVIDENCIAS/horarios_2026-11-09.json` y `EVIDENCIAS/sonda_horarios.py`.

## 2. Antes / después observado

| Conversación | Antes | Ahora |
|---|---|---|
| «Quiero una cita con la Dra. Ana el martes a las 12:00» | «¿Ya se ha hecho atender…?» sin mirar la agenda | «Tengo libre el martes 8 de enero a las 12:00 para Valoración con la Dra. Ana. ¿Se lo reservo?» |
| «… el martes a las 11:30» (almuerzo 11–12) | «A las 11:30 no alcanzamos» (sin explicar) | «La Dra. Ana tiene su pausa de almuerzo de 11:00 a 12:00. A las 12:00 tiene libre… ¿Le reservo?» |
| «… con el Dr. Luis el martes a las 10:00» | Preguntaba lo mismo o proponía a otro sin explicar | «El Dr. Luis no atiende el martes 8 de enero. Atiende jueves y viernes de 14:00 a 19:00. ¿Qué otro día le viene bien?» |
| «¿Qué horario tiene la Dra. Ana?» | Devolvía el horario del negocio (09:00–18:00) | «La Dra. Ana atiende lunes a miércoles de 09:00 a 13:00. Su pausa de almuerzo es de 11:00 a 12:00.» |
| «Quiero una cita el martes a las 10:00 para valoración» (sin preferencia) | Listaba a los tres, incluido el Dr. Luis que no trabaja ese día | Lista sólo a quienes pueden atender: Dra. Ana y Dra. Marta |
| «… con el Dr. Luis el jueves a las 16:30» (almuerzo 16–17) | No lo detectaba | Ofrece las 17:00 del mismo día |

## 3. Cambios

`crm/canal.py`:
- `_extract_professional`: el título «Dra.» se tomaba como nombre y asignaba
  siempre a la primera doctora; ahora se compara el nombre completo y, si no,
  el nombre de pila, nunca el título. Test: `PRO11` (Dra. Marta).
- `_con_articulo` / `_inicio_oracion`: «la Dra. Ana», «el Dr. Luis» en las
  respuestas (antes «con Dra. Ana»).
- `_datos_horario_profesional`, `_resumen_horario_profesional` y
  `_horario_profesional`: leen `crm_professionals.horario_json` y
  `almuerzo_inicio/fin`; responden la jornada propia agrupando días
  consecutivos (sin volcar siete líneas).
- Al pedir cita con un profesional nombrado y día/hora, no se interrumpe con
  «¿ya se ha atendido?»: se comprueba su jornada, su almuerzo y la agenda.
- Si el hueco cae en el almuerzo, se dice el intervalo real y se ofrece la
  primera hora válida después de la pausa.
- Si el profesional no trabaja ese día, se dice y se resumen sus días/horas.
- Sin profesional elegido pero con día/hora, la lista se reduce a quienes
  pueden atender de verdad; no se ofrecen doctores libres ese día.
- Los textos de propuesta/confirmación usan el artículo natural.

No se cambió la regla de negocio: la cita se sigue creando sólo tras
confirmación y revalidando el hueco en la transacción.

## 4. Pruebas

| Conjunto | Resultado |
|---|---|
| `tests/test_bot_eval_01.py` | **41 passed** (incluye 5 pruebas de horario/almuerzo) |
| `tests/test_c02_seleccion_cita.py` | **30 passed** |
| `tests/test_bot_eval_01.py` + `test_c02_seleccion_cita.py` | **71 passed** |
| `tests/test_c02_canal.py` + `test_c02_agenda_y_ficha.py` + `test_c02_atencion.py` | **38 passed** |
| `tests/test_business_profile.py` + `test_c02_config_funcional.py` | **28 passed** |
| Sonda de horarios | 6 recorridos, salida JSON |

Comandos reales en `.venv-op`, `--basetemp` local, `-p no:cacheprovider`, sin
red externa.

## 5. Límites y pendientes

- Sin `horario_json`/almuerzo cargado, manda el horario del negocio; el bot no
  inventa jornadas. El panel/Excel debe completar esos datos por profesional.
- La lista sin preferencia se reduce a los disponibles, pero todavía pide
  elegir número/nombre; se puede autoasignar al de menos carga si el negocio lo
  autoriza.
- Falta prueba dedicada de hueco ocupado por **otro** cliente y de cambio de
  hora entre doctores con almuerzos distintos.
- La batería completa `tono_v2` se re-ejecutó con este código: 225 casos,
  215 aprobados, 4 con observaciones, 0 fallidos, 1 bloqueado, 5 omitidos y
  0 fallos críticos (`EVIDENCIAS/reglas_nov9c/`).
