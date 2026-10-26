-- 0003_compliance.sql
-- Tablas de cumplimiento (GDPR/LGPD/CCPA): customers, data_processing_records,
-- consent_log, ai_disclosures.
-- Columnas de retención y anónimización en messages y columna de auditoría
-- tool_calls en audit_log.
-- Idempotente: aplicable varias veces sobre la misma base sin fallar.
-- NOTA: para añadir columnas a tablas existentes (messages, audit_log) se
-- reconstruye la tabla completa con las nuevas columnas, ya que SQLite no
-- soporta ALTER TABLE ... ADD COLUMN IF NOT EXISTS.

-- customers (tabla nueva, idempotente vía IF NOT EXISTS)
CREATE TABLE IF NOT EXISTS customers (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  phone TEXT,
  name TEXT,
  email TEXT,
  data_retention_until TEXT,
  anonymized_at TEXT,
  right_to_be_forgotten_requested_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, id)
);
CREATE INDEX IF NOT EXISTS idx_customers_tenant ON customers(tenant_id);
CREATE INDEX IF NOT EXISTS idx_customers_tenant_phone ON customers(tenant_id, phone);
CREATE INDEX IF NOT EXISTS idx_customers_forgotten ON customers(right_to_be_forgotten_requested_at);

-- data_processing_records (tabla nueva, idempotente vía IF NOT EXISTS)
CREATE TABLE IF NOT EXISTS data_processing_records (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  purpose TEXT NOT NULL CHECK (purpose IN ('booking','marketing','support')),
  legal_basis TEXT NOT NULL CHECK (legal_basis IN ('consent','contract','legitimate_interest')),
  data_categories TEXT NOT NULL CHECK (json_valid(data_categories)),
  retention_days INTEGER NOT NULL CHECK (retention_days > 0),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, purpose)
);
CREATE INDEX IF NOT EXISTS idx_data_processing_records_tenant ON data_processing_records(tenant_id);

-- consent_log (tabla nueva, idempotente vía IF NOT EXISTS)
CREATE TABLE IF NOT EXISTS consent_log (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  customer_id TEXT NOT NULL,
  purpose TEXT NOT NULL,
  consent_text_shown TEXT NOT NULL CHECK (length(trim(consent_text_shown)) > 0),
  accepted INTEGER NOT NULL CHECK (accepted IN (0,1)),
  accepted_at TEXT,
  ip_hash TEXT NOT NULL,
  user_agent_hash TEXT NOT NULL,
  revoked_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (tenant_id, id)
);
CREATE INDEX IF NOT EXISTS idx_consent_log_tenant ON consent_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_consent_log_tenant_customer ON consent_log(tenant_id, customer_id);

-- ai_disclosures (tabla nueva, idempotente vía IF NOT EXISTS)
CREATE TABLE IF NOT EXISTS ai_disclosures (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  conversation_id TEXT NOT NULL,
  disclosure_text TEXT NOT NULL,
  shown_at TEXT NOT NULL,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, conversation_id) REFERENCES conversations(tenant_id, id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_ai_disclosures_tenant ON ai_disclosures(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ai_disclosures_tenant_conversation ON ai_disclosures(tenant_id, conversation_id);

-- messages: añadir data_retention_until y anonymized_at (idempotente vía recreación de tabla)
CREATE TABLE IF NOT EXISTS messages_tmp (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  conversation_id TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('in','out')),
  author_type TEXT NOT NULL CHECK (author_type IN ('customer','bot','human','system')),
  author_id TEXT,
  body TEXT NOT NULL,
  external_id TEXT,
  delivery_status TEXT NOT NULL DEFAULT 'received' CHECK (delivery_status IN ('received','queued','sent','delivered','read','failed')),
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at TEXT NOT NULL,
  data_retention_until TEXT,
  anonymized_at TEXT,
  FOREIGN KEY (tenant_id, conversation_id) REFERENCES conversations(tenant_id, id) ON DELETE CASCADE,
  UNIQUE (tenant_id, id)
);
DELETE FROM messages_tmp;
INSERT INTO messages_tmp
  SELECT id, tenant_id, conversation_id, direction, author_type, author_id, body, external_id, delivery_status, metadata_json, created_at, NULL, NULL
  FROM messages;
DROP TABLE messages;
ALTER TABLE messages_tmp RENAME TO messages;
CREATE INDEX IF NOT EXISTS idx_messages_tenant ON messages(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_messages_tenant_external ON messages(tenant_id, external_id) WHERE external_id IS NOT NULL;

-- audit_log: añadir tool_calls (idempotente vía recreación de tabla)
CREATE TABLE IF NOT EXISTS audit_log_tmp (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('human','bot','system')),
  actor_id TEXT,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(payload_json)),
  tool_calls TEXT CHECK (tool_calls IS NULL OR json_valid(tool_calls)),
  created_at TEXT NOT NULL,
  UNIQUE (tenant_id, id)
);
DELETE FROM audit_log_tmp;
INSERT INTO audit_log_tmp
  SELECT id, tenant_id, actor_type, actor_id, action, entity_type, entity_id, payload_json, NULL, created_at
  FROM audit_log;
DROP TABLE audit_log;
ALTER TABLE audit_log_tmp RENAME TO audit_log;