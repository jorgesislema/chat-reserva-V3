-- Fase 1: tenancy, configuración del negocio y metadatos de conocimiento.
-- Todas las tablas de negocio llevan tenant_id con índice propio.
-- Las referencias entre tablas del mismo tenant usan FK compuestas
-- (tenant_id, id) para impedir cruces accidentales entre tenants.

CREATE TABLE tenants (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  legal_name TEXT,
  status TEXT NOT NULL DEFAULT 'active'
    CHECK (status IN ('active', 'paused', 'deleted')),
  timezone TEXT NOT NULL DEFAULT 'UTC',
  locale TEXT NOT NULL DEFAULT 'es-ES',
  currency TEXT NOT NULL DEFAULT 'EUR' CHECK (length(currency) = 3),
  business_type TEXT,
  labels_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(labels_json)),
  settings_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(settings_json)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE resources (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  name TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'professional',
  email TEXT,
  phone TEXT,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  sort_order INTEGER NOT NULL DEFAULT 0,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, name)
);

CREATE INDEX idx_resources_tenant ON resources(tenant_id);
CREATE INDEX idx_resources_tenant_active ON resources(tenant_id, active, sort_order);

CREATE TABLE services (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  name TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  category TEXT,
  duration_min INTEGER NOT NULL CHECK (duration_min > 0),
  buffer_before_min INTEGER NOT NULL DEFAULT 0 CHECK (buffer_before_min >= 0),
  buffer_after_min INTEGER NOT NULL DEFAULT 0 CHECK (buffer_after_min >= 0),
  price_cents INTEGER NOT NULL DEFAULT 0 CHECK (price_cents >= 0),
  currency TEXT NOT NULL DEFAULT 'EUR' CHECK (length(currency) = 3),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  sort_order INTEGER NOT NULL DEFAULT 0,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, name)
);

CREATE INDEX idx_services_tenant ON services(tenant_id);
CREATE INDEX idx_services_tenant_active ON services(tenant_id, active, sort_order);

CREATE TABLE schedules (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  resource_id TEXT NOT NULL,
  weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
  start_time TEXT NOT NULL CHECK (length(start_time) = 5),
  end_time TEXT NOT NULL CHECK (length(end_time) = 5),
  valid_from TEXT,
  valid_to TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, id),
  CHECK (start_time < end_time),
  CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
  FOREIGN KEY (tenant_id, resource_id)
    REFERENCES resources(tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX idx_schedules_tenant ON schedules(tenant_id);
CREATE INDEX idx_schedules_tenant_resource ON schedules(tenant_id, resource_id, weekday);

CREATE TABLE schedule_exceptions (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  resource_id TEXT NOT NULL,
  exception_date TEXT NOT NULL CHECK (length(exception_date) = 10),
  exception_type TEXT NOT NULL
    CHECK (exception_type IN ('closed', 'extra', 'modified')),
  start_time TEXT,
  end_time TEXT,
  reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, id),
  CHECK (
    (exception_type = 'closed' AND start_time IS NULL AND end_time IS NULL)
    OR
    (exception_type IN ('extra', 'modified')
      AND start_time IS NOT NULL AND end_time IS NOT NULL AND start_time < end_time)
  ),
  FOREIGN KEY (tenant_id, resource_id)
    REFERENCES resources(tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX idx_schedule_exceptions_tenant ON schedule_exceptions(tenant_id);
CREATE INDEX idx_schedule_exceptions_tenant_resource_date
  ON schedule_exceptions(tenant_id, resource_id, exception_date);

CREATE TABLE faqs (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  question TEXT NOT NULL CHECK (length(trim(question)) > 0),
  answer TEXT NOT NULL CHECK (length(trim(answer)) > 0),
  category TEXT,
  priority INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, id)
);

CREATE INDEX idx_faqs_tenant ON faqs(tenant_id);
CREATE INDEX idx_faqs_tenant_active ON faqs(tenant_id, active, priority);

CREATE TABLE policies (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  key TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL CHECK (length(trim(body)) > 0),
  category TEXT,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, key)
);

CREATE INDEX idx_policies_tenant ON policies(tenant_id);
CREATE INDEX idx_policies_tenant_active ON policies(tenant_id, active, key);

CREATE TABLE knowledge_documents (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  section TEXT NOT NULL CHECK (section IN ('faqs', 'catalog', 'policies')),
  source_type TEXT NOT NULL,
  source_id TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL,
  indexed_hash TEXT,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'indexed', 'stale', 'error')),
  chunk_count INTEGER NOT NULL DEFAULT 0 CHECK (chunk_count >= 0),
  embedding_model TEXT,
  last_indexed_at TEXT,
  last_error TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, section, source_id)
);

CREATE INDEX idx_knowledge_documents_tenant ON knowledge_documents(tenant_id);
CREATE INDEX idx_knowledge_documents_tenant_section_status
  ON knowledge_documents(tenant_id, section, status);
