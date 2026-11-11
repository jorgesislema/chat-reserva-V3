# Resultado de la batería de evaluaciones — reglas

Generado: 2026-11-10T00:55:14+00:00. Datos sintéticos; sin envíos ni servicios externos.

| Dato | Valor |
|---|---|
| Dataset | `docs\producto\evals\tono_v2\casos.jsonl` |
| Modo | reglas |
| Adaptador de conocimiento | simulado |
| Semilla / reloj | 2030-01-07 / reloj por caso (fixture v2) |
| Casos | 54 |
| Turnos de usuario ejecutados | 58 |

## Conteo por estado

| Estado | Casos |
|---|---:|
| aprobado | 53 |
| aprobado_con_observaciones | 0 |
| fallido | 0 |
| bloqueado | 1 |
| omitido | 0 |
| no_ejecutado | 0 |
| **hallazgos críticos** | **0** |

## Por categoría

| Categoría | Aprobados | Con observaciones | Fallidos | Otros |
|---|---:|---:|---:|---:|
| canal | 6 | 0 | 0 | 0 |
| cobertura | 1 | 0 | 0 | 0 |
| despedida | 4 | 0 | 0 | 0 |
| fechas | 1 | 0 | 0 | 0 |
| humano | 7 | 0 | 0 | 0 |
| medios | 5 | 0 | 0 | 0 |
| negacion | 1 | 0 | 0 | 0 |
| presupuesto | 4 | 0 | 0 | 0 |
| profesional | 1 | 0 | 0 | 0 |
| queja | 4 | 0 | 0 | 0 |
| seguridad | 6 | 0 | 0 | 0 |
| texto | 5 | 0 | 0 | 0 |
| timeout | 4 | 0 | 0 | 1 |
| ventana | 4 | 0 | 0 | 0 |

## No ejecutados, omitidos o bloqueados

| Caso | Estado | Motivo |
|---|---|---|
| TIM02 | bloqueado | La inyección de un timeout posterior al commit no está implementada en el ejecutor; requiere trabajo de dominio y no se cuenta como aprobado. |

## Límites

- Modo reglas: motor y adaptador deterministas; no evalúa el tono de un modelo real ni la tasa de alucinación de un proveedor.
- Los casos marcados como bloqueados u omitidos no cuentan como aprobados.
- Una excepción del ejecutor se reporta como fallo, nunca como aprobación.
