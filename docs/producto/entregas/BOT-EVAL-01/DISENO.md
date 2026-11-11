# BOT-EVAL-01 — Diseño y diagnóstico previo

Fecha: 6 de noviembre de 2026. Repositorio: `chat-reserva-V3`.
Estado: implementación para revisión de Codex; **no aceptada**.

Este documento registra el diagnóstico hecho **antes** de editar y las
decisiones tomadas. Las correcciones de la auditoría R1–R9 ya estaban
implementadas en el árbol de trabajo al empezar (16 regresiones en verde); no
se revirtieron ni se duplicaron. El detalle de esas correcciones sigue en
`ENTREGA_CORRECCIONES_2026-11-06.md`; aquí sólo se comprueba su estado.

## 1. Flujo real del canal

```
WhatsApp/webhook
  → crm.whatsapp_webhook (verificación y parseo)
  → crm.c02_services.wa_ingest        (mensaje inbound + operación en cola)
  → crm.canal.WorkerCanal.paso
      → procesar_lote → op_claim      (una operación por worker)
      → _run_dialog
          → detectar_peticion_humana  (reglas estructuradas, antes del LLM)
          → MotorSimulado | MotorIA/ClasificadorIntenciones
          → reservas / cancelación / reagenda (reservation_service bajo guardia)
          → _consulta_rag → c02_services.responder_chat_internal
                → AdaptadorSimulado | AdaptadorRemotoConfigurable
                → _herramientas_chat: KB publicada, catálogo publicado,
                  stock de la base, agenda según rol, horario del negocio
  → crm_outbox (pendiente, origen ia|humano|sistema, generación)
  → crm.egress.egress_drain → crm.transporte_whatsapp (no ejecutado aquí)
```

Persistencia: SQLite con migraciones versionadas (`crm_migrations`, v1–v26).
La base del canal es una por instalación; cada caso de evaluación usa una base
nueva en `.pytest_cache`, nunca una base operativa.

## 2. Estado de R1–R9 al empezar

| Hallazgo | Estado comprobado antes de editar | Evidencia |
|---|---|---|
| R1 salida humana duplicada | Corregido (marca durable común, CAS, liberación de diferidas) | 16 regresiones verdes |
| R2 memoria sin dueño | Corregido (migración v24, `owner`, rechazo de ids ajenos) | idem |
| R3 borrador retira publicación | Corregido (v23, versiones inmutables, puntero) | idem |
| R4 dependencias pytest | Corregido (runtime sin pytest; lock 9.2.0) | idem |
| R5 aislamiento de pruebas | Corregido (`conftest.py`: Temp, CRM_CHAT_*, red externa) | idem |
| R6 baja de profesional | Corregido (v25, origen/destino, barrido) | idem |
| R7 límite al reactivar | Corregido (transacción serializada) | idem |
| R8 métricas del asistente | Corregido (estados canónicos) | idem |
| R9 zona efectiva | Corregido (`zona_efectiva`, config efectiva) | idem |

Comando real de comprobación: `pytest tests/test_regresiones_auditoria.py` →
**16 passed** (29,56 s). No se modificó ninguna de esas correcciones.

## 3. Causas nuevas encontradas (con archivo)

### F1. Importes en centavos presentados como unidades
`crm/chat_adapter.py` (rama de catálogo del adaptador simulado) imprimía
`f'Precio: {precio} {moneda}'` con `price_cents=4500` → «USD 4500». El
contexto remoto dividía siempre por 100, lo que además es incorrecto para
monedas sin decimales (CLP/COP). `crm/moneda.py` no existía.
**Decisión:** una única autoridad `formatear_importe(centavos, moneda)` con
tabla ISO 4217 documentada; moneda desconocida → `None` (no se inventa escala);
`NULL` → `None` (no es gratuito).

### F2. Perfil público reutilizaba el asistente interno
`_PROMPT_SISTEMA` decía «asistente de consulta interna de una clínica dental»;
`_consulta_rag` llamaba a `responder_chat_internal` sin perfil; el simulado
respondía con contadores de agenda y el remoto podía filtrar `[n]`.
**Decisión:** `perfil='publico'|'interno'` en el adaptador y en el servicio;
prompt público con nombre/rubro configurables, sin `[n]`, sin contadores, con
identidad honesta; el interno conserva citas y agenda. Los permisos de las
herramientas no cambian.

### F3. `_mapear_citas` valida referencias, no verdad
Un texto con `USD 999 [1]` y una fuente real número 1 pasaba como «con
fuente». **Decisión:** `_validar_hechos` contrasta importes y conteos con los
hechos estructurados del contexto; si no coinciden, sustituye por la respuesta
determinista de la herramienta (o abstención). La fuente se conserva para
auditoría aunque el texto público no muestre `[n]`.

### F4. Textos fijos con IDs, fechas ISO, jerga y políticas inventadas
- `_texto_lista_citas` imprimía `#<id>` y `YYYY-MM-DD HH:MM`.
- Cancelación/reagenda confirmaban con `#id` y fecha ISO.
- El alta añadía «Si puedes llegar 15 minutos antes…», una política no
  configurada.
- Menús rígidos («Indica el número», «escribe no»), mezcla tú/usted
  (`Indique`, `Desea`), abstención técnica («conocimiento publicado»).
**Decisión:** fechas legibles en la zona efectiva (`miércoles 9 de enero a las
10:00`), sin IDs ni ISO; sin políticas inventadas; trato único por
conversación; abstención natural que ofrece el equipo.

### F5. «Sí, pero no reserves» autorizaba el alta
`_confirma_si` miraba sólo la primera palabra y además aceptaba «cancelar» como
afirmación. «Sí, pero no reserves todavía» creaba la cita; «Sí, pero no la
canceles» cancelaba.
**Decisión:** `_autoriza_accion` exige afirmación y ausencia de negación en el
mismo mensaje; una duda explícita responde «no reservo nada todavía» sin
escribir. La cancelación usa la misma función.

### F6. Fallo del proveedor sin mensaje al cliente
`intencion == 'indisponible'` y el fallo del RAG devolvían `texto=None` con
pausa: el cliente quedaba en silencio. **Decisión:** aviso de sistema breve,
veraz y sin prometer lectura («no puedo responder… he dejado tu mensaje al
equipo»), origen `sistema`, con la pausa y la alerta existentes.

### F7. Identidad y cierre
«¿Eres un bot?» podía interpretarse como petición humana por la frase «persona
real»; una despedida o un rechazo recibían una abstención genérica que podía
invitar a seguir vendiendo. **Decisión:** `_pregunta_identidad` responde con
honestidad sin derivar; `_es_cierre`/`_es_no_contactar` cierran sin insistir y
sin afirmar que se guardó una preferencia inexistente.

### F8. Stock y plurales
«¿Cuántos cepillos quedan?» no entraba en la rama de stock (faltaba «quedan») y
`_catalog_search` comparaba subcadenas sin singular/plural («cepillos» no
encontraba «Cepillo suave»). **Decisión:** palabras de stock ampliadas y
variantes singular/plural en la búsqueda.

### F9. Horario del negocio no respondido
El bot sólo listaba profesionales; no contestaba «¿abren el sábado?».
**Decisión:** herramienta `horario_negocio()` desde la configuración efectiva,
respuesta estructurada y sin inventar.

### F10. Horarios con `null` rompían el perfil
`business_profile.from_dict` exigía `[apertura, cierre]` en todos los días; un
día cerrado (`null`) lanzaba `ProfileError` al construir el perfil efectivo.
**Decisión:** `null`/`[]` = día cerrado, se omite la ventana; el ejecutor
también omite esos días al sembrar.

### F11. Fechas ISO en mensajes de excepción
`check_window` devolvía «El negocio está cerrado el 2030-01-08». **Decisión:**
`dd/mm/aaaa` legible.

## 4. Texto fijo, adaptador simulado y modelo remoto

| Capa | Qué es | Qué puede probar |
|---|---|---|
| Texto fijo (`canal.py`) | Plantillas deterministas de reserva, cancelación, cierre, derivación | Acciones, fechas, trato, no invención |
| `MotorSimulado` + `AdaptadorSimulado` | Heurística local sin red | Reglas, permisos, precios/stock desde datos, abstención |
| `AdaptadorRemotoConfigurable` | Cliente HTTP real | Calidad del proveedor, alucinación real… **no ejecutado** (sin presupuesto) |

El ejecutor de reglas usa `WorkerCanal` y los servicios de dominio; no existe
un bot paralelo. El modo modelo envuelve el adaptador remoto con límites de
llamadas/tokens y exige `--presupuesto-autorizado`. Esta entrega no consumió
API.

## 5. Estrategia de pruebas

- Regresiones nuevas en `tests/test_bot_eval_01.py` (24 casos): moneda, perfil,
  defensa factual, autorización, trato, fechas, aviso de sistema, contrato del
  ejecutor y pruebas negativas del juez.
- Dataset `docs/producto/evals/tono_v2`: 222 casos, 44 multiturno, 102 nuevos,
  49 reservados; validación estructural en el generador y en una prueba.
- Batería en modo reglas con base limpia por caso, reloj inyectado y juez
  independiente. Puerta: cero fallos críticos.
- Migración v26 (trato por conversación) aditiva; se prueba sobre bases nuevas
  y las suites de migraciones existentes.

## 6. Riesgos y límites declarados

- El modo reglas no mide naturalidad ni alucinación de un modelo real.
- Los casos marcados `requiere_modelo` o `bloqueado` no cuentan como aprobados.
- La evaluación clínica y las políticas de menores/seguros requieren contenido
  aprobado por el profesional; mientras falte, el bot se abstiene y deriva.
- No se probaron WhatsApp, Google Calendar ni una instalación Linux en esta
  entrega.
