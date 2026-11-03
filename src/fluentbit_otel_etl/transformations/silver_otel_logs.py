"""Silver — flatten Zerobus OTEL logs into typed, client-aware support events.

Bronze is the standalone managed table populated by Fluent Bit → Zerobus OTLP gRPC
(accessdemo.fluentbit.helix_otel_logs). This pipeline does not own bronze.
"""
from pyspark import pipelines as dp
from pyspark.sql import functions as F

BRONZE_TABLE = spark.conf.get("otel.bronze_table")
# UC functions created by sql/governance_functions.sql before the first pipeline update.
GOV = f'{spark.conf.get("helix.catalog")}.{spark.conf.get("helix.schema")}'

SILVER_SCHEMA = f"""
  record_id STRING NOT NULL COMMENT 'Unique log record id (dedup key; Zerobus is at-least-once)',
  event_time TIMESTAMP COMMENT 'Source event time from the application (simulated timeline)',
  event_date DATE COMMENT 'Date of event_time',
  ingest_time TIMESTAMP COMMENT 'Time the record was landed by Fluent Bit via Zerobus',
  client_id STRING COMMENT 'Helix client (pharma / CRO tenant) id',
  client_name STRING COMMENT 'Helix client display name',
  site_id STRING COMMENT 'Clinical site id within the client',
  study_id STRING MASK {GOV}.mask_study_id COMMENT 'Clinical study protocol id (client-confidential, masked)',
  user_email STRING MASK {GOV}.mask_email COMMENT 'End-user (site coordinator) email (PII, masked)',
  service_name STRING COMMENT 'Kubernetes application / OTEL service.name',
  namespace STRING COMMENT 'Kubernetes namespace',
  deployment STRING COMMENT 'Kubernetes deployment',
  severity_text STRING COMMENT 'ERROR, WARN, INFO or DEBUG',
  severity_number STRING COMMENT 'OTEL severity number',
  trace_id STRING COMMENT 'OTEL trace id',
  span_id STRING COMMENT 'OTEL span id',
  body_text STRING COMMENT 'Raw log message',
  error_signature STRING COMMENT 'Normalized message phrase used to group errors',
  latency_ms DOUBLE COMMENT 'Request latency in milliseconds',
  http_status INT COMMENT 'HTTP status code',
  http_method STRING COMMENT 'HTTP method',
  url_path STRING COMMENT 'Request path',
  is_error BOOLEAN COMMENT 'severity_text = ERROR'
"""


def _vget(col: str, path: str, typ: str = "string"):
    # Double any SQL single quotes so paths like $["service.name"] stay valid.
    sql_path = path.replace("'", "''")
    return F.expr(f"try_variant_get({col}, '{sql_path}', '{typ}')")


def _attr(key: str, typ: str = "string"):
    return _vget("attributes", f'$["{key}"]', typ)


@dp.table(
    name="silver_otel_logs",
    comment=(
        "Typed Helix Clinical Cloud application log events: client, site, study, end user, "
        "latency, severity, HTTP fields and error signature. Deduplicated on record_id."
    ),
    cluster_by=["event_time", "client_id"],
    schema=SILVER_SCHEMA,
    row_filter=f"ROW FILTER {GOV}.client_isolation_filter ON (client_id)",
    table_properties={
        "delta.enableRowTracking": "true",
        "delta.enableChangeDataFeed": "true",
    },
)
@dp.expect_or_drop("valid_record_id", "record_id IS NOT NULL")
@dp.expect("valid_time", "event_time IS NOT NULL")
@dp.expect("valid_service", "service_name IS NOT NULL")
@dp.expect("valid_client", "client_id IS NOT NULL")
@dp.expect("valid_sev", "severity_text IN ('ERROR','WARN','INFO','DEBUG')")
def silver_otel_logs():
    src = spark.readStream.option("skipChangeCommits", "true").table(BRONZE_TABLE)
    body_text = F.coalesce(
        F.expr("try_variant_get(body, '$', 'string')"),
        F.col("body").cast("string"),
    )
    service = F.coalesce(
        F.col("service_name"),
        _vget("resource.attributes", "$.service.name"),
        _attr("service.name"),
    )
    severity = F.upper(F.coalesce(F.col("severity_text"), _attr("SeverityText")))
    source_ns = _attr("Timestamp", "bigint")
    event_time = F.coalesce(
        F.timestamp_micros(F.floor(source_ns / F.lit(1000)).cast("bigint")),
        F.col("time"),
    )
    return (
        src.withColumn("body_text", body_text)
        .withColumn("record_id", F.coalesce(F.col("record_id"), _attr("record_id")))
        .withColumn("service_name", service)
        .withColumn("severity_text", severity)
        .withColumn("ingest_time", F.col("time"))
        .withColumn("event_time", event_time)
        .withColumn("event_date", F.to_date(F.col("event_time")))
        .withColumn("client_id", _attr("helix.client_id"))
        .withColumn("client_name", _attr("helix.client_name"))
        .withColumn("site_id", _attr("helix.site_id"))
        .withColumn("study_id", _attr("helix.study_id"))
        .withColumn("user_email", _attr("enduser.id"))
        .withColumn("latency_ms", _attr("latency_ms", "double"))
        .withColumn("http_status", _attr("http.status_code", "int"))
        .withColumn("http_method", _attr("http.method"))
        .withColumn("url_path", _attr("url.path"))
        .withColumn("namespace", _attr("k8s.namespace.name"))
        .withColumn("deployment", F.coalesce(_attr("deployment"), F.col("service_name")))
        .withColumn(
            "error_signature",
            F.coalesce(
                F.nullif(F.regexp_extract("body_text", r"^\S+ \S+ \d{3} (.*?) client=", 1), F.lit("")),
                F.lit("other"),
            ),
        )
        .withColumn("is_error", F.col("severity_text") == F.lit("ERROR"))
        .withWatermark("ingest_time", "10 minutes")
        .dropDuplicatesWithinWatermark(["record_id"])
        .select(
            "record_id",
            "event_time",
            "event_date",
            "ingest_time",
            "client_id",
            "client_name",
            "site_id",
            "study_id",
            "user_email",
            "service_name",
            "namespace",
            "deployment",
            "severity_text",
            "severity_number",
            "trace_id",
            "span_id",
            "body_text",
            "error_signature",
            "latency_ms",
            "http_status",
            "http_method",
            "url_path",
            "is_error",
        )
    )
