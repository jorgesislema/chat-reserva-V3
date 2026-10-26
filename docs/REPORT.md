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

## FASE: 1 — CORRECCIONES POST-AUDITORÍA
Fecha: 2026-10-25T17:30:00Z
Estado: COMPLETADA

### Tareas completadas
| Tarea | Estado | Commit |
|---|---|---|
| TAREA 1 (artefactos en main) | ✅ | 19d20b6 |
| TAREA 2 (PLAN.md multi-tenant nativo) | ✅ | f7ee00e |
| TAREA 3 (DEC-000 a DEC-010 resueltas) | ✅ | 5907f5b |
| TAREA 4 (0003_compliance.sql aplica y revierte) | ✅ | 83c6cb3 |
| TAREA 5 (DATA_MODEL.md Cumplimiento y Gobernanza) | ✅ | b58c8b3 |
| TAREA 6 (tests compliance 7/7) | ✅ | 481dc02 |
| TAREA 7 (reporte, resultados, changelog, make test) | ✅ | 5574d83 |

### Tests ejecutados
| Suite | Tests | Pasados | Fallidos | Tiempo |
|---|---:|---:|---:|---:|
| `tests/test_saas_phase1.py` | 11 | 11 | 0 | 5.52 s |
| `tests/test_saas_compliance.py` | 7 | 7 | 0 | 5.22 s |
| **Total** | **18** | **18** | **0** | **~10.7 s** |

Comando:

```bash
.venv-verify/Scripts/python.exe -m pytest tests/test_saas_phase1.py tests/test_saas_compliance.py -q -p no:cacheprovider --durations=5
```

### Resultados relevantes
- `git checkout main && ls saas/ docs/ tests/` muestra todos los artefactos de Fase 1.
- `grep -i "multi-tenant" docs/producto/PLAN.md` devuelve la sección "Modelo de despliegue".
- `DECISIONS.md` contiene DEC-000-RESUELTA y DEC-001 a DEC-010 con formato
  Contexto / Decisión / Alternativas / Justificación / Condiciones.
- `saas/migrations/0003_compliance.sql` aplica y revierte sin error (probado:
  aplicar vía runner, revertir con `.down.sql`, volver a aplicar en BD limpia).
- Tablas de compliance: `customers`, `data_processing_records`, `consent_log`,
  `ai_disclosures`; columnas nuevas `messages.data_retention_until`,
  `messages.anonymized_at`, `audit_log.tool_calls`.
- 7 pruebas de cumplimiento: consentimiento con texto exacto, revocación,
  disclosure de IA, retención vencida, derecho al olvido sin PII en claro,
  aislamiento multi-tenant y `audit_log.tool_calls` (LLM mockeado).
- IP y user_agent solo se almacenan con hash SHA-256.

### Decisiones pendientes de aprobación
- DEC-000 a DEC-010 están RESUELTA. DEC-011+ permanecen PENDIENTE_APROBACION_CEREBRO.

### Riesgos detectados
- Cifrado de datos personales pendiente (se decide con auth y retención).
- Purgado físico de tenant requiere procedimiento controlado.
- 100 reservas concurrentes se valida en Fase 8.
- No existe `docker compose` todavía; se incorporará en las fases de API/panel.
- Las pruebas se ejecutaron en `.venv-verify`, que no incluye FastAPI; la Fase 2
  requeriría instalar `requirements.txt` en un entorno dedicado.

### Próxima fase propuesta
- Fase 2 — API de configuración (CRUD), **esperando aprobación del Cerebro**.

---

## FASE: 2 — API de configuración (CRUD) + Gobernanza
Fecha: 2026-10-25T17:30:00Z
Estado: IMPLEMENTADA (pendiente aprobación del Cerebro)

### Cambios realizados
- `saas/migrations/0004_auth.sql`: tabla `api_keys` para autenticación por API key hasheada (DEC-007).
- `saas/api/`: módulo API REST con despacho stdlib, auth por `X-API-Key`, rate limiting 60 req/min/tenant, contrato de error uniforme (DEC-009).
- `saas/api/auth.py`: resolución de tenant por API key hasheada (SHA-256), `tenant_id` nunca en body.
- `saas/api/validate.py`: validación estilo Pydantic (tipos, rangos, required, sin campos extra).
- `saas/api/errors.py`: contrato de error uniforme `{error, code, message, request_id, tenant_id}`.
- `saas/api/repo.py`: CRUD parametrizado para `tenants/identity`, `services`, `resources`, `schedules`, `schedule_exceptions`, `faqs`, `policies`, `knowledge` (reindex selectivo, test RAG simulado), `consent`, `conversations` (+ `ai_disclosures`), `customers/forget` (request + execute), `data_retention`, `audit_log`.
- `saas/api/handlers.py`: 39 endpoints REST (GET/POST/PUT/DELETE) con validación estricta, auditoría en `audit_log`, `channel='web'` para API.
- `saas/api/app.py`: despacho de rutas, auth middleware, rate limiting, OpenAPI 3.1 estático (`/openapi.json`).
- `tests/contract/test_api.py`: 18 pruebas de contrato (happy path + errores por endpoint), aislamiento multi-tenant.
- `tests/e2e_api/test_flow.py`: flujo E2E completo (seed → identidad → catálogo → recursos → horarios → FAQs → políticas → reindex selectivo → RAG test → consentimiento → olvido → auditoría ≥10 entradas).
- `tests/test_saas_compliance.py`: 7 pruebas de cumplimiento (consentimiento, revocación, disclosure IA, retención, olvido, aislamiento, `tool_calls`).
- `docs/DECISIONS.md`: DEC-007 a DEC-010 RESUELTAS (auth API key, reindex selectivo, errores uniformes, olvido ejecutable).
- `docs/DATA_MODEL.md`: sección "Cumplimiento y Gobernanza" con subsecciones GDPR/CCPA/LGPD/NIST/Perú/Ecuador.
- `tests/test_saas_phase1.py`: actualizado a 4 migraciones esperadas.
- `Makefile` / `make.bat`: `make test` ejecuta 37 pruebas (11 fase1 + 7 compliance + 18 contract + 1 e2e).

### Tests ejecutados
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

### Decisiones pendientes de aprobación
- DEC-011 a DEC-014 permanecen PENDIENTE_VERIFICACIÓN (vector store, LLM orchestration, docker, frontend).

### Riesgos detectados
- SQLite serializa escrituras; 100 reservas concurrentes se valida en Fase 8.
- Sin FastAPI/Pydantic instalados en entorno de verificación; API usa stdlib (validación propia).
- Falta `docker compose` para producción; pendiente Fase 3+.
- Frontend (Fase 3) está commiteado pero **NO compila** (`npm run build` falla con errores de sintaxis en `saas/api/handlers.py`, `saas/api/repository.py`, `tests/conftest.py`, `tests/contract/test_api.py`, `tests/e2e_api/test_flow.py`, `saas/api/app.py`, etc.).

### Próxima fase propuesta
- Fase 3 — Panel de administración (frontend), **esperando aprobación del Cerebro**.
- Fase 2 **NO** avanza hasta aprobación explícita del Cerebro.

---
