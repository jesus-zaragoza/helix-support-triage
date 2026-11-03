-- Official Zerobus OTEL logs schema.
-- Docs: https://docs.databricks.com/aws/en/ingestion/opentelemetry/configure
-- Target: accessdemo.fluentbit.helix_otel_logs (profile fevm-ai)

-- Requires schema accessdemo.fluentbit to exist. One statement per file (CLI query limitation).

CREATE TABLE IF NOT EXISTS accessdemo.fluentbit.helix_otel_logs (
  record_id STRING,
  time TIMESTAMP,
  date DATE,
  service_name STRING,
  event_name STRING,
  trace_id STRING,
  span_id STRING,
  time_unix_nano LONG,
  observed_time_unix_nano LONG,
  severity_number STRING,
  severity_text STRING,
  body VARIANT,
  attributes VARIANT,
  dropped_attributes_count INT,
  flags INT,
  resource STRUCT<
    attributes: VARIANT,
    dropped_attributes_count: INT
  >,
  resource_schema_url STRING,
  instrumentation_scope STRUCT<
    name: STRING,
    version: STRING,
    attributes: VARIANT,
    dropped_attributes_count: INT
  >,
  log_schema_url STRING
) USING DELTA
CLUSTER BY (time, service_name)
TBLPROPERTIES (
  'otel.schemaVersion' = 'v2',
  'delta.checkpointPolicy' = 'classic',
  'delta.enableVariantShredding' = 'true',
  'delta.feature.variantShredding' = 'supported',
  'delta.feature.variantType' = 'supported'
);
