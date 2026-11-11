# Recorrido comercial — Matriz requisito → código → prueba → evidencia

Fecha: 6 de noviembre de 2026. Estado: **lista para revisión, no aceptada**.

| # | Requisito del encargo | Código | Prueba | Evidencia |
|---|---|---|---|---|
| A1 | Precio normal / retiro / descuento / domicilio / envío / total, una fórmula | `crm/comercio.py::cotizar` | `tests/test_comercio_cotizacion.py` (12) | `pytest` 12 passed |
| A2 | Vigencia, alcance, condiciones, estado activo, zona del negocio | `cotizar` + `comercio_promociones/zonas` | vigencia/futura/vencida, zona sin tarifa | idem |
| A3 | Regalo con existencias e inventario | `cotizar` (regalo) + `confirmar` (reserva) | disponible/agotado, cancelación libera | idem |
| A4 | Pedidos con snapshot; cambios posteriores no alteran lo confirmado | `comercio_pedidos` + snapshot + recotización | cambio de precio exige recotizar | idem |
| A5 | Idempotencia, última unidad, pago pendiente, auditoría | `confirmar` (clave), `BEGIN IMMEDIATE`, `registrar_pago` | concurrentes, repetida, pago | idem |
| B1 | Identificar producto sin confundir variantes; cantidad; referencias | `canal.py::_menciona_producto`, `_cantidad_compra` | `tests/test_comercio_ventas.py` (10) | `pytest` 10 passed |
| B2 | Consulta ≠ confirmación; retiro/domicilio; resumen; confirmación explícita | `_dialogo_compra` | propuesta/negación/zona | idem |
| B3 | Persistir antes de afirmar; alerta + pausa IA; operador continúa | `confirmar` + `conv_raise_alert` + `conv_set_egress_paused` | pedido+alerta+pausa, silencio tras pedido | idem |
| B4 | Cancelación con reversión; pago contra entrega pendiente | `_cancela_pedido`, `comercio.cancelar` | cancela+stock, pago pendiente | idem |
| C1 | Plantillas CONFIGURACION/ACTUALIZAR_INVENTARIO descargables | `comercio_excel.plantilla_*` + `GET /api/comercio/plantilla/<cual>` | `tests/test_comercio_resumen.py` (endpoints) | `pytest` 3 passed |
| C2 | Preview/errores/duplicados/refs/atomicidad/reimportación/concurrencia | `vista_previa`/`aplicar` + endpoints | `tests/test_comercio_excel.py` (8) | `pytest` 8 passed |
| C3 | RAG por registro; retirar conocimiento anterior; sin notas internas | FAQ→`kb_*` versionado, `internal_notes` admin | faq actualiza/desactiva, retrieve | idem |
| D1 | «Meta» identificada; proveedor real implementado | `adaptador_por_defecto` (openai-compatible) | `test_bot_eval_01` (remoto guionizado) | 25 passed |
| D2 | Jina no conversacional: documentada, sin integración | `.env.example`, README, `adaptador_con_respaldo_desde_entorno` | revisión de docs oficiales (jina.ai) | este expediente |
| D3 | Principal+respaldo, timeouts/reintentos, sin duplicar acciones | `AdaptadorConRespaldo` | `tests/test_comercio_proveedores.py` (3) | `pytest` 3 passed |
| D4 | Fallo de ambos: conserva conversación, incidencia, deriva segura | propaga + `indisponible` + incidencia | ambos fallan → incidencia | idem |
| E1 | Resumen: pedidos, coordinación, humano, proveedor, importaciones, sync | `comercio.resumen` + panel + `dashboard.html` | `tests/test_comercio_resumen.py` | `pytest` 3 passed |
| E2 | Dataset ventas multiturno, verificación en BD además del texto | `docs/producto/evals/ventas_v1/` (14) + juez `total_falso`/pedidos | batería modo reglas | `EVIDENCIAS/ventas/RESUMEN.md` |
| E3 | Sin ingresos inventados; sin «servidor caído» sin medición | resumen (pendiente ≠ cobrado), incidencias con motivo | revisión de código | este expediente |
| E4 | Recorrido visual móvil/escritorio | — | no realizado: sin navegador disponible | pendiente declarado |

## No declarado cumplido

- Tono del modelo real, WhatsApp/Google reales, VM: fuera de alcance; todo simulado.
- Modo modelo del ejecutor: preparado, no ejecutado (sin presupuesto).
- UI de importación en panel: sólo API + plantillas descargables; página de
  importación pendiente.
