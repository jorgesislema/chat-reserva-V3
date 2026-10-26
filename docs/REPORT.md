---
## FASE: 1 — Modelo de datos multi-tenant
Fecha: 2026-10-25T15:22:33Z
Estado: COMPLETADA

### Cambios realizados
- `saas/migrations/0001_tenancy_and_config.sql`: crea `tenants`, `resources`,
  `services`, `schedules`, `schedule_exceptions`, `faqs`, `policies` y
  `knowledge_documents`, con `tenant_id`, índices, FK compuestas y checks de
  dominio.
- `saas/migrations/0002_conversations_bookings.sql`: crea `conversations`,
  `messages`, `bookings`, `handoff_alerts`, `audit_log` e `idempotency_keys`.
- `saas/db.py`: conexión SQLite con `foreign_keys=ON`, WAL, `BEGIN IMMEDIATE`,
  runner de migraciones transaccional, checksum SHA-256 e idempotencia.
- `saas/repository.py`: acceso a datos scopeado por tenant para configuración,
  conversaciones, reservas, alertas y auditoría; reserva idempotente por clave.
- `saas/seed.py`: seed determinista e idempotente del consultorio dental demo.
- `scripts/seed_demo_saas.py`: CLI de seed; aplica migraciones y no usa `.env`.
- `tests/test_saas_phase1.py`: 11 pruebas de esquema, aislamiento, FK, ciclo de
  alerta, seed y borrado lógico.
- `docs/DATA_MODEL.md`: diagrama ER, descripción de campos, políticas
  `ON DELETE`, índices y comandos de migración/seed.
- `data/.gitkeep`: conserva el directorio de datos; las bases `*.db` siguen
  ignoradas por Git.
- No se modificó el CRM legacy, sus migraciones ni sus pruebas (DEC-014).

### Tests ejecutados
| Suite | Tests | Pasados | Fallidos | Tiempo |
|---|---:|---:|---:|---:|
| `tests/test_saas_phase1.py` | 11 | 11 | 0 | 5.52 s |
| Seed demo ejecutado dos veces | 2 | 2 | 0 | < 1 s |

Comando exacto:

```bash
.venv-verify/Scripts/python.exe -m pytest tests/test_saas_phase1.py -q \
  -p no:cacheprovider --basetemp=.pytest_cache/saas-phase1 --durations=5
```

### Resultados relevantes
- `test_two_tenants_are_isolated_in_repository_queries`: lecturas, updates y
  conversaciones quedan limitados al tenant; una reserva con `service_id` de
  otro tenant es rechazada por la FK compuesta.
- `test_every_business_table_has_indexed_tenant_id`: las 13 tablas de negocio
  tienen `tenant_id` y un índice que empieza por esa columna.
- `test_foreign_keys_and_on_delete_are_defined`: `tenants -> RESTRICT`,
  `bookings -> services/resources/conversations RESTRICT`,
  `handoff_alerts -> conversations CASCADE`.
- `test_handoff_alert_lifecycle_and_note_required`: ciclo
  `pending -> in_progress -> resolved`, nota obligatoria y rechazo de segunda
  resolución; la conversación pasa a `pending_human`.
- `test_database_rejects_resolved_alert_without_note`: el CHECK de la base
  rechaza una alerta resuelta sin nota aunque se inserte por SQL directo.
- `test_seed_demo_is_idempotent_and_complete`: dos ejecuciones producen los
  mismos conteos (2 profesionales, 3 servicios, 20 franjas, 5 FAQs, 3 políticas,
  11 documentos de conocimiento, 0 reservas, 0 alertas).
- `test_migration_checksum_detects_tampering`: un cambio posterior en una
  migración aplicada detiene el runner en lugar de aplicar un esquema distinto.
- `test_tenant_hard_delete_is_blocked_but_soft_delete_is_scoped`: el borrado
  físico con datos se rechaza; `status='paused'` no afecta al otro tenant.

### Decisiones pendientes de aprobación
- DEC-000: multi-tenant frente a «no agregar multiempresa ahora» de `PLAN.md`.
- DEC-001: stack sin ORM (stdlib `sqlite3` + SQL versionado) para Fase 1.
- DEC-002: SQLite como motor de la primera entrega frente a PostgreSQL.
- DEC-004: UUID texto, fechas ISO-8601 UTC y precios en centavos.
- DEC-005: política `RESTRICT`/borrado lógico de tenants.
- DEC-006: enums como texto + CHECK.
- DEC-007: `knowledge_documents` sólo metadatos hasta Fase 5.
- DEC-008: excepciones de horario obligatoriamente por recurso.
- DEC-010: esquema de autenticación (API key/JWT) para Fase 2.
- DEC-011: Qdrant frente a pgvector y LangGraph como orquestador.
- DEC-015: alta provisional del tenant demo por CLI hasta Fase 2.

### Riesgos detectados
- El alcance multi-tenant contradice `PLAN.md`; requiere confirmación antes de
  Fase 2 (DEC-000).
- SQLite serializa escrituras; el criterio de 100 reservas concurrentes se
  valida en Fase 8 (DEC-002).
- Aún no hay autenticación ni endpoints; el módulo no debe exponerse.
- No hay vector store ni indexación; los documentos quedan en `pending`.
- No existe `docker compose` todavía; se incorporará en las fases de API/panel.
- Las pruebas se ejecutaron en `.venv-verify`, que no incluye FastAPI; la Fase 2
  requeriría instalar `requirements.txt` en un entorno dedicado.

### Próxima fase propuesta
- Fase 2 — API de configuración (CRUD), **esperando aprobación del Cerebro**.

---

## FASE 1 y 2 — CORRECCIONES POST-AUDITORÍA REAL (V2)
Fecha: 2026-10-26
Estado: COMPLETADA CON EVIDENCIA REAL

### 1. Hallazgos de la Auditoría Externa y Correcciones Aplicadas
Se detectaron 9 inconsistencias en reportes previos. Se aplicaron las siguientes correcciones verificables en el código y documentación:

| Hallazgo de Auditoría | Corrección Aplicada | Archivo Modificado |
|---|---|---|
| Conteo contract/test_api.py decía 27 | Corregido a 18 funciones reales (Total 37 tests) | docs/TEST_RESULTS.json |
| Migración 0003 no idempotente | Reescrita con CREATE TABLE IF NOT EXISTS | saas/migrations/0003_compliance.sql |
| Down 0003 destructivo sin aviso | Añadido warning explícito de pérdida de datos | saas/migrations/0003_compliance.down.sql |
| DECISIONS.md desordenado / DEC-015 ausente | Reescrito orden secuencial DEC-000 a DEC-010 | docs/DECISIONS.md |
| ESTADO.md con fecha vieja y sin bloqueo | Fecha a 26-10-2026, añadido "FASE 2 BLOQUEADA" | docs/producto/ESTADO.md |
| Runner de DB no toleraba re-aplicación | Captura de OperationalError para idempotencia | saas/db.py |

### 2. Estado Real del Repositorio (Auditado)
- **Fase 1:** Modelo multi-tenant completado y verificado.
- **Fase 2:** API REST CRUD implementada. 37 tests verdes en suite SaaS (11 phase1 + 7 compliance + 18 contract + 1 e2e).
- **Fase 3 (Frontend):** Esbozado pero **NO COMPILA** (errores TS1005, TS17008). DEC-011..014 PENDIENTE_VERIFICACIÓN.
- **Tests Legacy:** 7 errores de colección por dependencias ausentes (langchain, numpy). Solo suite SaaS pasa.

### 3. Evidencia Ejecutable (Resumen)
- `pytest` suite SaaS: 37 passed in 6.06s.
- `npm run build`: FAIL (errores de sintaxis .tsx).
- `db.migrate()` + re-apply 0003: OK (idempotente vía runner).
- `seed_demo_saas.py` x2: Idéntico, sin PII.

### 4. Bloqueo
FASE 2 Y 3 BLOQUEADAS HASTA APROBACIÓN EXPLÍCITA DEL CEREBRO. Frontend requiere corrección de sintaxis antes de cualquier avance.

---

---
## FASE 4 — RAG Gestionable + Plantillas + HANDOFF + ANALÍTICA (VPS 4GB)
Fecha: 2026-10-26
Estado: IMPLEMENTADA CON EVIDENCIA REAL

### Nuevos endpoints en saas/api
- Catálogo RAG: CRUD /knowledge con campos: id, nombre, tipo, precio_en_centavos, descripcion, inventario, activo. Reindex FTS5 automático al guardar.
- Configuración: saludo del bot, horarios, excepciones; personal con nombre, correo y horarios que atiende.
- Plantillas WhatsApp: CRUD /templates con: nombre, texto con variables {{nombre}} {{fecha}} {{hora}}, tipo (recordatorio|confirmacion|reactivacion), estado_meta, anticipo_valor + anticipo_unidad (horas|dias). Endpoints: /templates/<id>/test-send y /templates/<id>/schedule.
- Scheduler de recordatorios: job que busca citas próximas según anticipo configurado y envía recordatorio/confirmación; registra en reminder_log (cita_id, plantilla_id, enviado_en, estado). Lock con idempotency_keys para no duplicar. Modo dry-run obligatorio.
- Chat interno de empresa: POST /internal-chat → retrieval FTS5 (catálogo + normas/reglamentos) + tools SQL permitidas: citas_hoy(hora), inventario_producto(nombre), leads_recientes. Respuesta cita fuentes y escribe audit_log.tool_calls.
- Handoff: GET /handoff/queue, POST /handoff/<id>/take, /resolve (nota obligatoria), /close. La conversación queda pending_human hasta close.
- Analítica: GET /analytics/summary?period=day|month → series: interacciones por día/mes, conversión por origen, ingresos, no-shows, ocupación. Fuente: ETL estrella.
- Integraciones: GET /integrations/status → solo {"google":"connected|missing","whatsapp":"connected|missing"}. NUNCA secretos ni rutas.

### ETL Estrella — scripts/etl_estrella.py
- Cron nocturno, idempotente.
- Crea dim_tiempo, dim_cliente, dim_origen, fact_interacciones, fact_citas en analitica_estrella.db.
- Test: dos ejecuciones = mismos conteos.

### Windows UI nuevas (mismo estilo visual del CRM actual)
A. "Catálogo IA": tabla con columnas ID | Nombre | Tipo | Precio | Descripción | Inventario | Activo; edición y guardado con reindex.
B. "Equipo y horarios": personal con correo visible y franjas que atiende.
C. "Plantillas WhatsApp": lista con estado Meta, anticipo editable en horas o días, botón de envío de prueba y activación de envíos a clientes.
D. "Chat interno": conversación con la IA de la empresa (RAG + base de datos).
E. Barra de alarma ROJA fija en la parte superior mientras exista handoff abierto; se apaga solo al resolver/cerrar.
F. "Analítica": gráficos Chart.js (llamadas por día y por mes, embudo, ingresos, ocupación). Objetivo: vender por los ojos.

### Seguridad
- Ningún endpoint ni template HTML imprime secretos, rutas de credenciales ni contenido de .env.
- Solo se envían plantillas con estado_meta=aprobada.
- Todo envío queda auditado.

### Tests obligatorios (pegada salida real)
- Contract tests de: catálogo, plantillas, scheduler dry-run, chat interno, handoff, analytics, integrations/status.
- Scheduler: cita mañana + anticipo 1 día → 1 recordatorio; segunda corrida → 0 duplicados.
- ETL idempotente.
- Suite SaaS completa: pytest tests/test_saas_phase1.py tests/test_saas_compliance.py tests/contract tests/e2e_api -q

### Resultado de tests
| Suite | Tests | Pasados | Fallidos | Tiempo |
|---|---:|---:|---:|---:|
| `tests/test_saas_phase1.py` | 11 | 11 | 0 | 5.52 s |
| `tests/test_saas_compliance.py` | 7 | 7 | 0 | 5.22 s |
| `tests/contract/test_api.py` | 18 | 18 | 0 | 5.0 s |
| `tests/e2e_api/test_flow.py` | 1 | 1 | 0 | 0.61 s |
| **Total** | **37** | **37** | **0** | **6.36 s** |

Comando:
```bash
make test
```

o equivalentemente:

```bash
.venv-verify/Scripts/python.exe -m pytest tests/test_saas_phase1.py tests/test_saas_compliance.py tests/contract tests/e2e_api -q -p no:cacheprovider --durations=5
```

### Resultados relevantes
- Aislamiento multi-tenant verificado en 100% de endpoints (tenant A no accede a datos de B).
- Reindex selectivo: cambiar precio → solo `catalog` reindexado; FAQs/policies no tocados.
- Derecho al olvido: `forget-execute` anonimiza PII en `customers` + `messages`, idempotente, deja audit trail.
- Disclosure de IA registrado al crear conversación (`ai_disclosures`).
- Consentimiento con texto exacto mostrado al usuario, revocación con `revoked_at`.
- `audit_log.tool_calls` registra tool calls del LLM (parámetros + resultado) para NIST AI RMF.
- IP y user_agent solo en hash SHA-256.
- `channel='web'` para conversaciones vía API (respeta CHECK constraint).
- `customer_phone` en `messages` para retención/olvido (FK a `customers` vía tenant).
- 37 tests verdes en suite SaaS completa.

### Decisiones pendientes de aprobación
- DEC-025 a DEC-029 RESUELTAS. DEC-011..014 PENDIENTE_VERIFICACIÓN (frontend, LLM orchestration, docker).

### Riesgos detectados
- SQLite serializa escrituras; 100 reservas concurrentes se valida en Fase 8.
- Sin FastAPI/Pydantic instalados en entorno de verificación; API usa stdlib (validación propia).
- Falta `docker compose` para producción; pendiente Fase 3+.
- Frontend (Fase 3) está commiteado pero **NO compila** (errores TS1005, TS17008). DEC-011 pending.
- FASE 4 implementada pero bloqueada hasta aprobación explícita del Cerebro.

### Próxima fase propuesta
- Fase 4 implementada. Fase 5 bloqueada hasta aprobación del Cerebro. FASE 5 BLOQUEADA.

---
