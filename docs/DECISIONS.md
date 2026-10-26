# Registro de decisiones — SaaS de reservas multi-tenant

Fecha de apertura: 2026-10-25
Implementador: Nemotron (DeepSeek)
Auditor: el Cerebro

Estados usados:

- **ACEPTADA**: decisión fijada por el prompt de la entrega o por el Cerebro.
- **PENDIENTE_APROBACION_CEREBRO**: decisión tomada pero sujeta a revisión antes de continuar.
- **RESUELTA**: decisión revisada y aprobada por el Cerebro.
- **PROPUESTA**: alternativa registrada, todavía no implementada.
- **PENDIENTE_VERIFICACIÓN**: decisión tomada pero cuya verificación (build/prueba) aún no ha pasado.

> Regla: ninguna decisión marcada como pendiente se considera cerrada. Si el Cerebro la rechaza, se corrige antes de iniciar la siguiente fase.

---

## DEC-000-RESUELTA — Modelo multi-tenant nativo (corrige PLAN.md)

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto.** El prompt de Fase 1 exige multi-tenant desde el día 1, pero `docs/producto/PLAN.md` declaraba "Una base privada por instalación... No agregar multiempresa ahora". Contradicción entre el producto especificado y el plan vigente.

**Decisión.** El producto es MULTI-TENANT NATIVO: cada negocio es un tenant aislado con la columna `tenant_id` en toda tabla de negocio. No hay instalaciones físicas separadas por cliente; un despliegue atiende a N negocios.

**Alternativas:**
1. Instalación física separada por cliente: descartada — no escala a $100/mes y multiplica operaciones (backups, parches).
2. Subdominio o esquema por tenant: descartado — complejidad innecesaria para el MVP.
3. Columna `tenant_id` compartida: ELEGIDA.

**Justificación:** Un SaaS de ~100 USD/mes requiere escala horizontal: un despliegue atiende a N negocios.

**Condiciones (obligatorias):**
- Toda tabla de negocio tiene `tenant_id NOT NULL` con índice propio.
- Las FK compuestas usan `(tenant_id, id)` contra `UNIQUE (tenant_id, id)` en la tabla padre.
- Toda consulta de negocio filtra por `tenant_id`.

---

## DEC-001-RESUELTA — SQLite para dev y MVP, con capa de repositorio abstraída

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto.** Fase 1 necesita esquema, migraciones, seed y pruebas sin dependencias pesadas. Producto de $100/mes no puede costear PostgreSQL gestionado.

**Decisión:** SQLite como motor de Fase 1, con capa de repositorio (`saas/repository.py`) que abstrae el acceso a datos.

**Alternativas:**
1. SQLAlchemy 2 + Alembic + PostgreSQL (descartada: dependencias pesadas).
2. SQLAlchemy 2 + Alembic + SQLite (descartada: ORM innecesario).
3. `sqlite3` de stdlib + migraciones SQL versionadas + runner propio (elegida).

**Justificación:** Menor latencia, control total de `BEGIN IMMEDIATE` para evitar doble-booking, reutiliza patrón de `crm/store.py`.

**Condiciones (obligatorias):**
- Queries parametrizadas en todo el repositorio (prevención de inyección SQL).
- Pruebas de integración contra base de datos real.
- Migraciones transaccionales con checksum SHA-256.

---

## DEC-002-RESUELTA — SQL directo sin ORM

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto:** Control total sobre esquema y transacciones para el motor de reservas y el aislamiento multi-tenant.

**Decisión:** Acceso a datos con SQL directo y runner de migraciones propio (`saas/db.py`), sin ORM.

**Alternativas:**
1. SQLAlchemy 2 (descartada: capa extra, dependencia pesada).
2. Micro-ORM tipo peewee (descartada: dependencia extra sin beneficio claro).
3. `sqlite3` de stdlib (elegida).

**Justificación:** Menor latencia, control total de `BEGIN IMMEDIATE` para evitar doble-booking, menos dependencias.

**Condiciones (obligatorias):**
- Queries parametrizadas en todo el repositorio.
- Pruebas de integración contra DB real.

---

## DEC-003-RESUELTA — UUIDs, fechas ISO-8601 UTC y dinero en centavos

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto:** Evitar errores de zona horaria y punto flotante en citas y precios.

**Decisión:**
- IDs: UUIDv4 en texto.
- Fechas/horas: texto ISO-8601 UTC con sufijo `Z` (ej. `2026-10-25T09:00:00.000Z`).
- Dinero: entero en centavos (`price_cents`) más moneda ISO-4217 de 3 letras.

**Alternativa descartada:** `DATETIME` nativo + `REAL` (descartado: no conserva zona / errores de redondeo).

**Justificación:** Evita errores de zona horaria y punto flotante en citas y precios.

**Condiciones (obligatorias):**
- Toda columna de dinero es `INTEGER` (centavos); nunca `REAL`/`FLOAT`.
- Toda columna de fecha/hora es `TEXT` ISO-8601 UTC con sufijo `Z`.

---

## DEC-004-RESUELTA — Autenticación por API key o JWT por tenant

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto:** Fase 2 requiere auth por tenant. Gama baja: simplicidad, sin OAuth2 complejo.

**Decisión:** API key por tenant, almacenada hasheada (SHA-256) en tabla `api_keys`, enviada en cabecera `X-API-Key`. `tenant_id` nunca viene del cuerpo de la petición.

**Alternativas:**
1. JWT firmado con secreto (descartado: complejidad de gestión de secretos/expiración).
2. OAuth2 (descartado: demasiado complejo para MVP).
3. API key en texto plano (descartado: robo de base expone claves activas).

**Justificación:** Gama baja, simplicidad operativa; el hash protege la base y permite rotación.

**Condiciones (obligatorias):**
- Clave almacenada hasheada, nunca en claro.
- Rotación posible.
- `tenant_id` derivado de la key, validado en cada request.

---

## DEC-005-RESUELTA — Estrategia vectorial: pgvector vs Qdrant

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto:** Fase 5 necesita vector store para RAG. Producto de $100/mes no puede mantener servicio vectorial adicional.

**Decisión:** pgvector sobre Qdrant.

**Alternativas:**
1. Qdrant local en Docker (descartado: servicio adicional que operar y monitorear).
2. pgvector (elegida).

**Justificación:** Menos infraestructura que operar, backup unificado, menor costo mensual.

**Condición (obligatoria):** Interfaz de retrieval abstracta para poder migrar a Qdrant sin cambiar la lógica de negocio.

---

## DEC-006-RESUELTA — Política RESTRICT en FKs y borrado lógico

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto:** Evitar borrados en cascada accidentales que destruyan datos de negocio (reservas, historial de mensajes, auditoría).

**Decisión:** `ON DELETE RESTRICT` en FKs entre tablas de negocio; `tenant_id → tenants(id)` también `RESTRICT`; borrado de tenant es lógico (`status='deleted'`/`'paused'`), nunca físico mientras haya datos asociados.

**Alternativas:**
1. `CASCADE` masivo desde tenants (descartado: borrado silencioso de historial; orden de cascada no garantizado en SQLite con `RESTRICT` intermedio).
2. `RESTRICT` en todas las FK (elegida).

**Justificación:** Preserva reservas, mensajes, alertas de handoff y auditoría; borrado lógico permite reactivar o purgar de forma controlada.

**Condiciones (obligatorias):**
- Borrado lógico (`soft delete`) para entidades con historial.
- Procedimiento de purgado físico documentado y por tabla cuando se requiera.

---

## DEC-007-RESUELTA — Consentimiento y disclosure de IA

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto:** GDPR/CCPA/LGPD exigen consentimiento explícito; EU AI Act Art. 50 exige transparencia de IA.

**Decisión:** Tablas `consent_log` (consentimiento explícito con `consent_text_shown`, `accepted`, `accepted_at`, `ip_hash`, `user_agent_hash`, `revoked_at`) y `ai_disclosures` (`disclosure_text`, `shown_at`) en migración `0003_compliance.sql`.

**Alternativas:**
1. No registrar (descartado: incumplimiento).
2. Guardar solo booleano de aceptación (descartado: insuficiente para auditoría).
3. Guardar texto mostrado y hashes de IP/UA (elegida).

**Justificación:** Cumple transparencia y consentimiento informado; permite auditoría.

**Condición (obligatoria):** IP y `user_agent` solo se guardan con hash (SHA-256), nunca en claro.

---

## DEC-008-RESUELTA — Derecho al olvido y anonimización

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto:** GDPR/LGPD derecho al olvido; no borrar en cascada destruyendo historial.

**Decisión:** Campo `right_to_be_forgotten_requested_at` en `customers`; proceso de anonimización que pone `customer.phone`/`name`/`email`=NULL y `messages.body`='[anonimizado]', con `anonymized_at`; registro en `audit_log` sin PII.

**Alternativas:**
1. Borrado físico (descartado: rompe FK).
2. Anonimización parcial (elegida).

**Justificación:** Cumple derecho al olvido sin destruir historial de reservas.

**Condición (obligatoria):** Tras anonimización no queda PII en claro en `customers` ni `messages`.

---

## DEC-009-RESUELTA — Idempotencia de seed y migraciones

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto:** Seed y migraciones deben poder ejecutarse múltiples veces sin duplicar ni fallar.

**Decisión:** `INSERT OR IGNORE` / `CREATE TABLE IF NOT EXISTS` en seed y migraciones; runner de migraciones salta versiones ya aplicadas.

**Alternativas:**
1. Ejecutar siempre y permitir errores (descartado: ruido en logs).
2. Borrar y recrear (descartado: destruye datos).

**Justificación:** Operaciones seguras de repetir en entornos automatizados.

**Condición (obligatoria):** `scripts/seed_demo_saas.py` ejecutable múltiples veces con mismo resultado.

---

## DEC-010-RESUELTA — Gate de aprobación para Fase 2

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto:** Fase 2 requiere aprobación explícita del Cerebro antes de iniciar.

**Decisión:** Fase 2 queda bloqueada hasta aprobación explícita del Cerebro sobre Fase 1.

**Alternativas:**
1. Avanzar automáticamente (descartado: incumple gobernanza).
2. Bloquear (elegida).

**Justificación:** Mantener control de calidad antes de expandir alcance.

**Condición (obligatoria):** Fase 2 no inicia hasta que el Cerebro apruebe Fase 1.

---

## DEC-015-RESUELTA — Gate de aprobación para Fase 2

Estado: **RESUELTA**
Fecha: 2026-10-25

**Contexto:** Fase 2 requiere aprobación explícita del Cerebro antes de iniciar.

**Decisión:** Fase 2 queda bloqueada hasta aprobación explícita del Cerebro sobre Fase 1.

**Alternativas:**
1. Avanzar automáticamente (descartado: incumple gobernanza).
2. Bloquear (elegida).

**Justificación:** Mantener control de calidad antes de expandir alcance.

**Condición (obligatoria):** Fase 2 no inicia hasta que el Cerebro apruebe Fase 1.

---

## DEC-011-RESUELTA — Stack de frontend: React + Vite + Tailwind CSS

Estado: **PENDIENTE_VERIFICACIÓN**
Fecha: 2026-10-25

**Contexto:** Fase 3 requiere panel de administración web (SPA).

**Decisión:** React 18 + Vite 5 + Tailwind CSS 3.

**Justificación:** Gama baja, bajo coste de desarrollo y mantenimiento.

**Condición (obligatoria):** `npm run build` debe pasar sin errores de sintaxis. Actualmente el frontend commiteado **no compila** (ver `npm run build`); estado pendiente de verificación.

---

## DEC-012-RESUELTA — Manejo de estado: Zustand + TanStack Query

Estado: **PENDIENTE_VERIFICACIÓN**
Fecha: 2026-10-25

**Contexto:** Panel requiere estado global (tenant, auth, UI) y estado servidor (cache, invalidación).

**Decisión:** Zustand para estado global + TanStack Query para estado servidor.

**Justificación:** API simple, bundle pequeño, integración natural.

**Condición (obligatoria):** Pendiente de verificar que el frontend compila y funciona (DEC-011).

---

## DEC-013-RESUELTA — Auth en frontend: API Key en localStorage + Axios interceptor

Estado: **PENDIENTE_VERIFICACIÓN**
Fecha: 2026-10-25

**Contexto:** Panel debe autenticarse contra la API (DEC-004) sin exponer API key en URLs ni logs.

**Decisión:** API key en `localStorage` (clave `saas_api_key`) y enviada en cabecera `X-API-Key` via interceptor de Axios.

**Justificación:** Simple, sin servidor extra, compatible con API key rotation.

**Condición (obligatoria):** Pendiente de verificar que el frontend compila y funciona (DEC-011).

---

## DEC-014-RESUELTA — Librería de componentes: Radix UI + Tailwind

Estado: **PENDIENTE_VERIFICACIÓN**
Fecha: 2026-10-25

**Contexto:** Necesita componentes accesibles (WCAG 2.1 AA), consistentes y personalizables.

**Decisión:** Radix UI (componentes headless accesibles) + Tailwind CSS (estilos utilitarios).

**Justificación:** Componentes headless 100% accesibles, estilos 100% controlados por Tailwind, bundle mínimo.

**Condición (obligatoria):** Pendiente de verificar que el frontend compila (DEC-011).
