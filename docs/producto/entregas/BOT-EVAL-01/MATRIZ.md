# BOT-EVAL-01 — Matriz requisito → código → prueba → evidencia

Fecha: 6 de noviembre de 2026. Estado global: **lista para revisión, no
aceptada**. Los conteos de la batería están en `REPORTE.md` y en
`EVIDENCIAS/reglas/RESUMEN.md` (resultados actuales, no históricos).

| # | Requisito del encargo | Código | Regresión / caso | Evidencia | Estado |
|---|---|---|---|---|---|
| R1 | Salida humana/IA/sistema con comienzo durable; no reintento inseguro | `crm/egress.py`, `crm/c02_services.py` (outbox_mark_sending) | `tests/test_regresiones_auditoria.py::test_r1_*` | 16 regresiones verdes (29,56 s) | Verificado (heredado) |
| R2 | Memoria interna aislada por usuario; ids ajenos rechazados | `crm/c02_services.py`, `crm/app.py`, migración v24 | `test_r2_*` | idem | Verificado (heredado) |
| R3 | Borrador no retira publicación; reversión | `crm/c02_services.py`, migración v23 | `test_r3_*` | idem | Verificado (heredado) |
| R4 | Dependencias de prueba coherentes | `requirements-crm*.txt`, README | `test_r4_*` | idem | Verificado (heredado) |
| R5 | Temp y configuración de IA aisladas; red externa bloqueada | `tests/conftest.py` | `test_r5_*`, `conftest` autouse | idem | Verificado (heredado) |
| R6 | Baja de profesional migra calendario y no cancela | `crm/app.py`, `crm/calendar.py`, v25 | `test_r6_*` | idem | Verificado (heredado) |
| R7 | Límite de tres al crear y reactivar | `crm/app.py` | `test_r7_*` | idem | Verificado (heredado) |
| R8 | Métricas con estados canónicos | `crm/c02_services.py` | `test_r8_*` | idem | Verificado (heredado) |
| R9 | Una zona efectiva en agenda/alta/detalle/sync/resúmenes | `crm/business_config.py`, `crm/app.py`, `crm/canal.py` | `test_r9_*` | idem | Verificado (heredado) |
| M1 | 4500 centavos USD = USD 45; sin escala inventada; NULL ≠ gratis; monedas con exponente documentado | `crm/moneda.py`, `crm/chat_adapter.py`, `crm/c02_services.py` | `test_importe_centavos_*`, `test_catalogo_publico_*`, `test_precio_documental_*` | `EVIDENCIAS/ejemplos_antes_despues.md`, `tests` | Verificado en reglas |
| M2 | Precio/stock desde datos estructurados; documento/memoria no los sobreescriben | `crm/chat_adapter.py` (`_contexto_con_fuentes`, `_validar_hechos`), `crm/c02_services.py` (`_catalog_search`) | `test_precio_documental_antiguo_no_sobreescribe_al_catalogo`, `test_sin_dato_estructurado_no_se_acepta_una_cifra_del_modelo`, casos `PRE11`–`PRE16` | `EVIDENCIAS/reglas/resultados.json` | Verificado en reglas |
| M3 | Defensa factual verificable frente a `[n]` válido (importe/stock) | `crm/chat_adapter.py` (`_validar_hechos`, `_respuesta_determinista`, `_limpiar_presentacion`) | `test_remoto_corrige_importe_falso_aunque_cite_la_fuente`, `test_remoto_corrige_stock_falso`, `test_publico_quita_marcadores_*` | idem | Verificado con transporte ficticio |
| M4 | Separar recepción pública del chat interno; sin agenda ajena, sin jerga ni `[n]`; rubro/nombre configurables | `crm/chat_adapter.py` (`prompt_sistema`, perfiles), `crm/canal.py` (`_consulta_rag`), `crm/c02_services.py` (`responder_chat_internal`, `horario_negocio`) | `test_prompt_publico_e_interno_no_se_mezclan`, `test_publico_no_recibe_contadores_de_agenda`, `test_abstencion_publica_es_natural_y_ofrece_equipo` | idem | Verificado en reglas |
| M5 | Voz editorial: 1–3 frases, sin menús rígidos, tú por defecto/usted si se pide, sin IDs/ISO/jerga, sin políticas inventadas | `crm/canal.py` (textos, `_detectar_trato`, `_cita_descr`), `crm/business_config.py` (`negocio_trato`) | `test_trato_usted_y_vuelta_a_tu_se_mantienen`, `test_cancelacion_muestra_fechas_legibles_sin_ids`, `test_reserva_exitosa_no_inventa_politica_de_llegada`, casos `TXT*`, `DES*` | `EVIDENCIAS/ejemplos_antes_despues.md` | Verificado en reglas; rúbrica humana pendiente |
| M6 | Proponer antes de escribir y confirmar después del resultado | `crm/canal.py` (rama reservar) | `test_reserva_no_se_crea_con_si_pero_no_reserves`, casos `NEG01`, `DUP01` | idem | Verificado |
| M7 | Negaciones y matices: «sí, pero no reserves», «no la canceles» | `crm/canal.py` (`_autoriza_accion`, `_duda_no_autoriza`) | `test_reserva_no_se_crea_*`, `test_cancelacion_no_se_ejecuta_*` | idem | Verificado |
| M8 | Sólo afirmar acciones comprobadas | `_run_dialog` + dominio; juez `commit_falso` | Pruebas negativas del juez | `tests/test_bot_eval_01.py` | Verificado |
| M9 | Fallo del proveedor: mensaje seguro y mecanismo humano, sin fabricar respuesta | `crm/canal.py` (`indisponible`, RAG caído) | `test_fallo_del_proveedor_deja_aviso_de_sistema_y_pausa` | idem | Verificado |
| M10 | No reactivar IA por texto del cliente tras toma humana | `crm/canal.py` (`_paused`, `_ia_puede_emitir`) | `test_ia_no_responde_tras_toma_humana`, casos `HUM12`, `HUM15` | idem | Verificado |
| M11 | Identidad honesta si preguntan si es un bot | `crm/canal.py` (`_pregunta_identidad`) | `test_identidad_honesta_no_deriva_a_humano`, caso `SAL13` | idem | Verificado |
| M12 | Cierre/rechazo sin insistencia ni promesas de preferencia guardada | `crm/canal.py` (`_es_cierre`, `_es_no_contactar`) | casos `DES01`–`DES04` | idem | Verificado |
| M13 | Stock: «quedan», plurales, servicio sin inventario | `crm/chat_adapter.py`, `crm/c02_services.py` (`_catalog_search`) | `test_stock_publico_*`, casos `PROD01`–`PROD04` | idem | Verificado |
| M14 | Horario del negocio desde configuración; día cerrado legible | `crm/c02_services.py` (`horario_negocio`), `crm/business_config.py` | caso `SAL12`, `PRO14`, `VEN02` | idem | Verificado |
| M15 | Dataset ≥200 casos, ≥80 nuevos, ≥40 multiturno, split y bloqueos | `docs/producto/evals/tono_v2` | `test_dataset_tono_v2_cumple_el_encargo` | `VALIDACION.md`, `REVISIONES.json`, `EVIDENCIAS/reglas/RESUMEN.md` (225 casos, 44 multiturno, 214+5 aprobados, 0 fallidos, 0 críticos) | Verificado |
| M16 | Ejecutor sobre el flujo compartido real | `tools/evals/ejecutor.py` | `test_ejecutor_usa_el_flujo_real_y_crea_la_cita` | `EVIDENCIAS/reglas/resultados.json` (271 turnos) | Verificado |
| M17 | Juez independiente y pruebas negativas | `tools/evals/juez.py` | `test_juez_detecta_*`, batería | `EVIDENCIAS/reglas/RESUMEN.md` (0 críticos) | Verificado |
| M18 | Modo modelo real preparado y desactivado sin presupuesto | `tools/evals/cli.py` (`AdaptadorConPresupuesto`) | Revisión de código; no ejecutado | `REPORTE.md` | Preparado, **no ejecutado** |
| M19 | Informes JSON/Markdown con conteos separados y crítica | `tools/evals/reporte.py` | `RESUMEN.md` generado | `EVIDENCIAS/reglas/` | Verificado |
| M20 | Sin red, sin WhatsApp/Google, sin base operativa | `tests/conftest.py`, `EntornoCaso`, CLI | Ejecución completa | `REPORTE.md` | Verificado por diseño |
| M21 | Migración aditiva de trato sin romper bases | `crm/store.py` v26 | Suites de migraciones + `test_trato_*` | Resultados de pruebas | Verificado en bases nuevas |
| M22 | Documentación de continuidad | `ESTADO.md`, `README.md`, este expediente | — | — | Actualizado |

## Requisitos que NO se declaran cumplidos

- **Tono del modelo real**: no hay presupuesto autorizado; el modo modelo no se
  ejecutó. No se afirma «cero alucinaciones» ni naturalidad validada.
- **Casos clínicos** (dolor, embarazo, medicación, menores): requieren política
  aprobada por un profesional; el dataset los deja como bloqueados/omitidos y
  el bot se abstiene o deriva.
- **WhatsApp/Google/VM**: fuera de esta entrega; todo es simulado.
- **Casos bloqueados**: timeout tras commit y retorno explícito a IA (ver
  `REPORTE.md`); se listan como bloqueados, no como aprobados.
