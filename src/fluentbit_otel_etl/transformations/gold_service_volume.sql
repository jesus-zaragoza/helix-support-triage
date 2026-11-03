CREATE OR REFRESH MATERIALIZED VIEW gold_service_volume
CLUSTER BY (event_date, service_name)
COMMENT 'Daily OTEL log volume by service, namespace and severity.'
AS
SELECT
  event_date,
  service_name,
  namespace,
  deployment,
  severity_text,
  COUNT(*) AS event_count,
  SUM(CASE WHEN is_error THEN 1 ELSE 0 END) AS error_count
FROM silver_otel_logs
GROUP BY event_date, service_name, namespace, deployment, severity_text;
