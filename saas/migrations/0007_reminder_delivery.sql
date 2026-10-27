-- 0007_reminder_delivery.sql
-- Separa simulación de entrega real en recordatorios (Fase 4, Bloque 3).
-- Añade metadatos de entrega a reminder_log y una tabla de intentos.
-- ADD COLUMN no admite IF NOT EXISTS en SQLite: la idempotencia la garantiza
-- el runner de migraciones (una versión se aplica una sola vez por checksum).

ALTER TABLE reminder_log ADD COLUMN transport TEXT;
ALTER TABLE reminder_log ADD COLUMN delivered_at TEXT;

-- Cada intento de envío (simulado o real) queda registrado sin consumir el
-- recordatorio real: reminder_log.status permanece 'pending' hasta que un
-- transporte real confirma la entrega (mark_reminder_delivered).
CREATE TABLE IF NOT EXISTS reminder_send_attempts (
  id TEXT PRIMARY KEY,
  tenant_id TEXT NOT NULL,
  reminder_log_id TEXT NOT NULL,
  transport TEXT NOT NULL CHECK (transport IN ('simulated', 'whatsapp')),
  kind TEXT NOT NULL CHECK (kind IN ('simulated', 'delivery')),
  detail TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (reminder_log_id) REFERENCES reminder_log(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_reminder_attempts_tenant ON reminder_send_attempts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_reminder_attempts_log ON reminder_send_attempts(reminder_log_id);
