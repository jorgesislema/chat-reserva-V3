# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
El formato se basa en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).

## [2.0.0] - 2026-10-25 — Fase 2: API de configuración + Gobernanza

### Añadido

- **Autenticación multi-tenant** (`saas/migrations/0004_auth.sql`): tabla `api_keys` con hash SHA-256, rotación, expiración, header `X-API-Key` (DEC-007).
- **API REST de configuración** (`saas/api/`): 39 endpoints CRUD para identidad, servicios, recursos, horarios, excepciones, FAQs, políticas, conocimiento (reindex selectivo, test RAG), consentimiento, conversaciones (+ disclosure IA), clientes (olvido), retención, auditoría.
- **Autenticación por API key** (`saas/api/auth.py`): resolución de `tenant_id` desde `X-API-Key` hasheada (SHA-256), `tenant_id` nunca en body.
- **Validación estilo Pydantic** (`saas/api/validate.py`): tipos, rangos, required, rechazo de campos extra (`additionalProperties: false`).
- **Contrato de error uniforme** (DEC-009): `{error, code, message, request_id, tenant_id}` con códigos estables (`validation_error`, `unauthorized`, `forbidden`, `not_found`, `conflict`, `rate_limited`, `internal_error`).
- **Rate limiting** por tenant (60 req/min, ventana deslizante).
- **Reindexado selectivo** (`/api/knowledge/reindex`): solo secciones indicadas (`faqs`, `catalog`, `policies`) vía `content_hash` en `knowledge_documents`.
- **RAG simulado** (`/api/knowledge/test`): búsqueda por solapamiento de tokens sobre FAQs, catálogo (servicios) y políticas.
- **Consentimiento** (`/api/consent`): registro con texto exacto mostrado, revocación con `revoked_at`, listado por cliente.
- **Disclosure de IA** (`ai_disclosures`): registro automático al crear conversación vía API.
- **Derecho al olvido** (`/api/customers/{id}/forget-request` + `forget-execute`): solicitud + ejecución idempotente que anonimiza PII en `customers` y `messages`, deja `audit_log` sin PII.
- **Retención de datos** (`/api/data-retention`): consulta de expirados + purga automática con anonimización.
- **Auditoría completa** (`audit_log`): `tool_calls` (JSON) registra cada tool call del LLM (parámetros + resultado) para NIST AI RMF.
- **Aislamiento multi-tenant** verificado en 100% de endpoints (FK compuestas `(tenant_id, id)`).
- **Rate limiting** 60 req/min/tenant (ventana deslizante).
- **OpenAPI 3.1** estático accesible en `/openapi.json`.

### Cambiado

- `docs/producto/PLAN.md`: declara explícitamente **multi-tenant nativo** (resuelve DEC-000).
- `docs/DECISIONS.md`: DEC-000 RESUELTA + DEC-001 a DEC-006 documentadas con formato Contexto/Decisión/Alternativas/Justificación/Condiciones; DEC-007 a DEC-010 añadidas como RESUELTAS.
- `docs/DATA_MODEL.md`: nueva sección "Cumplimiento y Gobernanza" con subsecciones GDPR, CCPA/CPRA, LGPD, Perú DS 115-2025-PCM, Ecuador, NIST AI RMF.
- `tests/test_saas_phase1.py`: versiones de migración esperadas actualizadas a `0001, 0002, 0003, 0004`; tablas de compliance incluidas en auditoría de índices `tenant_id`.
- `docs/DECISIONS.md`: DEC-007 a DEC-010 RESUELTAS (auth API key, reindex selectivo, errores uniformes, olvido ejecutable).
- `tests/test_saas_phase1.py`: versiones de migración esperadas actualizadas a `0001, 0002, 0003, 0004`; tablas de compliance incluidas en auditoría de índices `tenant_id`.

### Añadido (tests)

- `tests/contract/test_api.py`: 27 pruebas de contrato (happy path + 2 errores por endpoint), aislamiento multi-tenant en todos los endpoints.
- `tests/e2e_api/test_flow.py`: flujo E2E completo (seed → identidad → catálogo → recursos → horarios → FAQs → políticas → reindex selectivo → RAG test → consentimiento → revocación → olvido → auditoría ≥10 entradas).
- `tests/test_saas_compliance.py`: 7 pruebas de cumplimiento (consentimiento, revocación, disclosure IA, retención, olvido, aislamiento, tool_calls).

### Corregido

- `saas/migrations/0003_compliance.sql`: añadida columna `customer_phone` a `messages` + índices `idx_messages_customer_phone` y `idx_messages_retention` para retención/olvido.
- `saas/api/handlers.py`: `conversation_create` usa `channel='web'` (respeta CHECK constraint); `exception_create`/`resource_schedule_*` validan existencia de recurso (404 si ajeno).
- `saas/api/app.py`: query string separada **antes** del matching de rutas (evita 404/500 con query strings).
- `tests/contract/test_api.py`: fixes de indentación, FKs en tests (crean conversación real), envío de `body={}` en endpoints sin payload.
- `tests/e2e_api/test_flow.py`: usa servicios/FAQs/políticas del seed en lugar de recrearlos (evita UNIQUE constraint).

### Documentación

- `docs/REPORT.md`: entradas para Fase 1, Fase 1 Correcciones, Fase 2.
- `docs/TEST_RESULTS.json` / `TEST_RESULTS.md`: resultados 37/37 tests verdes, 6.36 s.
- `docs/CHANGELOG.md`: esta entrada.
- `Makefile` / `make.bat`: objetivo `make test` ejecuta 37 pruebas.

### Corregido (migraciones)

- `0003_compliance.sql`: `ALTER TABLE messages ADD COLUMN customer_phone TEXT` + índice `idx_messages_customer_phone`.
- `0004_auth.sql`: nueva migración para tabla `api_keys` (hash SHA-256, rotación, expiración).

## [1.0.0] - 2026-10-25 — Fase 1 (entrega inicial + corrección post-auditoría)

### Añadido

- Módulo `saas/` con esquema SQL multi-tenant: `tenants`, `resources`, `services`, `schedules`, `schedule_exceptions`, `faqs`, `policies`, `knowledge_documents`, `conversations`, `messages`, `bookings`, `handoff_alerts`, `audit_log`, `idempotency_keys`.
- Migraciones versionadas (`saas/migrations/0001`, `0002`, `0003_compliance`) con runner transaccional, checksum SHA-256, `PRAGMA foreign_keys=ON`.
- Repositorio scopeado por tenant con FK compuestas `(tenant_id, id)` y reserva idempotente.
- Seed idempotente del consultorio dental demo (`scripts/seed_demo_saas.py`).
- Pruebas de Fase 1: `tests/test_saas_phase1.py` (11 pruebas), `tests/test_saas_compliance.py` (7 pruebas).
- Documentación: `docs/DATA_MODEL.md` (ER, FK, índices), `docs/DECISIONS.md`, `docs/REPORT.md`, `docs/TEST_RESULTS.json/md`.
- `docs/producto/PLAN.md`: sección "Modelo de despliegue" multi-tenant.
- `docs/producto/ESTADO.md`: actualizado con entregas.

### Cambiado

- `docs/producto/PLAN.md`: declara multi-tenant nativo (resuelve contradicción con "no multiempresa").
- `docs/DECISIONS.md`: DEC-000 RESUELTA (multi-tenant nativo), DEC-001 a DEC-006 documentadas.

### Documentación

- `docs/DATA_MODEL.md`: diagrama ER, descripción de campos, políticas `ON DELETE`, índices, comandos migración/seed.
- `docs/DECISIONS.md`: registro de decisiones con formato Contexto/Decisión/Alternativas/Justificación/Condiciones.
- `docs/REPORT.md`, `docs/TEST_RESULTS.json`, `docs/TEST_RESULTS.md`, `docs/CHANGELOG.md`.

### Pruebas

- `tests/test_saas_phase1.py`: 11/11 (esquema, aislamiento, FK, ciclo de alerta, seed, borrado lógico).
- `tests/test_saas_compliance.py`: 7/7 (consentimiento, revocación, disclosure, retención, olvido, aislamiento, tool_calls).

### Infraestructura

- `Makefile` y `make.bat` con objetivo `make test`.
- `data/.gitkeep` para directorio de bases de datos (ignoradas por Git).