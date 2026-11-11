# Resultado de la batería de evaluaciones — reglas

Generado: 2026-11-09T17:17:24+00:00. Datos sintéticos; sin envíos ni servicios externos.

| Dato | Valor |
|---|---|
| Dataset | `docs\producto\evals\tono_v2\casos.jsonl` |
| Modo | reglas |
| Adaptador de conocimiento | simulado |
| Semilla / reloj | 2030-01-07 / reloj por caso (fixture v2) |
| Casos | 57 |
| Turnos de usuario ejecutados | 57 |

## Conteo por estado

| Estado | Casos |
|---|---:|
| aprobado | 53 |
| aprobado_con_observaciones | 3 |
| fallido | 1 |
| bloqueado | 0 |
| omitido | 0 |
| no_ejecutado | 0 |
| **hallazgos críticos** | **0** |

## Por categoría

| Categoría | Aprobados | Con observaciones | Fallidos | Otros |
|---|---:|---:|---:|---:|
| cambios | 7 | 0 | 0 | 0 |
| comercial | 6 | 3 | 1 | 0 |
| informacion | 10 | 0 | 0 | 0 |
| precios | 10 | 0 | 0 | 0 |
| reservas | 10 | 0 | 0 | 0 |
| saludos | 10 | 0 | 0 | 0 |

## Casos fallidos (no críticos incluidos)

| Caso | Categoría | Códigos |
|---|---|---|
| COM06 | comercial | hecho_faltante |

## Límites

- Modo reglas: motor y adaptador deterministas; no evalúa el tono de un modelo real ni la tasa de alucinación de un proveedor.
- Los casos marcados como bloqueados u omitidos no cuentan como aprobados.
- Una excepción del ejecutor se reporta como fallo, nunca como aprobación.
