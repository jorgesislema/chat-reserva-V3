-- 0006_reminders.sql
-- Scheduler de recordatorios, handoff y FTS5 para RAG (Fase 4, Bloque 2).
-- Idempotente: CREATE TABLE/TRIGGER/VIRTUAL TABLE IF NOT EXISTS en todas partes.

-- reminder_log: registro de envíos de recordatorios por cita y plantilla
CREATE TABLE IF NOT EXISTS reminder_log (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  booking_id TEXT NOT NULL,
  template_id TEXT NOT NULL,
  scheduled_for TEXT NOT NULL,
  sent_at TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sent','failed')),
  UNIQUE (tenant_id, booking_id, template_id)
);
CREATE INDEX IF NOT EXISTS idx_reminder_log_tenant ON reminder_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_reminder_log_status ON reminder_log(status);

-- FTS5 para búsqueda RAG en catálogo, FAQs y políticas.
-- Tabla virtual fina (sin content externo): el rowid INTEGER lo asigna SQLite.
CREATE VIRTUAL TABLE IF NOT EXISTS rag_search USING fts5(
  content,
  tenant_id,
  source_type,
  source_id
);

-- Trigger para mantener FTS5 sincronizado con catalog_items
CREATE TRIGGER IF NOT EXISTS catalog_items_fts_insert AFTER INSERT ON catalog_items BEGIN
  INSERT INTO rag_search(content, tenant_id, source_type, source_id)
  VALUES (new.name || ' ' || COALESCE(new.description, ''), new.tenant_id, 'catalog', new.id);
END;

CREATE TRIGGER IF NOT EXISTS catalog_items_fts_update AFTER UPDATE ON catalog_items BEGIN
  DELETE FROM rag_search WHERE source_type = 'catalog' AND source_id = old.id;
  INSERT INTO rag_search(content, tenant_id, source_type, source_id)
  VALUES (new.name || ' ' || COALESCE(new.description, ''), new.tenant_id, 'catalog', new.id);
END;

CREATE TRIGGER IF NOT EXISTS catalog_items_fts_delete AFTER DELETE ON catalog_items BEGIN
  DELETE FROM rag_search WHERE source_type = 'catalog' AND source_id = old.id;
END;

-- Trigger para mantener FTS5 sincronizado con faqs
CREATE TRIGGER IF NOT EXISTS faqs_fts_insert AFTER INSERT ON faqs BEGIN
  INSERT INTO rag_search(content, tenant_id, source_type, source_id)
  VALUES (new.question || ' ' || new.answer, new.tenant_id, 'faq', new.id);
END;

CREATE TRIGGER IF NOT EXISTS faqs_fts_update AFTER UPDATE ON faqs BEGIN
  DELETE FROM rag_search WHERE source_type = 'faq' AND source_id = old.id;
  INSERT INTO rag_search(content, tenant_id, source_type, source_id)
  VALUES (new.question || ' ' || new.answer, new.tenant_id, 'faq', new.id);
END;

CREATE TRIGGER IF NOT EXISTS faqs_fts_delete AFTER DELETE ON faqs BEGIN
  DELETE FROM rag_search WHERE source_type = 'faq' AND source_id = old.id;
END;

-- Trigger para mantener FTS5 sincronizado con policies
CREATE TRIGGER IF NOT EXISTS policies_fts_insert AFTER INSERT ON policies BEGIN
  INSERT INTO rag_search(content, tenant_id, source_type, source_id)
  VALUES (new.title || ' ' || new.body, new.tenant_id, 'policy', new.id);
END;

CREATE TRIGGER IF NOT EXISTS policies_fts_update AFTER UPDATE ON policies BEGIN
  DELETE FROM rag_search WHERE source_type = 'policy' AND source_id = old.id;
  INSERT INTO rag_search(content, tenant_id, source_type, source_id)
  VALUES (new.title || ' ' || new.body, new.tenant_id, 'policy', new.id);
END;

CREATE TRIGGER IF NOT EXISTS policies_fts_delete AFTER DELETE ON policies BEGIN
  DELETE FROM rag_search WHERE source_type = 'policy' AND source_id = old.id;
END;

-- Inicializar FTS5 con datos existentes (se ejecuta una sola vez por migración)
INSERT INTO rag_search(content, tenant_id, source_type, source_id)
  SELECT name || ' ' || COALESCE(description, ''), tenant_id, 'catalog', id FROM catalog_items;

INSERT INTO rag_search(content, tenant_id, source_type, source_id)
  SELECT question || ' ' || answer, tenant_id, 'faq', id FROM faqs;

INSERT INTO rag_search(content, tenant_id, source_type, source_id)
  SELECT title || ' ' || body, tenant_id, 'policy', id FROM policies;
