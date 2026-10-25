# Resultados de pruebas — Fase 1 (corregida post-auditoría)

Última ejecución: 2026-10-25T15:53:59Z
Entorno: Python 3.13.1, pytest 8.1.1, SQLite 3.45.3, `.venv-verify`
Base: SQLite temporal por prueba (nunca bases operativas)

## Resumen

| Suite | Tests | Pasados | Fallidos | Omitidos | Tiempo |
|---|---:|---:|---:|---:|---:|
| `tests/test_saas_phase1.py` | 11 | 11 | 0 | 0 | 5.52 s |
| `tests/test_saas_compliance.py` | 7 | 7 | 0 | 0 | 5.22 s |
| **Total** | **18** | **18** | **0** | **0** | **~10.7 s** |

Estado: **todo verde (18/18)**.

## Comando

```bash
make test
```

Equivalente:

```bash
.venv-verify/Scripts/python.exe -m pytest tests/test_saas_phase1.py tests/test_saas_compliance.py -q -p no:cacheprovider --durations=5
```

## Cobertura

No se midió formalmente en esta entrega (no hay herramienta de cobertura
instalada en el entorno de verificación). El umbral >= 80% sobre módulos
críticos (`booking_engine`, `guardrails`, `handoffs` y ahora tablas de
cumplimiento) se medirá en la Fase 8.

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

## Migración de cumplimiento

`saas/migrations/0003_compliance.sql` aplica y revierte sin error (probado:
aplicar vía runner, revertir con `0003_compliance.down.sql`, volver a aplicar
en base limpia).
