-- Fase 1: conversaciones, mensajes, reservas, alertas de handoff, auditoría e
-- idempotencia. Las reservas referencian servicio y recurso con ON DELETE
-- RESTRICT para no perder historial: se recomienda desactivar, no borrar.
-- La conversación se conserva con RESTRICT por la misma razón.

CREATE TABLE conversations (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  channel TEXT NOT NULL DEFAULT 'whatsapp'
    CHECK (channel IN ('whatsapp', 'web', 'test', 'telegram')),
  customer_phone TEXT NOT NULL,
  customer_name TEXT,
  status TEXT NOT NULL DEFAULT 'idle'
    CHECK (status IN ('idle', 'pending_human', 'closed')),
  state TEXT NOT NULL DEFAULT 'idle'
    CHECK (state IN ('idle', 'collecting_service', 'collecting_slot',
                     'confirming', 'booked', 'pending_human', 'resolved',
                     'closed')),
  assigned_to TEXT,
  last_message_at TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, id)
);

CREATE INDEX idx_conversations_tenant ON conversations(tenant_id);
CREATE INDEX idx_conversations_tenant_status ON conversations(tenant_id, status);
CREATE INDEX idx_conversations_tenant_phone
  ON conversations(tenant_id, customer_phone, last_message_at);

CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  conversation_id TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('in', 'out')),
  author_type TEXT NOT NULL
    CHECK (author_type IN ('customer', 'bot', 'human', 'system')),
  author_id TEXT,
  body TEXT NOT NULL,
  external_id TEXT,
  delivery_status TEXT NOT NULL DEFAULT 'received'
    CHECK (delivery_status IN ('received', 'queued', 'sent', 'delivered',
                               'read', 'failed')),
  metadata_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(metadata_json)),
  created_at TEXT NOT NULL,
  UNIQUE (tenant_id, id),
  FOREIGN KEY (tenant_id, conversation_id)
    REFERENCES conversations(tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX idx_messages_tenant ON messages(tenant_id);
CREATE INDEX idx_messages_tenant_conversation
  ON messages(tenant_id, conversation_id, created_at);
CREATE UNIQUE INDEX ux_messages_tenant_external
  ON messages(tenant_id, external_id) WHERE external_id IS NOT NULL;

CREATE TABLE bookings (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  service_id TEXT NOT NULL,
  resource_id TEXT NOT NULL,
  conversation_id TEXT,
  customer_name TEXT NOT NULL,
  customer_phone TEXT NOT NULL,
  customer_email TEXT,
  start_at TEXT NOT NULL,
  end_at TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'confirmed'
    CHECK (status IN ('pending', 'confirmed', 'cancelled', 'completed',
                      'no_show')),
  source TEXT NOT NULL DEFAULT 'admin'
    CHECK (source IN ('bot', 'web', 'admin', 'import', 'test')),
  notes TEXT NOT NULL DEFAULT '',
  cancellation_reason TEXT,
  idempotency_key TEXT,
  google_event_id TEXT,
  google_sync_status TEXT NOT NULL DEFAULT 'disabled'
    CHECK (google_sync_status IN ('disabled', 'pending', 'synced', 'error')),
  cancelled_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, id),
  CHECK (end_at > start_at),
  FOREIGN KEY (tenant_id, service_id)
    REFERENCES services(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, resource_id)
    REFERENCES resources(tenant_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (tenant_id, conversation_id)
    REFERENCES conversations(tenant_id, id) ON DELETE RESTRICT
);

CREATE INDEX idx_bookings_tenant ON bookings(tenant_id);
CREATE INDEX idx_bookings_tenant_resource_range
  ON bookings(tenant_id, resource_id, start_at, end_at);
CREATE INDEX idx_bookings_tenant_customer
  ON bookings(tenant_id, customer_phone, start_at);
CREATE INDEX idx_bookings_tenant_status_range
  ON bookings(tenant_id, status, start_at);
CREATE UNIQUE INDEX ux_bookings_tenant_idempotency
  ON bookings(tenant_id, idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE TABLE handoff_alerts (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  conversation_id TEXT NOT NULL,
  reason TEXT NOT NULL CHECK (length(trim(reason)) > 0),
  severity TEXT NOT NULL DEFAULT 'medium'
    CHECK (severity IN ('low', 'medium', 'high', 'urgent')),
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'in_progress', 'resolved')),
  assigned_to TEXT,
  created_at TEXT NOT NULL,
  taken_at TEXT,
  resolved_at TEXT,
  resolution_note TEXT,
  UNIQUE (tenant_id, id),
  CHECK (status <> 'in_progress' OR taken_at IS NOT NULL),
  CHECK (
    status <> 'resolved'
    OR (taken_at IS NOT NULL AND resolved_at IS NOT NULL
        AND resolution_note IS NOT NULL
        AND length(trim(resolution_note)) > 0)
  ),
  FOREIGN KEY (tenant_id, conversation_id)
    REFERENCES conversations(tenant_id, id) ON DELETE CASCADE
);

CREATE INDEX idx_handoff_alerts_tenant ON handoff_alerts(tenant_id);
CREATE INDEX idx_handoff_alerts_tenant_status
  ON handoff_alerts(tenant_id, status, created_at);
CREATE INDEX idx_handoff_alerts_tenant_conversation
  ON handoff_alerts(tenant_id, conversation_id);

CREATE TABLE audit_log (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  actor_type TEXT NOT NULL CHECK (actor_type IN ('human', 'bot', 'system')),
  actor_id TEXT,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}' CHECK (json_valid(payload_json)),
  created_at TEXT NOT NULL,
  UNIQUE (tenant_id, id)
);

CREATE INDEX idx_audit_log_tenant ON audit_log(tenant_id);
CREATE INDEX idx_audit_log_tenant_entity
  ON audit_log(tenant_id, entity_type, entity_id, created_at);
CREATE INDEX idx_audit_log_tenant_created ON audit_log(tenant_id, created_at);

CREATE TABLE idempotency_keys (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  operation TEXT NOT NULL CHECK (operation IN ('book', 'cancel', 'reschedule')),
  key TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  response_json TEXT CHECK (response_json IS NULL OR json_valid(response_json)),
  status TEXT NOT NULL DEFAULT 'in_progress'
    CHECK (status IN ('in_progress', 'completed', 'failed')),
  created_at TEXT NOT NULL,
  completed_at TEXT,
  UNIQUE (tenant_id, id),
  UNIQUE (tenant_id, operation, key)
);

CREATE INDEX idx_idempotency_keys_tenant ON idempotency_keys(tenant_id);
CREATE INDEX idx_idempotency_keys_tenant_operation
  ON idempotency_keys(tenant_id, operation, status);
