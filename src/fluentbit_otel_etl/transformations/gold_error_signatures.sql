CREATE OR REFRESH MATERIALIZED VIEW gold_error_signatures
CLUSTER BY (event_date, error_signature)
COMMENT 'Daily ERROR/WARN volume by error signature, client and service.'
AS
SELECT
  event_date,
  error_signature,
  client_id,
  client_name,
  service_name,
  namespace,
  severity_text,
  COUNT(*) AS event_count
FROM silver_otel_logs
WHERE severity_text IN ('ERROR', 'WARN')
GROUP BY event_date, error_signature, client_id, client_name, service_name, namespace, severity_text;
