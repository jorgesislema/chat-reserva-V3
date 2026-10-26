-- 0005_catalog_templates.sql
-- Catálogo RAG y Plantillas WhatsApp (Fase 4, Bloque 1).
-- Idempotente: CREATE TABLE IF NOT EXISTS en todas partes.

-- catálogo_items: tratamientos, productos, regalos, normas
CREATE TABLE IF NOT EXISTS catalog_items (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('tratamiento','producto','regalo','norma')),
  price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
  description TEXT,
  inventory INTEGER DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, name)
);
CREATE INDEX IF NOT EXISTS idx_catalog_items_tenant ON catalog_items(tenant_id);
CREATE INDEX IF NOT EXISTS idx_catalog_items_type ON catalog_items(type);

-- whatsapp_templates: plantillas de mensaje con variables {{nombre}} {{fecha}} {{hora}}
CREATE TABLE IF NOT EXISTS whatsapp_templates (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  name TEXT NOT NULL,
  body_text TEXT NOT NULL,
  meta_status TEXT NOT NULL DEFAULT 'pendiente' CHECK (meta_status IN ('aprobada','pendiente','rechazada')),
  advance_value INTEGER NOT NULL DEFAULT 0 CHECK (advance_value >= 0),
  advance_unit TEXT NOT NULL DEFAULT 'horas' CHECK (advance_unit IN ('horas','dias')),
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (tenant_id, name)
);
CREATE INDEX IF NOT EXISTS idx_whatsapp_templates_tenant ON whatsapp_templates(tenant_id);
CREATE INDEX IF NOT EXISTS idx_whatsapp_templates_meta ON whatsapp_templates(meta_status);