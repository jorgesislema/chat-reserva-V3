# Resultado de la batería de evaluaciones — reglas

Generado: 2026-11-07T22:57:40+00:00. Datos sintéticos; sin envíos ni servicios externos.

| Dato | Valor |
|---|---|
| Dataset | `docs\producto\evals\tono_v2\casos.jsonl` |
| Modo | reglas |
| Adaptador de conocimiento | simulado |
| Semilla / reloj | 2030-01-07 / reloj por caso (fixture v2) |
| Casos | 56 |
| Turnos de usuario ejecutados | 76 |

## Conteo por estado

| Estado | Casos |
|---|---:|
| aprobado | 50 |
| aprobado_con_observaciones | 0 |
| fallido | 1 |
| bloqueado | 0 |
| omitido | 5 |
| no_ejecutado | 0 |
| **hallazgos críticos** | **0** |

## Por categoría

| Categoría | Aprobados | Con observaciones | Fallidos | Otros |
|---|---:|---:|---:|---:|
| cobertura | 1 | 0 | 0 | 0 |
| duplicados | 5 | 0 | 0 | 0 |
| familia | 4 | 0 | 0 | 1 |
| fechas | 6 | 0 | 0 | 0 |
| fragmentos | 3 | 0 | 0 | 2 |
| multiturno | 7 | 0 | 0 | 0 |
| negacion | 4 | 0 | 0 | 2 |
| precios | 6 | 0 | 0 | 0 |
| productos | 5 | 0 | 0 | 0 |
| profesional | 4 | 0 | 1 | 0 |
| saludos | 5 | 0 | 0 | 0 |

## Casos fallidos (no críticos incluidos)

| Caso | Categoría | Códigos |
|---|---|---|
| PRO15 | profesional | hecho_faltante |

## No ejecutados, omitidos o bloqueados

| Caso | Estado | Motivo |
|---|---|---|
| FRAG02 | omitido | requiere modelo real (no autorizado en modo reglas) |
| FRAG03 | omitido | requiere modelo real (no autorizado en modo reglas) |
| NEG04 | omitido | requiere modelo real (no autorizado en modo reglas) |
| NEG05 | omitido | requiere modelo real (no autorizado en modo reglas) |
| FAM05 | omitido | requiere modelo real (no autorizado en modo reglas) |

## Límites

- Modo reglas: motor y adaptador deterministas; no evalúa el tono de un modelo real ni la tasa de alucinación de un proveedor.
- Los casos marcados como bloqueados u omitidos no cuentan como aprobados.
- Una excepción del ejecutor se reporta como fallo, nunca como aprobación.
