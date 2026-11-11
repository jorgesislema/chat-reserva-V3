# Diagnóstico inicial — Recorrido comercial demostrable (2026-11-06)

Fecha: 2026-11-06. Rama: `aucla`. Sin commit/push/despliegue. Sin secretos, bases reales ni servicios externos.

## Estado inicial verificado contra código (no sólo reportes)

- R1–R9: correcciones presentes en el árbol (`crm/egress.py`, `c02_services.py`, `store.py` v23–v26, `app.py`, `calendar.py`, `business_config.py`, `conftest.py`). Regresiones `tests/test_regresiones_auditoria.py` existen. Línea base previa del agente anterior: 41 passed (`test_bot_eval_01` + regresiones). No se revierte.
- BOT-EVAL-01 (trabajo previo sin seguimiento en git): `crm/moneda.py`, `tools/evals/*`, `docs/producto/evals/tono_v2` (222 casos), `tests/test_bot_eval_01.py`, `DISENO.md`/`MATRIZ.md` existen. Faltaba `REPORTE.md` y `EVIDENCIAS/reglas/` (4 lotes paralelos lanzados, sin resultados todavía; no bloquean el recorrido comercial).
- Catálogo: `crm_catalog_items` + revisiones, kinds `producto|servicio|regalo|promocion`, `stock_na`, `publish_state`, precio en centavos. Sin pedidos, líneas, cotizaciones, reglas de entrega, promociones vinculadas, regalos con condiciones, pagos, reservas de stock ni incidencias.
- Inventario: `c02_inventory.py` existe (upload → preview → confirmación → aplicar atómico, duplicados por code, sha256 anti-reimportación, stock contado absoluto). Sólo cubre catálogo; no hay `CONFIGURACION_DEL_NEGOCIO.xlsx` ni `ACTUALIZAR_INVENTARIO.xlsx` con hojas PRECIOS.
- RAG: `crm_kb_documents/versions/fragments`, publicación por puntero, `kb_search`/`kb_retrieve_public`. Precios/stock se leen de BD en `_herramientas_chat`. Documentos como contenido (instrucciones maliciosas no cambian reglas: hay pruebas de inyección en evals).
- Simulador: `POST /api/c02/simulador` con copia `<base>.simulador-<operador>.db`, `WorkerCanal` + `MotorSimulado`, sin transporte. Atención humana: `conv_take/return`, `egress_paused`, `crm_human_alerts` (razones cerradas), pausa IA verificada en pruebas.
- Proveedores: `AdaptadorRemotoConfigurable` openai-compatible (`abacus` RouteLLM por defecto). "Meta" en repo = `META_API_KEY`/`META_MODEL` mapeados a endpoint openai-compatible (por defecto `https://api.meta.ai/v1`, modelo `muse-spark-1.3`); sin adaptador separado. Jina (verificado en jina.ai oficial): Reader/Embeddings/Reranker/Search; `ReaderLM-v2` es HTML→Markdown, no un modelo conversacional para ejecutar el flujo del bot. Conclusión: Jina no compatible como principal conversacional; se documenta y se conserva el proveedor funcional con respaldo explícito.
- Resumen: `_agenda_summary`, `claims_resumen`, métricas canónicas. Sin sección de pedidos/incidencias comerciales.

## Plan de ejecución (orden A→E, dependencias primero)

1. A — `crm/comercio.py` + migración v27 (tablas entrega/retiro, promociones vinculadas, pedidos/líneas con snapshot, cotizaciones con vigencia, pagos, reservas stock, incidencias, importaciones). Cotización determinista en centavos enteros, precedencia única, sin stacking no autorizado. Pruebas de cotización.
2. B — Flujo de venta en `canal.py` reutilizando `WorkerCanal`: identificar variante, cantidad, referencias, retiro/domicilio, resumen, confirmación explícita, persistir antes de afirmar, alerta vinculada, pausa IA, idempotencia, cancelación con reversión, última unidad con `BEGIN IMMEDIATE`, pago contra entrega pendiente. Pruebas de recorrido + concurrencia.
3. C — Excel: generadores de las dos plantillas + importadores por encima de `c02_inventory` (compatible), validación por hoja/fila, preview/confirm/atómico/auditoría/reimportación/concurrencia, RAG por registro con retiro del conocimiento anterior. Pruebas Excel válido/duplicado/inválido/referencias.
4. D — Proveedores: wrapper primario+respaldo con timeouts/reintentos limitados, registro de proveedor/duración/fallo/motivo; ambos fallan → incidencia + derivación segura. Jina documentado como no conversacional. Pruebas con simulados.
5. E — Resumen con incidencias + dataset de ventas multiturno + recorrido visual móvil/escritorio + `README`/`ESTADO.md` y entrega "lista para revisión".

Siguiente paso: crear migración v27 + `crm/comercio.py` con cotización determinista y pruebas.
