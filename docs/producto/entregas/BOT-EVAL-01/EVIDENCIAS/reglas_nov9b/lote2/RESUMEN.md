# Resultado de la batería de evaluaciones — reglas

Generado: 2026-11-10T00:46:43+00:00. Datos sintéticos; sin envíos ni servicios externos.

| Dato | Valor |
|---|---|
| Dataset | `docs\producto\evals\tono_v2\casos.jsonl` |
| Modo | reglas |
| Adaptador de conocimiento | simulado |
| Semilla / reloj | 2030-01-07 / reloj por caso (fixture v2) |
| Casos | 57 |
| Turnos de usuario ejecutados | 84 |

## Conteo por estado

| Estado | Casos |
|---|---:|
| aprobado | 56 |
| aprobado_con_observaciones | 1 |
| fallido | 0 |
| bloqueado | 0 |
| omitido | 0 |
| no_ejecutado | 0 |
| **hallazgos críticos** | **0** |

## Por categoría

| Categoría | Aprobados | Con observaciones | Fallidos | Otros |
|---|---:|---:|---:|---:|
| cambios | 3 | 0 | 0 | 0 |
| errores | 10 | 0 | 0 | 0 |
| humano | 10 | 0 | 0 | 0 |
| multiturno | 14 | 0 | 0 | 0 |
| productos | 9 | 1 | 0 | 0 |
| seguridad | 10 | 0 | 0 | 0 |

## Límites

- Modo reglas: motor y adaptador deterministas; no evalúa el tono de un modelo real ni la tasa de alucinación de un proveedor.
- Los casos marcados como bloqueados u omitidos no cuentan como aprobados.
- Una excepción del ejecutor se reporta como fallo, nunca como aprobación.
