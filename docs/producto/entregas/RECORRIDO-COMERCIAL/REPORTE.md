# Recorrido comercial — Reporte de entrega

Fecha: 6 de noviembre de 2026. Estado: **lista para revisión, no aceptada**.
Sin commit/push/despliegue; sin secretos, bases reales ni servicios externos.
Búsqueda web usada sólo para documentación oficial (jina.ai); no incorporada
al bot. Si un proveedor exigiera cuenta nueva o pago, se detiene y se avisa:
no se contrató nada.

## Qué quedó corregido y qué no

- Cotización determinista y pedidos (`crm/comercio.py`, migración v27):
  fórmula única en centavos, precedencia explícita, envío pendiente sin total
  definitivo, regalo con stock, recotización ante cambios, confirmación
  idempotente, cancelación con reversión, pago pendiente salvo acción
  autorizada.
- Venta en el simulador (`crm/canal.py` rama `comprar`): variantes sin
  confusión, cantidad, referencias («ese», «el otro», número), consulta ≠
  confirmación, retiro/domicilio, resumen, persistencia antes de afirmar,
  alerta `por_revision` + pausa IA, pago contra entrega pendiente.
- Excel (`crm/comercio_excel.py` + 5 endpoints): plantillas descargables,
  preview/aplicar atómicos, validación por hoja/fila, reimportación y
  concurrencia detectadas, RAG de FAQ versionado por registro.
- Proveedores: «Meta» = `META_*` sobre adaptador openai-compatible.
  Jina (verificado en jina.ai oficial: Reader/Embeddings/Reranker/Search, sin
  modelo conversacional) no es compatible como principal: documentado, sin
  integración, sin llamadas. `AdaptadorConRespaldo` con incidencias.
- Resumen (`comercio.resumen` + panel): pedidos, coordinación, pago pendiente
  (nunca como cobrado), alertas, incidencias, sync/outbox con fallo, compras
  sin finalizar.
- BOT-EVAL-01 heredado: 5 fallos/1 crítico corregidos en código (eco de
  documento malicioso, detector de precio, negación en cancelación, fecha en
  alternativas, intención `comprar` que secuestraba preguntas informativas) y
  2 precondiciones ambiguas corregidas con trazabilidad.
- No verificado: modelo real, WhatsApp/Google reales, instalación Linux,
  recorrido visual en navegador (sin herramientas disponibles).

## Pruebas ejecutadas (comandos y resultados reales)

| Conjunto | Comando | Resultado |
|---|---|---|
| Cotización | `pytest tests/test_comercio_cotizacion.py` | 12 passed |
| Ventas en canal | `pytest tests/test_comercio_ventas.py` | 10 passed |
| Excel | `pytest tests/test_comercio_excel.py` | 8 passed |
| Resumen + endpoints | `pytest tests/test_comercio_resumen.py` | 3 passed |
| Proveedores | `pytest tests/test_comercio_proveedores.py` | 3 passed |
| Regresiones R1–R9 | `pytest tests/test_regresiones_auditoria.py` | 16 passed |
| Tono/contrato/juez | `pytest tests/test_bot_eval_01.py` | 25 passed |
| Ventas (batería) | `cli --modo reglas --sin-umbral-minimo --dataset ventas_v1` | 14/14, 0 críticos |
| Tono (batería) | `cli --modo reglas --dataset tono_v2` (4 lotes + `combinar`) | 222 casos: 211 + 5 obs, 0 fallidos, 1 bloq, 5 omit, **0 críticos** |
| Puerta final | `pytest` bot_eval + regresiones + 5 suites comercio + canal_rag + clasificador + simulador | **108 passed** |
| Pertinentes históricas | canal/control/outbox/reservas/migraciones | 3 failed preexistentes de `test_c02_canal.py` (documentados, sin tocar) |

Fallos preexistentes conservados (documentados en
`ENTREGA_CORRECCIONES_2026-11-06.md`, sin tocar): 3 de `test_c02_canal.py`
(motor simulado no crea la cita; cancelación TypeError).

## Iteraciones y fallos intermedios

1. Batería tono con código a medio editar: 5 fallidos/1 crítico (casos
   SEG04/NEG02/NEG03/TIM03/TIM05) → correcciones de código + 2 revisiones de
   dataset con trazabilidad → 0 fallidos en recheck dirigido.
2. Re-ejecución completa pisada por edición concurrente (resultados
   mezclados) → re-ejecución final con código congelado.
3. Juez demasiado estricto con importes derivados (descuento/total/envío) →
   cotización observada + `total_falso` contra el pedido guardado.
4. Intención `comprar` secuestraba preguntas de precio/stock → guardia de
   pregunta informativa.

## Limitaciones y trabajo pendiente

- Página de importación en el panel (hoy sólo API + plantillas).
- Modo modelo sin ejecutar (sin presupuesto); los casos clínicos requieren política
  profesional aprobada.
- Recorrido visual móvil/escritorio sin realizar.
- `demo_comercial.db`: base ficticia regenerable (`scripts/seed_demo_comercial.py --recrear`).
