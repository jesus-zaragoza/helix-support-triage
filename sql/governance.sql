-- Unity Catalog governance applied after the pipeline has published silver/gold.
-- Placeholders ${catalog} / ${schema} / ${bronze_table} are substituted by
-- src/notebooks/01_governance.ipynb. One statement per ';'.

COMMENT ON SCHEMA ${catalog}.${schema} IS 'Helix Clinical Cloud support triage: typed app logs, client health, anomaly scores and AI incident briefs. Synthetic data.';

ALTER SCHEMA ${catalog}.${schema} SET TAGS ('domain' = 'operations', 'data_classification' = 'pii', 'data_origin' = 'synthetic');

ALTER TABLE ${bronze_table} SET TAGS ('domain' = 'operations', 'layer' = 'bronze', 'contains_pii' = 'true', 'ingest_source' = 'fluent-bit-zerobus-otlp');

ALTER TABLE ${catalog}.${schema}.silver_otel_logs SET TAGS ('domain' = 'operations', 'layer' = 'silver', 'contains_pii' = 'true');

ALTER TABLE ${catalog}.${schema}.silver_otel_logs ALTER COLUMN user_email SET TAGS ('pii_category' = 'email');

ALTER TABLE ${catalog}.${schema}.silver_otel_logs ALTER COLUMN study_id SET TAGS ('confidentiality' = 'client_confidential');

ALTER TABLE ${catalog}.${schema}.gold_client_health SET TAGS ('domain' = 'operations', 'layer' = 'gold', 'contains_pii' = 'false', 'serving' = 'lakebase');

ALTER TABLE ${catalog}.${schema}.gold_incident_summary SET TAGS ('domain' = 'operations', 'layer' = 'gold', 'contains_pii' = 'false');

ALTER TABLE ${catalog}.${schema}.gold_error_signatures SET TAGS ('domain' = 'operations', 'layer' = 'gold', 'contains_pii' = 'false');

ALTER TABLE ${catalog}.${schema}.gold_service_volume SET TAGS ('domain' = 'operations', 'layer' = 'gold', 'contains_pii' = 'false');

-- Everyone in the account can browse the schema and read the PII-free gold layer.
GRANT USE SCHEMA ON SCHEMA ${catalog}.${schema} TO `account users`;

GRANT SELECT ON TABLE ${catalog}.${schema}.gold_client_health TO `account users`;

GRANT SELECT ON TABLE ${catalog}.${schema}.gold_incident_summary TO `account users`;

GRANT SELECT ON TABLE ${catalog}.${schema}.gold_error_signatures TO `account users`;

GRANT SELECT ON TABLE ${catalog}.${schema}.gold_service_volume TO `account users`;

-- Silver keeps PII. It is not granted to `account users`; masks hide email/study id from
-- anyone outside the account group helix_support_analysts, even when SELECT is granted.
-- The Support Console app service principal reads gold + AI outputs.
GRANT USE CATALOG ON CATALOG ${catalog} TO `${app_sp}`;

GRANT USE SCHEMA ON SCHEMA ${catalog}.${schema} TO `${app_sp}`;

GRANT SELECT ON SCHEMA ${catalog}.${schema} TO `${app_sp}`
