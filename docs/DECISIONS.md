# Registro de decisiones — SaaS de reservas multi-tenant

Fecha de apertura: 2026-10-25
Implementador: Nemotron (DeepSeek)
Auditor: el Cerebro

Estados usados:

- **ACEPTADA**: decisión fijada por el prompt de la entrega.
- **PENDIENTE_APROBACION_CEREBRO**: decisión tomada para poder avanzar, pero
  sujeta a revisión antes de continuar a la Fase 2.
- **PROPUESTA**: alternativa registrada, todavía no implementada.

> Regla: ninguna decisión marcada como pendiente se considera cerrada. Si el
> Cerebro la rechaza, se corrige antes de iniciar la fase siguiente.

---

## DEC-000 — Conflicto de alcance: multi-tenant frente a PLAN.md

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Contexto.** El prompt de esta entrega exige multi-tenant desde el día 1. El
`docs/producto/PLAN.md` vigente para la edición básica dice: «Una base privada
por instalación y aislamiento de archivos y conocimiento. No agregar multiempresa
ahora». Además, `ESTADO.md` indica que el destino Premium se trasladó a
`H:\git\Agente de reserva V4` y que V3 queda como referencia.

**Alternativas.**

1. No implementar multi-tenant en V3 y detenerse a pedir confirmación.
2. Implementar el nuevo producto en un paquete aislado (`saas/`) sin tocar el
   CRM legacy ni sus migraciones.
3. Reescribir el CRM legacy para multi-tenant.

**Elegida.** Opción 2. El prompt del propietario es una instrucción nueva y
explícita; se implementa en `saas/`, con pruebas propias, sin modificar el
código operativo existente. Si el Cerebro confirma que el alcance correcto era
el de `PLAN.md`, se elimina `saas/`, sus pruebas y sus documentos sin afectar
la aplicación legacy.

**Impacto.** La Fase 1 no toca `api/`, `crm/`, `ui/`, `database/` ni las bases
existentes.

---

## DEC-001 — Stack de la primera entrega

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Contexto.** El repositorio ya usa Python, SQLite y FastAPI en requirements,
pero el entorno de verificación no tiene instalados FastAPI, SQLAlchemy ni
Alembic. La Fase 1 sólo necesita esquema, migraciones, seed y pruebas.

**Alternativas.**

1. SQLAlchemy 2 + Alembic + PostgreSQL (contenedor).
2. SQLAlchemy 2 + Alembic + SQLite.
3. `sqlite3` de la biblioteca estándar + migraciones SQL versionadas + runner
   propio.
4. PostgreSQL + `psycopg` + migraciones SQL propias.

**Elegida.** Opción 3 para Fase 1. Mantiene el repositorio ejecutable con el
entorno existente, no añade dependencias y reutiliza el patrón de transacciones
`BEGIN IMMEDIATE` ya probado en `crm/store.py`.

**Consecuencias.** La lógica de negocio se escribe sin ORM. Si en fases
posteriores se migra a PostgreSQL, los contratos del repositorio se conservan y
las migraciones se traducen. FastAPI se incorporará en la Fase 2.

---

## DEC-002 — Motor de base de datos

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Contexto.** El prompt pide multi-tenant y un load test de 100 reservas
concurrentes. SQLite serializa escrituras, pero con WAL, `busy_timeout` y
transacciones cortas puede sostener el escenario de gama baja. PostgreSQL ofrece
mejor concurrencia y `EXCLUDE` para solapes.

**Alternativas.**

1. SQLite por instalación (como el CRM actual).
2. SQLite único compartido por todos los tenants (elegido para Fase 1).
3. PostgreSQL gestionado o en contenedor.

**Elegida.** SQLite único con `tenant_id`, WAL y `BEGIN IMMEDIATE`. Es suficiente
para el producto de ~100 USD/mes y evita dependencias externas en la primera
entrega. La decisión se revisará con el load test de la Fase 8; si falla, se
migra a PostgreSQL sin cambiar los contratos.

**Riesgo registrado.** El calendario interno y el vector store no comparten
transacción. La Fase 4 deberá definir la compensación.

---

## DEC-003 — Aislamiento reforzado en la base de datos

Estado: **ACEPTADA** (derivada de la regla 1 del prompt)
Fecha: 2026-10-25

**Decisión.** Todas las tablas de negocio tienen `tenant_id NOT NULL` con índice
propio. Las referencias entre tablas del mismo tenant usan claves foráneas
compuestas `(tenant_id, id)` contra un `UNIQUE (tenant_id, id)` en la tabla
padre. Así, un `service_id` del tenant A no puede usarse en una reserva del
tenant B aunque el programador olvide el filtro.

**Consecuencia.** Se añade `UNIQUE (tenant_id, id)` en las tablas padre. El `id`
sigue siendo único global (UUIDv4).

---

## DEC-004 — Identificadores, fechas y dinero

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Decisión.**

- IDs: UUIDv4 en texto (36 caracteres). Portable entre SQLite y PostgreSQL.
- Fechas/horas: texto ISO-8601 UTC con sufijo `Z` y milisegundos. Las reglas de
  zona horaria del negocio se aplican en la capa de dominio usando `zoneinfo` y
  `tenants.timezone` (IANA).
- Dinero: entero en centavos (`price_cents`) más moneda ISO-4217 de 3 letras.
  Nunca `float` para precios.

**Alternativa descartada.** `DATETIME` nativo de SQLite (no conserva zona) y
`REAL` para precios (errores de redondeo).

---

## DEC-005 — Política `ON DELETE`

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Decisión.**

- `tenant_id -> tenants(id)`: `ON DELETE RESTRICT`. El borrado de un tenant es
  lógico (`tenants.status = 'deleted'` o `'paused'`); un purgado físico exige un
  procedimiento controlado por tabla para no perder reservas ni auditoría.
- `schedules` y `schedule_exceptions -> resources`: `CASCADE`, porque una franja
  sin recurso no tiene sentido.
- `messages` y `handoff_alerts -> conversations`: `CASCADE`, porque son hijos
  directos de la conversación.
- `bookings -> services`, `resources`, `conversations`: `RESTRICT`. Se conserva
  el historial; para retirar un servicio se usa `active = 0`.

**Alternativa descartada.** `CASCADE` desde `tenants` a todo: en SQLite el orden
de aplicación de cascadas con `RESTRICT` intermedio no está garantizado y podía
impedir el purgado o borrar historial de forma silenciosa.

---

## DEC-006 — Enumeraciones como texto + CHECK

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Decisión.** Los estados (`status`, `state`, `severity`, `section`, etc.) se
guardan como `TEXT` con `CHECK` explícito. Evita `ENUM` nativo y facilita añadir
valores con una migración pequeña y portable.

---

## DEC-007 — `knowledge_documents` es metadatos, no el vector store

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Decisión.** En Fase 1 se crea la tabla de metadatos para indexación
incremental: sección (`faqs`, `catalog`, `policies`), `source_id`, `content_hash`,
`indexed_hash`, estado y fecha. Los vectores se almacenarán en Qdrant o pgvector
en la Fase 5. El seed deja los documentos en `pending`.

**Consecuencia.** Cambiar un precio actualizará el `content_hash` del documento
de catálogo y sólo ese documento se reindexará.

---

## DEC-008 — Excepciones de horario por recurso

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Decisión.** `schedule_exceptions.resource_id` es obligatorio. Un cierre de todo
el negocio se representa con una excepción por recurso. Simplifica las claves
foráneas compuestas y evita excepciones huérfanas.

---

## DEC-009 — Tabla `idempotency_keys`

Estado: **ACEPTADA** (derivada de la regla 4 del prompt)
Fecha: 2026-10-25

**Decisión.** Además de `bookings.idempotency_key`, se crea
`idempotency_keys(tenant_id, operation, key)` para cubrir `book`, `cancel` y
`reschedule` en la Fase 4. La tabla no estaba en la lista mínima del prompt, pero
es necesaria para que cancelar y reprogramar también sean idempotentes.

---

## DEC-010 — Autenticación y autorización

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Contexto.** La Fase 2 pide auth por tenant (API key o JWT básico).

**Opciones.** API key por tenant con hash en base; JWT firmado con un secreto
por instalación; ambos.

**Propuesta.** API key para integraciones y JWT de corta duración para el panel,
con `tenant_id` en el token. No se implementa en Fase 1. Se decide antes de
exponer endpoints.

---

## DEC-011 — Vector store y orquestador

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Propuesta.**

- Vector store: Qdrant local en Docker (ya es dependencia del repositorio) con
  `tenant_id` como filtro obligatorio. Alternativa: pgvector si se adopta
  PostgreSQL.
- Orquestador: LangGraph, ya presente en `requirements.txt`, con herramientas
  explícitas. El LLM no calcula agenda; sólo elige herramientas.

No se implementa en Fase 1.

---

## DEC-012 — Google Calendar es opcional

Estado: **ACEPTADA** (regla 6 del prompt)
Fecha: 2026-10-25

**Decisión.** El calendario interno SQL es la fuente de verdad. `bookings`
incluye `google_event_id` y `google_sync_status` desde el inicio, pero el flujo
funciona con `google_sync_status = 'disabled'`. El adapter Google se implementa
en Fase 4 y nunca es requisito para reservar.

---

## DEC-013 — Datos de prueba

Estado: **ACEPTADA** (AGENTS.md y prompt)
Fecha: 2026-10-25

**Decisión.** Las pruebas usan SQLite temporal. El seed `demo-dental` contiene
sólo datos ficticios y no crea conversaciones ni reservas. No se leen `.env` ni
secretos, ni se usan datos de clientes reales.

---

## DEC-014 — No se modifican migraciones ni pruebas legacy

Estado: **ACEPTADA**
Fecha: 2026-10-25

**Decisión.** La entrega añade `saas/migrations/` y
`tests/test_saas_phase1.py`. No se editan `crm/store.py`, sus migraciones ni los
tests existentes. Cualquier cambio futuro en legacy se justificará aquí.

---

## DEC-015 — Bootstrap inicial del tenant

Estado: **PENDIENTE_APROBACION_CEREBRO**
Fecha: 2026-10-25

**Contexto.** Multi-tenant requiere crear el primer tenant sin un panel todavía.

**Decisión provisional.** El tenant demo se crea con
`python scripts/seed_demo_saas.py --db data/saas.db`. En Fase 2 se añadirá el
alta de tenants y su API key. Hasta entonces no hay endpoint público de alta.

---

## Riesgos abiertos

1. **Conflicto con PLAN.md** (DEC-000): requiere confirmación antes de Fase 2.
2. **SQLite y 100 reservas concurrentes** (DEC-002): se valida en Fase 8.
3. **Cifrado de datos personales**: no definido todavía; se decidirá junto con
   auth y políticas de retención.
4. **Borrado de tenant**: es lógico; el purgado físico necesita procedimiento.
5. **Costo/operación de Qdrant**: se decide en Fase 5.
