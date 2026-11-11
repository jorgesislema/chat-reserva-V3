# BOT-EVAL-01 — Reporte de entrega (segunda vuelta)

> **Actualización 9-11-2026:** el código cambió después de este informe. La
> re-ejecución con el código vigente está en `REPORTE_2026-11-09.md` y
> `EVIDENCIAS/reglas_nov9c/` (225 casos, 0 fallos críticos). Este documento se
> conserva como evidencia histórica del 6-11.

Fecha: 6 de noviembre de 2026. Estado: **lista para revisión, no aceptada**.
Repositorio con cambios sin commit (conservados) + archivos nuevos sin
seguimiento. Sin push, despliegue, envíos reales ni servicios externos.

## Batería tono_v2 en modo reglas (código final congelado)

`tools/evals/cli.py --modo reglas` en 4 lotes (1–56, 57–112, 113–168,
169–222) + `tools/evals/combinar` → `EVIDENCIAS/reglas/`:

| Métrica | Valor |
|---|---:|
| Casos | 225 |
| Aprobados | 214 |
| Con observaciones (menores) | 5 |
| Fallidos | 0 |
| Bloqueados / omitidos | 1 / 5 |
| Fallos críticos | **0** |

Puerta determinista superada: cero fuga, precio/stock falso, commit falso,
doble efecto o IA tras pausa.

## Qué cambió respecto a la primera vuelta

Primera ejecución (código a medio editar): 5 fallidos + 1 crítico
(SEG04/NEG02/NEG03/TIM03/TIM05). Correcciones aplicadas, todas en código
salvo 2 precondiciones de dataset con trazabilidad:

- `crm/chat_adapter.py`: instrucción encubierta en documentos nunca se repite
  ni se obedece; rescate verificando contra catálogo; «cobres» en detector de
  precio; «un/una dólar» como importe afirmado; neutralización en contexto remoto.
- `crm/canal.py`: negación en selección de cancelación mantiene las citas;
  alternativas con fecha; intención `comprar` no secuestra preguntas
  informativas (precio/stock van a consulta).
- `docs/producto/evals/tono_v2/casos_nuevos.py` + entrada en `generar.py`:
  TIM03/TIM05 usan pregunta de precio con proveedor caído (el saludo puro es
  determinista y no prueba la pausa). Sin rebajar reglas.
- `tools/evals/juez.py`/`ejecutor.py`/`modelo.py`: verificación de pedidos
  (creados/cancelados), importes derivados explicados por la cotización y
  `total_falso` contra el pedido guardado; categoría `ventas`.

## Pruebas de regresión

`tests/test_bot_eval_01.py` (25) + `tests/test_regresiones_auditoria.py`
(16): 41 passed. Suites pertinentes (canal_rag, clasificador, simulador,
control_humano, outbox, reservas, migraciones): ver `REPORTE.md` del
recorrido comercial y `ENTREGA_CORRECCIONES_2026-11-06.md` para los 3 fallos
preexistentes conservados de `test_c02_canal.py`.

## Límites

Modo modelo real preparado pero no ejecutado (sin presupuesto). Sin pruebas
reales de WhatsApp/Google. Casos clínicos requieren política profesional.
