-- Fase 1 corrección post-auditoría: cumplimiento y gobernanza.
-- Normativas: GDPR (UE), CCPA/CPRA y NIST AI RMF (EE. UU.), LGPD (Brasil),
-- Perú DS 115-2025-PCM y Ecuador (en discusión).
--
-- Tablas nuevas: customers, data_processing_records, consent_log, ai_disclosures.
-- Columnas nuevas: messages.data_retention_until, messages.anonymized_at,
-- audit_log.tool_calls.
--
-- Índices para jobs de purga y DSAR sobre data_retention_until y
-- right_to_be_forgotten_requested_at.
--
-- Revertir con: saas/migrations/0003_compliance.down.sql

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
CREATE INDEX IF NOT EXISTS idx_customers_retention ON customers(data_retention_until);
CREATE INDEX IF NOT EXISTS idx_customers_forgotten
  ON customers(right_to_be_forgotten_requested_at);

CREATE TABLE IF NOT EXISTS data_processing_records (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  purpose TEXT NOT NULL CHECK (purpose IN ('booking', 'marketing', 'support')),
  legal_basis TEXT NOT NULL
    CHECK (legal_basis IN ('consent', 'contract', 'legitimate_interest')),
  data_categories TEXT NOT NULL CHECK (json_valid(data_categories)),
  retention_days INTEGER NOT NULL CHECK (retention_days > 0),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, purpose)
);

CREATE INDEX IF NOT EXISTS idx_data_processing_records_tenant
  ON data_processing_records(tenant_id);

CREATE TABLE IF NOT EXISTS consent_log (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  customer_id TEXT NOT NULL,
  purpose TEXT NOT NULL,
  consent_text_shown TEXT NOT NULL
    CHECK (length(trim(consent_text_shown)) > 0),
  accepted INTEGER NOT NULL CHECK (accepted IN (0, 1)),
  accepted_at TEXT,
  ip_hash TEXT NOT NULL,
  user_agent_hash TEXT NOT NULL,
  revoked_at TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, customer_id)
    REFERENCES customers(tenant_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_consent_log_tenant ON consent_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_consent_log_tenant_customer
  ON consent_log(tenant_id, customer_id);

CREATE TABLE IF NOT EXISTS ai_disclosures (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  conversation_id TEXT NOT NULL,
  disclosure_text TEXT NOT NULL,
  shown_at TEXT NOT NULL,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, conversation_id)
    REFERENCES conversations(tenant_id, id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_ai_disclosures_tenant ON ai_disclosures(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ai_disclosures_tenant_conversation
  ON ai_disclosures(tenant_id, conversation_id);

-- Columnas de retención, anonimización y contacto en mensajes.
ALTER TABLE messages ADD COLUMN data_retention_until TEXT;
ALTER TABLE messages ADD COLUMN anonymized_at TEXT;
ALTER TABLE messages ADD COLUMN customer_phone TEXT;

CREATE INDEX IF NOT EXISTS idx_messages_retention ON messages(data_retention_until);
CREATE INDEX IF NOT EXISTS idx_messages_customer_phone ON messages(customer_phone);

-- Auditoría de tool_calls del LLM (parámetros y resultado).
ALTER TABLE audit_log ADD COLUMN tool_calls TEXT
  CHECK (tool_calls IS NULL OR json_valid(tool_calls));
