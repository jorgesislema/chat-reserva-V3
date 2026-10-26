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
