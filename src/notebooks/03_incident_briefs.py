# %% [markdown]
# # 03 · AI incident briefs with `ai_query`
#
# Turns model-flagged windows into support-ready incident briefs:
#
# 1. Group anomalous 5-minute windows from `gold_client_anomalies` into incidents
#    (same client, gap ≤ 15 minutes).
# 2. Attach evidence from silver: affected sites and services, top error signatures,
#    peak error rate and p95 latency, sample log lines.
# 3. Call a Databricks-hosted foundation model with `ai_query` and a JSON response schema to
#    produce: summary, likely cause, severity, next step, and a draft client-facing reply.
# 4. Persist to `gold_incident_briefs` (served through Lakebase) and log prompt/response
#    to `gold_brief_inference` so the ML→GenAI loop is auditable.

# %%
import json
import os

try:
    dbutils  # noqa: F821
    IN_DATABRICKS = True
except NameError:
    IN_DATABRICKS = False


def param(name: str, default: str) -> str:
    if IN_DATABRICKS:
        dbutils.widgets.text(name, default)  # noqa: F821
        return dbutils.widgets.get(name)  # noqa: F821
    return os.environ.get(name.upper(), default)


if not IN_DATABRICKS:
    from databricks.connect import DatabricksSession

    spark = DatabricksSession.builder.profile(os.environ.get("DATABRICKS_CONFIG_PROFILE", "fevm-ai")).serverless().getOrCreate()

CATALOG = param("catalog", "accessdemo")
SCHEMA = param("schema", "dev_jesus_zaragoza_helix_support")
LLM = param("llm_endpoint", "databricks-claude-sonnet-4-6")
FQ = f"{CATALOG}.{SCHEMA}"
print(f"schema={FQ} llm={LLM}")

# %% [markdown]
# ## 1–2. Build incident context

# %%
spark.sql(f"""
CREATE OR REPLACE TEMP VIEW incident_context AS
WITH a AS (
  SELECT *,
         CASE WHEN window_start - LAG(window_start) OVER (PARTITION BY client_id ORDER BY window_start)
                   <= INTERVAL 15 MINUTES THEN 0 ELSE 1 END AS new_incident
  FROM {FQ}.gold_client_anomalies
),
g AS (
  SELECT *, SUM(new_incident) OVER (PARTITION BY client_id ORDER BY window_start) AS seq FROM a
),
inc AS (
  SELECT
    concat(client_id, '-', date_format(MIN(window_start), 'yyyyMMdd-HHmm')) AS incident_id,
    client_id, ANY_VALUE(client_name) AS client_name,
    MIN(window_start) AS started_at,
    MAX(window_start) + INTERVAL 5 MINUTES AS ended_at,
    COUNT(*) AS anomalous_windows,
    array_sort(collect_set(site_id)) AS sites,
    array_sort(collect_set(service_name)) AS services,
    ROUND(MAX(error_rate), 3) AS peak_error_rate,
    ROUND(MAX(p95_latency_ms), 0) AS peak_p95_latency_ms,
    ROUND(MAX(anomaly_score), 3) AS max_anomaly_score,
    SUM(event_count) AS events_in_scope,
    SUM(error_count) AS errors_in_scope
  FROM g GROUP BY client_id, seq
),
sig AS (
  SELECT i.incident_id, s.error_signature, COUNT(*) AS n,
         ANY_VALUE(s.body_text) AS sample_line
  FROM inc i
  JOIN {FQ}.silver_otel_logs s
    ON s.client_id = i.client_id
   AND s.event_time >= i.started_at AND s.event_time < i.ended_at
   AND array_contains(i.sites, s.site_id) AND array_contains(i.services, s.service_name)
   AND s.severity_text IN ('ERROR', 'WARN')
  GROUP BY i.incident_id, s.error_signature
),
sig_agg AS (
  SELECT incident_id,
         to_json(slice(array_sort(
           collect_list(named_struct('n', n, 'signature', error_signature, 'sample', sample_line)),
           (l, r) -> CAST(r.n - l.n AS INT)), 1, 4)) AS top_signatures_json
  FROM sig GROUP BY incident_id
)
SELECT inc.*, sig_agg.top_signatures_json
FROM inc LEFT JOIN sig_agg USING (incident_id)
WHERE anomalous_windows >= 2 OR peak_error_rate >= 0.15
""")
ctx = spark.table("incident_context").orderBy("started_at")
print(f"{ctx.count()} incidents to brief")
print(ctx.drop("top_signatures_json").toPandas().to_string(index=False))

# %% [markdown]
# ## 3. Generate briefs with `ai_query` (structured JSON output)

# %%
response_format = json.dumps({
    "type": "json_schema",
    "json_schema": {
        "name": "incident_brief",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "likely_cause": {"type": "string"},
                "severity": {"type": "string", "enum": ["SEV1", "SEV2", "SEV3"]},
                "recommended_next_step": {"type": "string"},
                "client_reply": {"type": "string"},
            },
            "required": ["summary", "likely_cause", "severity", "recommended_next_step", "client_reply"],
            "additionalProperties": False,
        },
    },
})

prompt_header = (
    "You are a senior support engineer at Helix Clinical Cloud, a SaaS vendor that runs "
    "clinical-trial applications (imaging archive, DICOM router, trial-data upload, eConsent) "
    "for pharma and CRO clients. Write an incident brief from the telemetry below. "
    "summary: 2 sentences, plain English, what the client experienced. "
    "likely_cause: 1-2 sentences grounded only in the evidence. "
    "severity: SEV1 if error rate >= 25% on a clinical data path, SEV2 if >= 10% or p95 latency "
    "is far above normal, else SEV3. recommended_next_step: one concrete action for the on-call "
    "engineer. client_reply: a short, calm message to the client's site coordinator; no internal "
    "hostnames, no blame, include that the team is monitoring. Telemetry: "
).replace("'", "\\'")

spark.sql(f"""
CREATE OR REPLACE TEMP VIEW brief_gen AS
WITH prompts AS (
  SELECT *,
    concat('{prompt_header}', to_json(named_struct(
      'client', client_name, 'sites', sites, 'services', services,
      'started_at', started_at, 'ended_at', ended_at,
      'anomalous_5min_windows', anomalous_windows,
      'peak_error_rate', peak_error_rate, 'peak_p95_latency_ms', peak_p95_latency_ms,
      'events', events_in_scope, 'errors', errors_in_scope,
      'top_error_signatures', top_signatures_json))) AS prompt
  FROM incident_context
)
SELECT *, ai_query('{LLM}', prompt, responseFormat => '{response_format}') AS brief_json
FROM prompts
""")
spark.sql(f"""
CREATE OR REPLACE TABLE {FQ}.gold_incident_briefs
COMMENT 'AI-generated incident briefs ({LLM} via ai_query) for model-detected client incidents. Input windows come from gold_client_anomalies.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
AS
SELECT
  incident_id, client_id, client_name, started_at, ended_at, anomalous_windows,
  array_join(sites, ', ') AS sites, array_join(services, ', ') AS services,
  peak_error_rate, peak_p95_latency_ms, max_anomaly_score, events_in_scope, errors_in_scope,
  top_signatures_json,
  brief_json:summary::string AS summary,
  brief_json:likely_cause::string AS likely_cause,
  brief_json:severity::string AS severity,
  brief_json:recommended_next_step::string AS recommended_next_step,
  brief_json:client_reply::string AS client_reply,
  '{LLM}' AS model_endpoint,
  current_timestamp() AS generated_at
FROM brief_gen
""")
spark.sql(f"""
CREATE OR REPLACE TABLE {FQ}.gold_brief_inference
COMMENT 'Logged ai_query inputs/outputs. Each row is one incident brief; features come from gold_client_anomalies.'
TBLPROPERTIES ('delta.enableChangeDataFeed' = 'true')
AS
SELECT
  incident_id, client_id, client_name, anomalous_windows, max_anomaly_score, peak_error_rate,
  prompt,
  brief_json AS response_json,
  '{LLM}' AS model_endpoint,
  current_timestamp() AS generated_at
FROM brief_gen
""")
print(f"wrote {spark.table(f'{FQ}.gold_incident_briefs').count()} briefs to {FQ}.gold_incident_briefs")
inf = spark.table(f"{FQ}.gold_brief_inference")
print(f"wrote {inf.count()} inference rows to {FQ}.gold_brief_inference")
print(inf.select("incident_id", "anomalous_windows", "max_anomaly_score", "model_endpoint").toPandas().to_string(index=False))

# %% [markdown]
# ## 4. Generated briefs (real model output)

# %%
for r in spark.table(f"{FQ}.gold_incident_briefs").orderBy("started_at").collect():
    print("=" * 100)
    print(f"{r.incident_id}  [{r.severity}]  {r.client_name}  sites={r.sites}  services={r.services}")
    print(f"window {r.started_at} -> {r.ended_at}  peak_error_rate={r.peak_error_rate}  "
          f"peak_p95={r.peak_p95_latency_ms} ms  windows={r.anomalous_windows}")
    print(f"SUMMARY      {r.summary}")
    print(f"LIKELY CAUSE {r.likely_cause}")
    print(f"NEXT STEP    {r.recommended_next_step}")
    print(f"CLIENT REPLY {r.client_reply}")
