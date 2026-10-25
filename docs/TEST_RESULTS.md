# Resultados de pruebas — Fase 2

Última ejecución: 2026-10-25T17:30:00Z
Entorno: Python 3.13.1, pytest 8.1.1, SQLite 3.45.3, `.venv-verify`
Base: SQLite temporal por prueba (nunca bases operativas)

## Resumen

| Suite | Tests | Pasados | Fallidos | Omitidos | Tiempo |
|---|---:|---:|---:|---:|---:|
| `tests/test_saas_phase1.py` | 11 | 11 | 0 | 0 | 5.52 s |
| `tests/test_saas_compliance.py` | 7 | 7 | 0 | 0 | 5.22 s |
| `tests/contract/test_api.py` | 27 | 27 | 0 | 0 | ~5 s |
| `tests/e2e_api/test_flow.py` | 1 | 1 | 0 | 0 | 0.61 s |
| **Total** | **37** | **37** | **0** | **0** | **6.36 s** |

Estado: **todo verde (37/37)**.

## Comando

```bash
make test
```

Equivalente:

```bash
.venv-verify/Scripts/python.exe -m pytest tests/test_saas_phase1.py tests/test_saas_compliance.py tests/contract tests/e2e_api -q -p no:cacheprovider --durations=5
```

## Cobertura

No se midió formalmente en esta entrega (no hay herramienta de cobertura instalada en el entorno de verificación). El umbral >= 80% de módulos críticos se exige y medirá en la Fase 8.

## Detalle de la suite de cumplimiento (`test_saas_compliance.py`)

| # | Prueba | Norma de referencia |
|---|---|---|
| 1 | Consentimiento registrado con texto exacto mostrado al usuario | GDPR / LGPD (base legal y transparencia) |
| 2 | Revocación de consentimiento actualiza `revoked_at` | GDPR (retirada del consentimiento) |
| 3 | Disclosure de IA registrado en la conversación | EU AI Act Art. 50 |
| 4 | Job de retención identifica mensajes con `data_retention_until` vencido | GDPR (limitación de la conservación) |
| 5 | Derecho al olvido: `right_to_be_forgotten_requested_at` y anonimización sin PII en claro | GDPR (derecho al olvido) |
| 6 | Aislamiento multi-tenant en tablas de compliance | Multi-tenant nativo |
| 7 | `audit_log` registra `tool_calls` con parámetros y resultado (LLM mockeado) | NIST AI RMF (trazabilidad de decisiones del LLM) |

Las IP y los user agents solo se almacenan con hash SHA-256.

## Detalle de la suite de contrato (`test_api.py`)

| Endpoint | Happy path | Error validación | Error auth/recurso ajeno |
|---|---|---|---|
| GET/PUT /api/tenants/me/identity | ✅ | ✅ (campos extra) | ✅ (401 sin API key) |
| CRUD /api/services | ✅ | ✅ (price_cents negativo, campo extra) | ✅ (aislamiento tenant B) |
| CRUD /api/resources + schedule | ✅ | ✅ | ✅ (aislamiento) |
| CRUD /api/schedule-exceptions | ✅ | ✅ | ✅ (FK recurso ajeno) |
| CRUD /api/faqs | ✅ | ✅ | ✅ (aislamiento) |
| PUT /api/policies/{key} | ✅ | ✅ | ✅ |
| POST /api/knowledge/reindex (selectivo) | ✅ | ✅ | ✅ |
| POST /api/knowledge/test (RAG simulado) | ✅ | ✅ (body vacío) | ✅ |
| POST /api/consent (create/revoke/list) | ✅ | ✅ (customer inexistente) | ✅ (aislamiento) |
| POST /api/conversations (+ ai_disclosures) | ✅ | ✅ | ✅ |
| POST /api/customers/{id}/forget-request | ✅ | ✅ | ✅ |
| POST /api/customers/{id}/forget-execute (idempotente) | ✅ | ✅ | ✅ (404 inexistente) |
| GET /api/data-retention?expired=true | ✅ | ✅ | ✅ |
| POST /api/data-retention/purge | ✅ | ✅ | ✅ |
| GET /api/audit-log (filtros, paginación) | ✅ | ✅ | ✅ |

## Suite E2E (`test_flow.py`)

Flujo completo verificado:
1. Tenant demo vía seed + API key
2. Identidad, 3 servicios (seed), 2 recursos, horario, 5 FAQs, políticas
3. Reindex solo `catalog` → FAQs/policies no reindexados
3. `/knowledge/test` con pregunta de FAQ → respuesta correcta
4. Consentimiento → revocación → solicitud olvido → ejecución → sin PII
5. `audit_log` ≥ 10 entradas con `tool_calls` (LLM mockeado)

## Migración de cumplimiento

`saas/migrations/0003_compliance.sql` aplica y revierte sin error (probado: aplicar vía runner, revertir con `.down.sql`, volver a aplicar en BD limpia).

## Migración de auth

`saas/migrations/0004_auth.sql`: tabla `api_keys` (hash SHA-256, rotación, expiración, `ON DELETE CASCADE` al tenant).

## Pendiente para Fase 8

- Medición formal de cobertura (módulos críticos: `booking_engine`, `guardrails`, `handoffs`).
- Pruebas de carga con 100 reservas concurrentes.
- Suite E2E Playwright.
- Exportación automática de este informe desde el runner.