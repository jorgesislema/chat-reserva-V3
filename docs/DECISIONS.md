# Registro de decisiones — SaaS de reservas multi-tenant

Fecha de apertura: 2026-10-25
Implementador: Nemotron (DeepSeek)
Auditor: el Cerebro

Estados usados:

- **ACEPTADA**: decisión fijada por el prompt de la entrega o por el Cerebro.
- **PENDIENTE_APROBACION_CEREBRO**: decisión tomada para poder avanzar, pero
  sujeta a revisión antes de continuar a la Fase 2.
- **RESUELTA**: decisión revisada y aprobada por el Cerebro (post-auditoría
  Fase 1).
- **PROPUESTA**: alternativa registrada, todavía no implementada.

> Regla: ninguna decisión marcada como pendiente se considera cerrada. Si el
> Cerebro la rechaza, se corrige antes de iniciar la fase siguiente.

---

## DEC-000-RESUELTA — Modelo multi-tenant nativo (corrige PLAN.md)

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto.** El Cerebro detectó en la auditoría de Fase 1 una contradicción:
el mandato del producto exige multi-tenant desde el día 1, pero
`docs/producto/PLAN.md` declaraba «Una base privada por instalación... No agregar
multiempresa ahora». Esa contradicción impedía verificar el alcance en el
repositorio.

**Decisión.** El producto es MULTI-TENANT NATIVO: cada negocio es un tenant
aislado con la columna `tenant_id` en toda tabla de negocio. No hay instalaciones
ni bases de datos separadas por cliente.

**Justificación.** Un SaaS de ~100 USD/mes requiere escala horizontal: un solo
despliegue atiende a N tenants, con aislamiento lógico por `tenant_id` y
filtrado a nivel de fila en todas las consultas de negocio.

**Alternativas rechazadas.**

- Instalación física separada por cliente: no escala al modelo de precio y
  multiplica el coste de operación (backup, monitoreo, actualizaciones).
- Subdominio o esquema por tenant: complejidad innecesaria para el MVP;
  el aislamiento por columna con FK compuestas ya garantiza la separación.

**Evidencia.** `PLAN.md` incluye ahora la sección «Modelo de despliegue» que
declara explícitamente el multi-tenant nativo.

---

## DEC-001-RESUELTA — SQLite para dev y MVP, con capa de repositorio abstraída

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto.** Fase 1 necesita esquema, migraciones, seed y pruebas sin añadir
dependencias pesadas. El producto de 100 USD/mes no puede costear un
PostgreSQL gestionado + backup + monitoreo desde el día 1.

**Decisión.** SQLite como motor de la primera entrega, con una capa de
repositorio (`saas/repository.py`) que abstrae el acceso a datos, de modo que
migrar a PostgreSQL no reescribe la lógica de negocio.

**Alternativas.**

1. SQLAlchemy 2 + Alembic + PostgreSQL desde el inicio (descartada: añade
   dependencias y operación de base de datos gestionada en día 1).
2. SQLAlchemy 2 + Alembic + SQLite (descartada: ORM innecesario para el alcance
   de Fase 1).
3. `sqlite3` de la biblioteca estándar + migraciones SQL versionadas + runner
   transaccional propio (elegida).

**Justificación.** Menor latencia, control total de las transacciones
(`BEGIN IMMEDIATE`), menos dependencias y reutiliza el patrón ya probado en
`crm/store.py`.

**Condiciones (obligatorias).**

- Todas las queries deben ser parametrizadas (prevención de inyección SQL).
- Pruebas de integración contra base de datos real (SQLite temporal por prueba).
- El runner de migraciones es transacional y verifica checksum SHA-256.

---

## DEC-002-RESUELTA — Sin ORM: SQL directo con runner transaccional

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto.** Se necesita control total sobre el esquema y las transacciones
para el motor de reservas y el aislamiento multi-tenant.

**Decisión.** Acceso a datos con SQL directo y runner de migraciones propio
(`saas/db.py`), sin ORM.

**Alternativas.**

1. SQLAlchemy 2 (descartada: capa extra, dependencia pesada y posible ocultación
   del comportamiento transaccional).
2. Micro-ORM tipo peewee (descartada: otra dependencia sin beneficio claro).

**Justificación.** Menor latencia, control total de `BEGIN IMMEDIATE` para
evitar doble-booking, y menos dependencias en el entorno de verificación.

**Condiciones (obligatorias).**

- Queries parametrizadas en todo el reposatorio (prevención de inyección SQL).
- Tests de integración contra DB real, no solo mocks.
- Migraciones versionadas, idempotentes y con checksum para detectar manipulación.

---

## DEC-003-RESUELTA — Identificadores, fechas y dinero

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto.** Evitar errores de zona horaria y de punto flotante en un producto
que maneja citas y precios.

**Decisión.**

- IDs: UUIDv4 en texto (36 caracteres), portable entre SQLite y PostgreSQL.
- Fechas/horas: texto ISO-8601 UTC con sufijo `Z` (ej. `2026-10-25T09:00:00.000Z`).
- Dinero: entero en centavos (`price_cents`) más moneda ISO-4217 de 3 letras.

**Alternativa descartada.** `DATETIME` nativo de SQLite (no conserva zona de forma
fiable) y `REAL` para precios (errores de redondeo).

**Justificación.** Evita errores de zona horaria y de punto flotante en citas y
precios.

**Condiciones (obligatorias).**

- Toda columna de dinero es `INTEGER` (centavos); nunca `REAL`/`FLOAT`.
- Toda columna de fecha/hora es `TEXT` en ISO 8601 UTC con sufijo `Z`.

---

## DEC-004-RESUELTA — Autenticación por JWT o API key por tenant

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto.** Fase 2 requiere auth por tenant. Gama baja: simplicidad, sin
OAuth2 complejo.

**Decisión.** API key por tenant o JWT de corta duración. Mecanismo elegido y
documentado antes de exponer endpoints.

**Alternativas.**

1. API key por tenant con hash almacenado en base (elegida para integraciones).
2. JWT firmado con secreto por instalación, expiración corta y refresh token
   (elegida para el panel web).
3. OAuth2 completo (descartado: complejidad innecesaria para MVP).

**Justificación.** Gama baja, simplicidad operativa y suficiente para el alcance
inicial.

**Condiciones (obligatorias).**

- Documentar el mecanismo elegido y por qué es adecuado.
- Si API key: rotación programada y almacenamiento hasheado (nunca en claro).
- Si JWT: expiración corta y mecanismo de refresh.
- `tenant_id` viaja en el token/key; se valida en cada request.

---

## DEC-005-RESUELTA — pgvector como vector DB (no Qdrant)

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto.** Fase 5 necesita almacenamiento vectorial para RAG. El producto de
100 USD/mes no puede mantener un servicio vectorial adicional.

**Decisión.** pgvector como vector store, no Qdrant. Reduce la huella de
infraestructura a un solo servicio (PostgreSQL).

**Alternativas.**

1. Qdrant local en Docker (descartada: servicio adicional que operar y
   monitorear).
2. pgvector sobre PostgreSQL (elegida: un solo servicio, copia de seguridad
   unificada).

**Justificación.** Crítico para el modelo de 100 USD/mes: menos infraestructura
que operar, backup unificado y menor coste mensual.

**Condiciones (obligatorias).**

- La interfaz de retrieval debe ser abstracta para poder migrar a Qdrant sin
  cambiar la lógica de negocio.
- `tenant_id` como filtro obligatorio en toda consulta vectorial (aislamiento).

---

## DEC-006-RESUELTA — Política RESTRICT en claves foráneas

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto.** Evitar borrados en cascada accidentales que destruyan datos de
negocio (reservas, historial de mensajes, auditoría).

**Decisión.** `ON DELETE RESTRICT` en las claves foráneas entre tablas de
negocio. Los `tenant_id -> tenants(id)` también son `RESTRICT`: el borrado de un
tenant es lógico (`status = 'deleted'` o `'paused'`), nunca físico mientras haya
datos asociados.

**Alternativas.**

1. `CASCADE` masivo desde tenants (descartado: puede borrar historial de forma
   silenciosa y el orden de cascada en SQLite no está garantizado con
   `RESTRICT` intermedio).
2. `RESTRICT` en todas las FK (elegida).

**Justificación.** Preserva reservas, mensajes, alertas de handoff y auditoría;
el borrado lógico permite reactivar o purgar de forma controlada.

**Condiciones (obligatorias).**

- Borrado lógico (soft delete) para entidades con historial.
- Procedimiento de purgado físico documentado y por tabla cuando se requiera.

---

## DEC-007-RESUELTA — Mecanismo de auth: API key hasheada en cabecera X-API-Key

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto.** Fase 2 requiere autenticación por tenant. DEC-004 dejaba abierta
JWT vs API key.

**Decisión.** API key por tenant, almacenada hasheada (SHA-256) en tabla
`api_keys`, enviada en cabecera `X-API-Key`. Cada request resuelve `tenant_id`
desde la key; el `tenant_id` nunca se acepta del cuerpo de la petición.

**Alternativas.**

1. JWT con expiración corta + refresh y claim `tenant_id` (descartado para el
   MVP: añade complejidad de gestión de secretos, expiración y refresh que un
   producto de $100/mes no necesita operar aún).
2. API key en texto plano (descartado: robo de la base expone claves activas).

**Justificación.** Gama baja, simplicidad operativa y suficiente para el
alcance inicial; el hash protege la base y la rotación es posible.

**Condiciones (obligatorias).**

- La clave se almacena hasheada, nunca en claro.
- Rotación posible: varias claves activas por tenant, una puede desactivarse
  sin romper la otra.
- Middleware de auth resuelve `tenant_id` y lo inyecta en el contexto; sin key
  válida se devuelve 401.

---

## DEC-008-RESUELTA — Reindexado selectivo por sección

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto.** `/api/knowledge/reindex` recibe `sections` y debe reindexar solo
lo indicado, sin reconstruir todo el corpus.

**Decisión.** Cada sección (`faqs`, `catalog`, `policies`) rastrea su estado de
indexación en `knowledge_documents` mediante `content_hash` y
`last_indexed_at`. El reindex compara el hash del contenido de la sección con
el hash indexado: solo las filas cuyo hash cambió (o estado `pending`/`stale`)
se reindexan. Cambiar un precio actualiza el `content_hash` del documento de
catálogo y solo ese documento (sección `catalog`) se reindexa; FAQ y políticas
no se tocan.

**Alternativa.** Reindexar todo el corpus en cada cambio (descartado: costoso e
innecesario para MVP).

**Justificación.** Cumple el criterio de reindex incremental y es determinista
para pruebas.

---

## DEC-009-RESUELTA — Contrato de error uniforme

Estado: **RESUELTA**
Fecha: 2026-10-25

**Decisión.** Todos los errores de la API devuelven un cuerpo JSON estable:

```json
{
  "error": "<código estable>",
  "code": <HTTP status>,
  "message": "<legible para el cliente>",
  "request_id": "<UUID de la petición>",
  "tenant_id": "<ofuscado o null cuando no se conoce>"
}
```

Códigos estables: `validation_error`, `unauthorized`, `forbidden`,
`not_found`, `conflict`, `internal_error`.

**Alternativa.** Mensajes libres sin código (descartado: imposible de auditar
y de probar contratos estables).

**Justificación.** Permite tests de contrato deterministas y es compatible con
la auditoría (request_id correlaciona con `audit_log`).

**Condiciones (obligatorias).**

- `tenant_id` se ofusca (o se omite) cuando el request no se ha autenticado.
- Cada respuesta de error genera un `request_id` nuevo y se escribe en
  `audit_log` cuando el tenant es conocido.

---

## DEC-010-RESUELTA — Derecho al olvido: endpoint + anonimización ejecutiva

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto.** No basta con marcar `right_to_be_forgotten_requested_at`; debe
ejecutarse la anonimización.

**Decisión.**

- `POST /api/customers/{id}/forget-request` (cliente o admin): marca la fecha
  de solicitud.
- `POST /api/customers/{id}/forget-execute` (solo admin): anonimiza PII en
  `customers` (teléfono, nombre, email → NULL) y en `messages` (cuerpo →
  `[anonimizado]`), establece `anonymized_at`, deja `audit_log` con la acción
  y sin PII, es idempotente (segunda ejecución no falla).

**Justificación.** Cumple el derecho al olvido (GDPR/LGPD) y deja rastro de
auditoría sin exponer datos personales.

**Condiciones (obligatorias).**

- Tras `execute`, no quede nombre/teléfono/email en claro en `customers` ni
  `messages` de ese cliente.
- `execute` es idempotente y registra cada intento en `audit_log`.

---

## DEC-016 — Aislamiento reforzado en la base de datos

Estado: **ACEPTADA** (regla 1 del prompt)
Fecha: 2026-10-25

**Decisión.** Todas las tablas de negocio tienen `tenant_id NOT NULL` con índice
propio. Las referencias entre tablas del mismo tenant usan claves foráneas
compuestas `(tenant_id, id)` contra `UNIQUE (tenant_id, id)` en la tabla padre.
Así, un `service_id` del tenant A no puede usarse en una reserva del tenant B.

**Consecuencia.** `UNIQUE (tenant_id, id)` en las tablas padre; `id` sigue siendo
único global (UUIDv4).

---

## DEC-017 — `knowledge_documents` es metadatos, no el vector store

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Decisión.** Fase 1 crea la tabla de metadatos para indexación incremental
(sección, `source_id`, `content_hash`, `indexed_hash`, estado, fecha). Los
vectores se almacenan en pgvector en la Fase 5 (DEC-005). El seed deja los
documentos en `pending`.

**Consecuencia.** Cambiar un precio actualiza el `content_hash` del documento de
catálogo y sólo ese documento se reindexará.

---

## DEC-018 — Excepciones de horario por recurso

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Decisión.** `schedule_exceptions.resource_id` es obligatorio. Un cierre de todo
el negocio se replica como una excepción por recurso.

**Justificación.** Simplifica las claves foráneas compuestas y evita
excepciones huérfanas.

---

## DEC-019 — Tabla `idempotency_keys`

Estado: **ACEPTADA** (regla 4 del prompt)
Fecha: 2026-10-25

**Decisión.** Además de `bookings.idempotency_key`, se crea
`idempotency_keys(tenant_id, operation, key)` para cubrir `book`, `cancel` y
`reschedule` en la Fase 4. Necesaria para que cancelar y reprogramar también
sean idempotentes.

---

## DEC-020 — Bootstrap inicial del tenant

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Contexto.** Multi-tenant requiere crear el primer tenant sin un panel todavía.

**Decisión provisional.** El tenant demo se crea con
`python scripts/seed_demo_saas.py --db data/saas.db`. En Fase 2 se añade el alta
de tenants y su API key. Hasta entonces no hay endpoint público de alta.

---

## DEC-021 — Google Calendar es opcional

Estado: **ACEPTADA** (regla 6 del prompt)
Fecha: 2026-10-25

**Decisión.** El calendario interno SQL es la fuente de verdad. `bookings`
incluye `google_event_id` y `google_sync_status` desde el inicio, pero el flujo
funciona con `google_sync_status = 'disabled'`. El adapter Google se implementa
en Fase 4 y nunca es requisito para reservar.

---

## DEC-022 — Datos de prueba

Estado: **ACEPTADA** (AGENTS.md y prompt)
Fecha: 2026-10-25

**Decisión.** Las pruebas usan SQLite temporal. El seed `demo-dental` contiene
solo datos ficticios y no crea conversaciones ni reservas. No se leen `.env` ni
secretos, ni se usan datos de clientes reales.

---

## DEC-023 — No se modifican migraciones ni pruebas legacy

Estado: **ACEPTADA**
Fecha: 2026-10-25

**Decisión.** La entrega añade `saas/migrations/` y
`tests/test_saas_phase1.py`. No se editan `crm/store.py`, sus migraciones ni los
tests existentes. Cualquier cambio futuro en legacy se justificará aquí.

---

## DEC-024 — Enumeraciones como texto + CHECK

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Decisión.** Los estados (`status`, `state`, `severity`, `section`, etc.) se
guardan como `TEXT` con `CHECK` explícito. Evita `ENUM` nativo y facilita añadir
valores con una migración pequeña y portable.

---

## Riesgos abiertos

1. **Cifrado de datos personales**: pendiente; se decide con auth y políticas de
   retención (GDPR/CCPA/LGPD).
2. **Purgado físico de tenant**: requiere procedimiento controlado por tabla.
3. **Carga concurrente**: 100 reservas simultáneas se validan en Fase 8.
4. **Perfiles regulatorios por país**: pendiente de sección en DECISIONS.md
   (véase cumplimiento en DATA_MODEL.md).
