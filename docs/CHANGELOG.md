# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
El formato se basa en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/).

## [1.0.0] - 2026-10-25 — Fase 1 (entrega inicial + corrección post-auditoría)

### Añadido

- Módulo `saas/` con esquema SQL multi-tenant: `tenants`, `resources`,
  `services`, `schedules`, `schedule_exceptions`, `faqs`, `policies`,
  `knowledge_documents`, `conversations`, `messages`, `bookings`,
  `handoff_alerts`, `audit_log`, `idempotency_keys`.
- Migraciones versionadas (`saas/migrations/`) con runner transaccional,
  checksum SHA-256 y `PRAGMA foreign_keys=ON`.
- Repositorio scopeado por tenant con claves foráneas compuestas
  `(tenant_id, id)` y reserva idempotente por clave.
- Seed idempotente del consultorio dental demo (`scripts/seed_demo_saas.py`).
- Pruebas de Fase 1: `tests/test_saas_phase1.py` (11 pruebas, todas en verde).

### Cambiado

- `docs/producto/PLAN.md`: declara el producto como MULTI-TENANT NATIVO y
  añade la sección "Modelo de despliegue" (resuelve DEC-000).
- `docs/DECISIONS.md`: DEC-000 marcada RESUELTA; DEC-001 a DEC-006 documentadas
  con formato Contexto / Decisión / Alternativas / Justificación / Condiciones
  (aprobadas por el Cerebro).
- `tests/test_saas_phase1.py`: versiones de migración esperadas actualizadas a
  `0001, 0002, 0003`; tablas de cumplimiento incluidas en la auditoría de
  índices `tenant_id`.

### Corregido

- Migración `0003_compliance.sql` (cumplimiento y gobernanza): tablas
  `customers`, `data_processing_records`, `consent_log`, `ai_disclosures`;
  columnas `messages.data_retention_until`, `messages.anonymized_at` y
  `audit_log.tool_calls`; índices para jobs de purga y DSAR. Incluye script de
  reversión `0003_compliance.down.sql`.
- `docs/DATA_MODEL.md`: sección "Cumplimiento y Gobernanza" con subsecciones
  por normativa (GDPR, CCPA/CPRA, LGPD, Perú DS 115-2025-PCM, Ecuador,
  NIST AI RMF).

### Pruebas añadidas

- `tests/test_saas_compliance.py`: 7 pruebas de gobernanza (consentimiento,
  revocación, disclosure de IA, retención, derecho al olvido sin PII en claro,
  aislamiento multi-tenant, `tool_calls` del LLM mockeado).

### Documentación

- `docs/REPORT.md`, `docs/TEST_RESULTS.json`, `docs/TEST_RESULTS.md`
  actualizados con 18 pruebas en verde.
- `Makefile` con objetivo `make test`.
