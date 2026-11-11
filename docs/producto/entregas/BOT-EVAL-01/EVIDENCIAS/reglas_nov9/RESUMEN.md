# Resultado de la batería de evaluaciones — reglas

Generado: 2026-11-09T17:40:00+00:00. Datos sintéticos; sin envíos ni servicios externos.

| Dato | Valor |
|---|---|
| Dataset | `docs\producto\evals\tono_v2\casos.jsonl` |
| Modo | reglas |
| Adaptador de conocimiento | simulado |
| Semilla / reloj | 2030-01-07 / reloj por caso (fixture v2) |
| Casos | 225 |
| Turnos de usuario ejecutados | 274 |

## Conteo por estado

| Estado | Casos |
|---|---:|
| aprobado | 215 |
| aprobado_con_observaciones | 4 |
| fallido | 0 |
| bloqueado | 1 |
| omitido | 5 |
| no_ejecutado | 0 |
| **hallazgos críticos** | **0** |

## Por categoría

| Categoría | Aprobados | Con observaciones | Fallidos | Otros |
|---|---:|---:|---:|---:|
| cambios | 10 | 0 | 0 | 0 |
| canal | 6 | 0 | 0 | 0 |
| cobertura | 4 | 0 | 0 | 0 |
| comercial | 7 | 3 | 0 | 0 |
| despedida | 4 | 0 | 0 | 0 |
| duplicados | 5 | 0 | 0 | 0 |
| errores | 10 | 0 | 0 | 0 |
| familia | 4 | 0 | 0 | 1 |
| fechas | 7 | 0 | 0 | 0 |
| fragmentos | 3 | 0 | 0 | 2 |
| humano | 17 | 0 | 0 | 0 |
| informacion | 10 | 0 | 0 | 0 |
| medios | 5 | 0 | 0 | 0 |
| multiturno | 20 | 0 | 0 | 0 |
| negacion | 5 | 0 | 0 | 2 |
| precios | 16 | 0 | 0 | 0 |
| presupuesto | 4 | 0 | 0 | 0 |
| productos | 14 | 1 | 0 | 0 |
| profesional | 6 | 0 | 0 | 0 |
| queja | 4 | 0 | 0 | 0 |
| reservas | 10 | 0 | 0 | 0 |
| saludos | 15 | 0 | 0 | 0 |
| seguridad | 16 | 0 | 0 | 0 |
| texto | 5 | 0 | 0 | 0 |
| timeout | 4 | 0 | 0 | 1 |
| ventana | 4 | 0 | 0 | 0 |

## No ejecutados, omitidos o bloqueados

| Caso | Estado | Motivo |
|---|---|---|
| FRAG02 | omitido | requiere modelo real (no autorizado en modo reglas) |
| FRAG03 | omitido | requiere modelo real (no autorizado en modo reglas) |
| NEG04 | omitido | requiere modelo real (no autorizado en modo reglas) |
| NEG05 | omitido | requiere modelo real (no autorizado en modo reglas) |
| FAM05 | omitido | requiere modelo real (no autorizado en modo reglas) |
| TIM02 | bloqueado | La inyección de un timeout posterior al commit no está implementada en el ejecutor; requiere trabajo de dominio y no se cuenta como aprobado. |

## Límites

- Modo reglas: motor y adaptador deterministas; no evalúa el tono de un modelo real ni la tasa de alucinación de un proveedor.
- Los casos marcados como bloqueados u omitidos no cuentan como aprobados.
- Una excepción del ejecutor se reporta como fallo, nunca como aprobación.
