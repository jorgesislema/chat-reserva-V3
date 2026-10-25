# Resultados de pruebas — Fase 1

Última ejecución: 2026-10-25T15:22:33Z
Entorno: Python 3.13.1, pytest 8.1.1, SQLite 3.45.3, `.venv-verify`
Base: SQLite temporal por prueba (nunca bases operativas)

## Resumen

| Suite | Tests | Pasados | Fallidos | Omitidos | Tiempo |
|---|---:|---:|---:|---:|---:|
| `tests/test_saas_phase1.py` | 11 | 11 | 0 | 0 | 5.52 s |

Estado: **todo verde**.

## Comando

```bash
.venv-verify/Scripts/python.exe -m pytest tests/test_saas_phase1.py -q \
  -p no:cacheprovider --basetemp=.pytest_cache/saas-phase1 --durations=5
```

Salida:

```text
...........                                                              [100%]
11 passed in 5.52s
```

## Cobertura funcional de la Fase 1

| Criterio del prompt | Prueba |
|---|---|
| Todas las tablas de negocio tienen `tenant_id` con índice | `test_every_business_table_has_indexed_tenant_id` |
| FKs correctas y `ON DELETE` definido | `test_foreign_keys_and_on_delete_are_defined`, `test_conversation_delete_cascades_its_messages_and_alerts` |
| Crear 2 tenants y verificar aislamiento | `test_two_tenants_are_isolated_in_repository_queries`, `test_cross_tenant_conversation_reference_is_rejected` |
| Migraciones versionadas e idempotentes | `test_migrations_are_versioned_and_idempotent` |
| Detección de migración alterada | `test_migration_checksum_detects_tampering` |
| Seed demo idempotente | `test_seed_demo_is_idempotent_and_complete` |
| Nota obligatoria al resolver handoff | `test_handoff_alert_lifecycle_and_note_required`, `test_database_rejects_resolved_alert_without_note` |
| Borrado físico bloqueado / borrado lógico | `test_tenant_hard_delete_is_blocked_but_soft_delete_is_scoped` |

## Seed demo

Ejecutado dos veces sobre `.pytest_cache/saas-seed/demo.db`:

```json
{
  "resources": 2,
  "services": 3,
  "schedules": 20,
  "schedule_exceptions": 2,
  "faqs": 5,
  "policies": 3,
  "knowledge_documents": 11,
  "bookings": 0,
  "handoff_alerts": 0,
  "tenant_slug": "demo-dental"
}
```

Los conteos no cambian entre ejecuciones.

## Pendiente para la Fase 8

- Medición formal de cobertura (módulos críticos: `booking_engine`,
  `guardrails`, `handoffs`).
- Pruebas de carga con 100 reservas concurrentes.
- Suite E2E Playwright.
- Exportación automática de este informe desde el runner.
