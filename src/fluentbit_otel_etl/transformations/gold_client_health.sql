CREATE OR REFRESH MATERIALIZED VIEW gold_client_health
CLUSTER BY (window_start, client_id)
COMMENT 'Client health in 5-minute windows per client, site and service: volume, error/warn rate, latency percentiles, top error signature. Feature table for the anomaly model and source for Lakebase serving.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
AS
WITH base AS (
  SELECT
    window(event_time, '5 minutes').start AS window_start,
    client_id,
    client_name,
    site_id,
    service_name,
    severity_text,
    error_signature,
    latency_ms
  FROM silver_otel_logs
  WHERE client_id IS NOT NULL
),
agg AS (
  SELECT
    window_start,
    client_id,
    client_name,
    site_id,
    service_name,
    COUNT(*) AS event_count,
    SUM(CASE WHEN severity_text = 'ERROR' THEN 1 ELSE 0 END) AS error_count,
    SUM(CASE WHEN severity_text = 'WARN' THEN 1 ELSE 0 END) AS warn_count,
    percentile_approx(latency_ms, 0.5) AS p50_latency_ms,
    percentile_approx(latency_ms, 0.95) AS p95_latency_ms
  FROM base
  GROUP BY window_start, client_id, client_name, site_id, service_name
),
sig AS (
  SELECT window_start, client_id, site_id, service_name, error_signature AS top_error_signature
  FROM (
    SELECT
      window_start, client_id, site_id, service_name, error_signature,
      ROW_NUMBER() OVER (
        PARTITION BY window_start, client_id, site_id, service_name
        ORDER BY COUNT(*) DESC, error_signature
      ) AS rn
    FROM base
    WHERE severity_text IN ('ERROR', 'WARN')
    GROUP BY window_start, client_id, site_id, service_name, error_signature
  )
  WHERE rn = 1
)
SELECT
  concat_ws('|', date_format(a.window_start, 'yyyy-MM-dd HH:mm'), a.client_id, a.site_id, a.service_name) AS health_key,
  a.window_start,
  a.client_id,
  a.client_name,
  a.site_id,
  a.service_name,
  a.event_count,
  a.error_count,
  a.warn_count,
  ROUND(a.error_count / a.event_count, 4) AS error_rate,
  ROUND(a.warn_count / a.event_count, 4) AS warn_rate,
  ROUND(a.p50_latency_ms, 1) AS p50_latency_ms,
  ROUND(a.p95_latency_ms, 1) AS p95_latency_ms,
  s.top_error_signature
FROM agg a
LEFT JOIN sig s
  ON a.window_start = s.window_start
 AND a.client_id = s.client_id
 AND a.site_id = s.site_id
 AND a.service_name = s.service_name;
