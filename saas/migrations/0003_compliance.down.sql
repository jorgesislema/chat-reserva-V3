-- Revertido de 0003_compliance.sql.
-- ADVERTENCIA: esta migración elimina tablas y columnas (customers,
-- data_processing_records, consent_log, ai_disclosures,
-- messages.data_retention_until, messages.anonymized_at,
-- messages.customer_phone, audit_log.tool_calls). LOS DATOS SE PIERDEN IRREVERSIBLEMENTE.
-- Ejecutar DESPUÉS de haber aplicado la migración arriba. No gestionada por
-- el runner automático (se ejecuta manualmente en pruebas de reversión).

DROP INDEX IF EXISTS idx_messages_retention;
DROP INDEX IF EXISTS idx_customers_retention;
DROP INDEX IF EXISTS idx_customers_forgotten;
ALTER TABLE audit_log DROP COLUMN tool_calls;
ALTER TABLE messages DROP COLUMN anonymized_at;
ALTER TABLE messages DROP COLUMN data_retention_until;
ALTER TABLE messages DROP COLUMN customer_phone;

DROP TABLE IF EXISTS ai_disclosures;
DROP TABLE IF EXISTS consent_log;
DROP TABLE IF EXISTS data_processing_records;
DROP TABLE IF EXISTS customers;
