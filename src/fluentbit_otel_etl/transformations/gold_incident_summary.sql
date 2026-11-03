CREATE OR REFRESH MATERIALIZED VIEW gold_incident_summary
CLUSTER BY (event_date, client_id)
COMMENT 'Daily per-client, per-service scoreboard with error rate, p95 latency and top error signature.'
AS
WITH base AS (
  SELECT
    event_date,
    client_id,
    client_name,
    service_name,
    namespace,
    COUNT(*) AS event_count,
    SUM(CASE WHEN is_error THEN 1 ELSE 0 END) AS error_count,
    percentile_approx(latency_ms, 0.95) AS p95_latency_ms
  FROM silver_otel_logs
  GROUP BY event_date, client_id, client_name, service_name, namespace
),
sig AS (
  SELECT event_date, client_id, service_name, error_signature AS top_error_signature
  FROM (
    SELECT
      event_date,
      client_id,
      service_name,
      error_signature,
      ROW_NUMBER() OVER (
        PARTITION BY event_date, client_id, service_name
        ORDER BY COUNT(*) DESC, error_signature
      ) AS rn
    FROM silver_otel_logs
    WHERE is_error
    GROUP BY event_date, client_id, service_name, error_signature
  )
  WHERE rn = 1
)
SELECT
  b.event_date,
  b.client_id,
  b.client_name,
  b.service_name,
  b.namespace,
  b.event_count,
  b.error_count,
  ROUND(b.error_count / NULLIF(b.event_count, 0), 4) AS error_rate,
  ROUND(b.p95_latency_ms, 1) AS p95_latency_ms,
  s.top_error_signature
FROM base b
LEFT JOIN sig s
  ON b.event_date = s.event_date AND b.client_id = s.client_id AND b.service_name = s.service_name;
