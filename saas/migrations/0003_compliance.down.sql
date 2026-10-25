-- Revertido de 0003_compliance.sql.
-- Ejecutar DESPUÉS de haber aplicado la migración arriba. No gestionado por
-- el runner automático (se ejecuta manualmente en pruebas de reversión).

DROP INDEX IF EXISTS idx_messages_retention;
DROP INDEX IF EXISTS idx_customers_retention;
DROP INDEX IF EXISTS idx_customers_forgotten;
ALTER TABLE audit_log DROP COLUMN tool_calls;
ALTER TABLE messages DROP COLUMN anonymized_at;
ALTER TABLE messages DROP COLUMN data_retention_until;

DROP TABLE IF EXISTS ai_disclosures;
DROP TABLE IF EXISTS consent_log;
DROP TABLE IF EXISTS data_processing_records;
DROP TABLE IF EXISTS customers;
