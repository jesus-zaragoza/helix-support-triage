#!/usr/bin/env python3
"""Query the workspace and write text evidence for the ingest, pipeline, ML and Gen AI stages.

Writes:
  evidence/02_pipeline_and_tables.md  row counts per layer, SDP event log (expectations, flow progress)
  evidence/03_ml_and_genai.md         MLflow champion metrics, anomalies vs injected incidents, AI briefs
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import Disposition, Format

ROOT = Path(__file__).resolve().parents[1]


class Q:
    def __init__(self, w: WorkspaceClient, warehouse: str):
        self.w, self.wh = w, warehouse

    def md(self, title: str, sql: str, max_rows: int = 30, width: int = 160) -> list[str]:
        r = self.w.statement_execution.execute_statement(
            statement=sql, warehouse_id=self.wh, wait_timeout="50s",
            disposition=Disposition.INLINE, format=Format.JSON_ARRAY)
        while r.status.state.value in ("PENDING", "RUNNING"):
            r = self.w.statement_execution.get_statement(r.statement_id)
        if r.status.state.value != "SUCCEEDED":
            raise RuntimeError(f"{title}: {r.status.error.message if r.status.error else r.status.state}")
        cols = [c.name for c in r.manifest.schema.columns]
        rows = (r.result.data_array or [])[:max_rows] if r.result else []
        cell = lambda v: "" if v is None else str(v).replace("|", "\\|").replace("\n", " ")[:width]  # noqa: E731
        return [f"### {title}", "", "```sql", sql.strip(), "```", "",
                "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols),
                *["| " + " | ".join(cell(v) for v in row) + " |" for row in rows], ""]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", default="accessdemo")
    p.add_argument("--schema", default="dev_jesus_zaragoza_helix_support")
    p.add_argument("--bronze", default="accessdemo.fluentbit.helix_otel_logs")
    p.add_argument("--pipeline-id", default="52163865-cae0-4f16-8447-d653b2daa809")
    p.add_argument("--warehouse", default="2a82c8f87ef698a1")
    p.add_argument("--profile", default=os.environ.get("DATABRICKS_CONFIG_PROFILE", "fevm-ai"))
    args = p.parse_args()
    w = WorkspaceClient(profile=args.profile)
    q = Q(w, args.warehouse)
    fq = f"{args.catalog}.{args.schema}"

    pipe = ["# Lakeflow ingest + Spark Declarative Pipeline evidence", "",
            f"Bronze `{args.bronze}` is written by Fluent Bit over OTLP gRPC to Zerobus (see `01_ingest_load_test.log`). "
            f"Pipeline `{args.pipeline_id}` (serverless, triggered) builds silver and gold in `{fq}`.", ""]
    pipe += q.md("Rows per layer", f"""
SELECT 'bronze' AS layer, '{args.bronze}' AS table_name, count(*) AS row_count, count(DISTINCT coalesce(record_id, attributes:record_id::string)) AS distinct_record_ids FROM {args.bronze}
UNION ALL SELECT 'silver', 'silver_otel_logs', count(*), count(DISTINCT record_id) FROM {fq}.silver_otel_logs
UNION ALL SELECT 'gold', 'gold_client_health', count(*), NULL FROM {fq}.gold_client_health
UNION ALL SELECT 'gold', 'gold_incident_summary', count(*), NULL FROM {fq}.gold_incident_summary
UNION ALL SELECT 'gold', 'gold_error_signatures', count(*), NULL FROM {fq}.gold_error_signatures
UNION ALL SELECT 'gold', 'gold_service_volume', count(*), NULL FROM {fq}.gold_service_volume
UNION ALL SELECT 'ml', 'gold_client_anomalies', count(*), NULL FROM {fq}.gold_client_anomalies
UNION ALL SELECT 'genai', 'gold_incident_briefs', count(*), NULL FROM {fq}.gold_incident_briefs""")
    pipe += q.md("Silver coverage by client (wingtip-gx hidden by row filter)", f"""
SELECT client_id, count(*) AS events, min(event_time) AS first_event, max(event_time) AS last_event,
       round(avg(CASE WHEN severity_text = 'ERROR' THEN 1 ELSE 0 END) * 100, 2) AS error_pct
FROM {fq}.silver_otel_logs GROUP BY client_id ORDER BY client_id""")
    pipe += q.md("Top 5-minute error windows in gold_client_health", f"""
SELECT window_start, client_name, site_id, service_name, event_count, error_count, round(error_rate * 100, 1) AS error_pct,
       p95_latency_ms, top_error_signature
FROM {fq}.gold_client_health WHERE event_count >= 20 ORDER BY error_rate DESC LIMIT 10""")
    pipe += q.md("SDP event log: data-quality expectations across all updates", f"""
SELECT origin.flow_name AS flow, e.name AS expectation, sum(e.passed_records) AS passed, sum(e.failed_records) AS failed
FROM event_log('{args.pipeline_id}')
LATERAL VIEW explode(from_json(details:flow_progress.data_quality.expectations,
  'array<struct<name:string,dataset:string,passed_records:bigint,failed_records:bigint>>')) x AS e
WHERE event_type = 'flow_progress' AND details:flow_progress.data_quality.expectations IS NOT NULL
GROUP BY 1, 2""")
    pipe += q.md("SDP event log: recent updates", f"""
SELECT timestamp, origin.update_id, details:update_progress.state::string AS state
FROM event_log('{args.pipeline_id}')
WHERE event_type = 'update_progress' AND details:update_progress.state::string IN ('COMPLETED', 'FAILED', 'CANCELED')
ORDER BY timestamp DESC LIMIT 8""")
    (ROOT / "evidence" / "02_pipeline_and_tables.md").write_text("\n".join(pipe) + "\n")
    print("wrote evidence/02_pipeline_and_tables.md")

    ml = ["# ML + Gen AI evidence", ""]
    mv = w.model_versions.get_by_alias(f"{fq}.client_anomaly_model", "champion")
    run = w.experiments.get_run(mv.run_id).run
    metrics = {m.key: round(m.value, 4) for m in (run.data.metrics or [])}
    params = {pp.key: pp.value for pp in (run.data.params or [])}
    ml += [f"### Registered model `{fq}.client_anomaly_model` @champion = version {mv.version}", "",
           f"MLflow run `{mv.run_id}`, status `{mv.status.value if mv.status else None}`.", "",
           "| metric | value |", "|---|---|", *[f"| {k} | {v} |" for k, v in sorted(metrics.items())], "",
           "| param | value |", "|---|---|", *[f"| {k} | {v} |" for k, v in sorted(params.items())], ""]
    ml += q.md("Flagged windows per client vs injected incidents (src/config/incidents.json)", f"""
SELECT client_id, service_name, min(window_start) AS first_flag, max(window_start) AS last_flag, count(*) AS flagged_windows,
       round(max(error_rate) * 100, 1) AS peak_error_pct, max(p95_latency_ms) AS peak_p95_ms
FROM {fq}.gold_client_anomalies GROUP BY client_id, service_name HAVING count(*) >= 3 ORDER BY flagged_windows DESC""", 20)
    ml += q.md("AI incident briefs (ai_query, structured JSON output)", f"""
SELECT incident_id, client_name, severity, started_at, ended_at, services, summary, likely_cause, recommended_next_step, client_reply, model_endpoint
FROM {fq}.gold_incident_briefs ORDER BY severity, started_at""", 20, 600)
    (ROOT / "evidence" / "03_ml_and_genai.md").write_text("\n".join(ml) + "\n")
    print("wrote evidence/03_ml_and_genai.md")


if __name__ == "__main__":
    main()
