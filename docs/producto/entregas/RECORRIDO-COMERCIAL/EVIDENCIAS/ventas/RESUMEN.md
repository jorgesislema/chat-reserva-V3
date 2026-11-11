# Resultado de la batería de evaluaciones — reglas

Generado: 2026-11-07T22:51:20+00:00. Datos sintéticos; sin envíos ni servicios externos.

| Dato | Valor |
|---|---|
| Dataset | `docs\producto\evals\ventas_v1\casos.jsonl` |
| Modo | reglas |
| Adaptador de conocimiento | simulado |
| Semilla / reloj | 2030-01-07 / reloj por caso (fixture v2) |
| Casos | 14 |
| Turnos de usuario ejecutados | 59 |

## Conteo por estado

| Estado | Casos |
|---|---:|
| aprobado | 14 |
| aprobado_con_observaciones | 0 |
| fallido | 0 |
| bloqueado | 0 |
| omitido | 0 |
| no_ejecutado | 0 |
| **hallazgos críticos** | **0** |

## Por categoría

| Categoría | Aprobados | Con observaciones | Fallidos | Otros |
|---|---:|---:|---:|---:|
| ventas | 14 | 0 | 0 | 0 |

## Límites

- Modo reglas: motor y adaptador deterministas; no evalúa el tono de un modelo real ni la tasa de alucinación de un proveedor.
- Los casos marcados como bloqueados u omitidos no cuentan como aprobados.
- Una excepción del ejecutor se reporta como fallo, nunca como aprobación.
