# Lakeflow ingest + Spark Declarative Pipeline evidence

Bronze `accessdemo.fluentbit.helix_otel_logs` is written by Fluent Bit over OTLP gRPC to Zerobus (see `01_ingest_load_test.log`). Pipeline `52163865-cae0-4f16-8447-d653b2daa809` (serverless, triggered) builds silver and gold in `accessdemo.dev_jesus_zaragoza_helix_support`.

### Rows per layer

```sql
SELECT 'bronze' AS layer, 'accessdemo.fluentbit.helix_otel_logs' AS table_name, count(*) AS row_count, count(DISTINCT coalesce(record_id, attributes:record_id::string)) AS distinct_record_ids FROM accessdemo.fluentbit.helix_otel_logs
UNION ALL SELECT 'silver', 'silver_otel_logs', count(*), count(DISTINCT record_id) FROM accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs
UNION ALL SELECT 'gold', 'gold_client_health', count(*), NULL FROM accessdemo.dev_jesus_zaragoza_helix_support.gold_client_health
UNION ALL SELECT 'gold', 'gold_incident_summary', count(*), NULL FROM accessdemo.dev_jesus_zaragoza_helix_support.gold_incident_summary
UNION ALL SELECT 'gold', 'gold_error_signatures', count(*), NULL FROM accessdemo.dev_jesus_zaragoza_helix_support.gold_error_signatures
UNION ALL SELECT 'gold', 'gold_service_volume', count(*), NULL FROM accessdemo.dev_jesus_zaragoza_helix_support.gold_service_volume
UNION ALL SELECT 'ml', 'gold_client_anomalies', count(*), NULL FROM accessdemo.dev_jesus_zaragoza_helix_support.gold_client_anomalies
UNION ALL SELECT 'genai', 'gold_incident_briefs', count(*), NULL FROM accessdemo.dev_jesus_zaragoza_helix_support.gold_incident_briefs
```

| layer | table_name | row_count | distinct_record_ids |
|---|---|---|---|
| bronze | accessdemo.fluentbit.helix_otel_logs | 1637120 | 1637120 |
| silver | silver_otel_logs | 1440832 | 1440832 |
| gold | gold_client_health | 26010 |  |
| gold | gold_incident_summary | 60 |  |
| gold | gold_error_signatures | 182 |  |
| gold | gold_service_volume | 48 |  |
| ml | gold_client_anomalies | 130 |  |
| genai | gold_incident_briefs | 10 |  |

### Silver coverage by client (wingtip-gx hidden by row filter)

```sql
SELECT client_id, count(*) AS events, min(event_time) AS first_event, max(event_time) AS last_event,
       round(avg(CASE WHEN severity_text = 'ERROR' THEN 1 ELSE 0 END) * 100, 2) AS error_pct
FROM accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs GROUP BY client_id ORDER BY client_id
```

| client_id | events | first_event | last_event | error_pct |
|---|---|---|---|---|
| adatum-clin | 229502 | 2026-11-02T00:13:22.766Z | 2026-11-03T00:13:21.564Z | 1.48 |
| contoso-tx | 294057 | 2026-11-02T00:13:22.766Z | 2026-11-03T00:13:21.564Z | 1.58 |
| fabrikam-cro | 360332 | 2026-11-02T00:13:22.766Z | 2026-11-03T00:13:21.564Z | 1.69 |
| northwind-bio | 327302 | 2026-11-02T00:13:22.766Z | 2026-11-03T00:13:21.564Z | 1.54 |
| tailspin-onc | 229639 | 2026-11-02T00:13:22.766Z | 2026-11-03T00:13:21.564Z | 1.51 |

### Top 5-minute error windows in gold_client_health

```sql
SELECT window_start, client_name, site_id, service_name, event_count, error_count, round(error_rate * 100, 1) AS error_pct,
       p95_latency_ms, top_error_signature
FROM accessdemo.dev_jesus_zaragoza_helix_support.gold_client_health WHERE event_count >= 20 ORDER BY error_rate DESC LIMIT 10
```

| window_start | client_name | site_id | service_name | event_count | error_count | error_pct | p95_latency_ms | top_error_signature |
|---|---|---|---|---|---|---|---|---|
| 2026-11-02T19:00:00.000Z | Fabrikam CRO | site-204 | trial-upload-api | 74 | 33 | 44.6 | 2729.8 | upload timeout |
| 2026-11-02T18:45:00.000Z | Fabrikam CRO | site-204 | trial-upload-api | 65 | 28 | 43.1 | 2845.9 | DICOM association rejected |
| 2026-11-02T09:45:00.000Z | Contoso Therapeutics | site-113 | econsent-web | 47 | 19 | 40.4 | 1048.7 | e-signature provider 503 |
| 2026-11-02T17:45:00.000Z | Fabrikam CRO | site-204 | dicom-router | 61 | 24 | 39.3 | 1117.8 | DICOM association rejected |
| 2026-11-02T18:55:00.000Z | Fabrikam CRO | site-204 | dicom-router | 44 | 17 | 38.6 | 997.3 | upload timeout |
| 2026-11-02T18:30:00.000Z | Fabrikam CRO | site-204 | dicom-router | 58 | 22 | 37.9 | 1023.3 | association retry |
| 2026-11-02T18:25:00.000Z | Fabrikam CRO | site-204 | trial-upload-api | 45 | 17 | 37.8 | 2703.6 | DICOM association rejected |
| 2026-11-02T18:35:00.000Z | Fabrikam CRO | site-204 | dicom-router | 53 | 20 | 37.7 | 1081.7 | DICOM association rejected |
| 2026-11-02T18:30:00.000Z | Fabrikam CRO | site-204 | trial-upload-api | 64 | 24 | 37.5 | 2844.6 | DICOM association rejected |
| 2026-11-02T18:20:00.000Z | Fabrikam CRO | site-204 | trial-upload-api | 59 | 22 | 37.3 | 2964.4 | slow upload chunk |

### SDP event log: data-quality expectations across all updates

```sql
SELECT origin.flow_name AS flow, e.name AS expectation, sum(e.passed_records) AS passed, sum(e.failed_records) AS failed
FROM event_log('52163865-cae0-4f16-8447-d653b2daa809')
LATERAL VIEW explode(from_json(details:flow_progress.data_quality.expectations,
  'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) x AS e
WHERE event_type = 'flow_progress' AND details:flow_progress.data_quality.expectations IS NOT NULL
GROUP BY 1, 2
```

| flow | expectation | passed | failed |
|---|---|---|---|
| accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs | valid_time | 1637120 | 0 |
| accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs | valid_service | 1637120 | 0 |
| accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs | valid_record_id | 1637120 | 0 |
| accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs | valid_sev | 1637120 | 0 |
| accessdemo.dev_jesus_zaragoza_helix_support.silver_otel_logs | valid_client | 1637120 | 0 |

### SDP event log: recent updates

```sql
SELECT timestamp, origin.update_id, details:update_progress.state::string AS state
FROM event_log('52163865-cae0-4f16-8447-d653b2daa809')
WHERE event_type = 'update_progress' AND details:update_progress.state::string IN ('COMPLETED', 'FAILED', 'CANCELED')
ORDER BY timestamp DESC LIMIT 8
```

| timestamp | update_id | state |
|---|---|---|
| 2026-11-03T00:56:47.627Z | 9e646d99-b6ab-4a8b-a4ae-805349ffa0d0 | COMPLETED |
| 2026-11-03T00:27:07.122Z | 92c04719-00be-4875-941b-7acf907d0a15 | COMPLETED |

