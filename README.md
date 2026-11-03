# Helix Support Console: life-sciences client log triage on Databricks

**Open these first (all text — no notebooks required):** [`SOURCE_MAP.md`](SOURCE_MAP.md)

| Layer | Code | Run log |
|---|---|---|
| Lakeflow ingest (Zerobus OTLP gRPC) | `fluent-bit.yaml`, `sql/create_bronze.sql` | [`evidence/01_ingest_load_test.log`](evidence/01_ingest_load_test.log) |
| Lakeflow SDP (silver + gold) | `src/fluentbit_otel_etl/transformations/`, `resources/fluentbit_otel_etl.pipeline.yml` | [`evidence/02_pipeline_and_tables.md`](evidence/02_pipeline_and_tables.md) |
| Lakebase (sync + triage notes) | `src/lakebase/sync.py`, `sql/triage_notes.sql`, `src/app/app.py` | [`evidence/04_lakebase_serving.md`](evidence/04_lakebase_serving.md), [`evidence/notebooks/04_lakebase_sync.md`](evidence/notebooks/04_lakebase_sync.md) |
| ML → GenAI | `src/notebooks/02_train_anomaly_model.py` → `src/notebooks/03_incident_briefs.py` | [`evidence/notebooks/02_train_anomaly_model.md`](evidence/notebooks/02_train_anomaly_model.md), [`evidence/notebooks/03_incident_briefs.md`](evidence/notebooks/03_incident_briefs.md) |

An end-to-end prototype for a life-sciences SaaS vendor. **Helix Clinical Cloud** (fictional) runs imaging-archive, DICOM routing, trial-data upload and eConsent apps on Kubernetes for pharma and CRO clients. Its Support team could not see application logs, so every "site X's upload failed" ticket escalated to engineering.

**Outcome:** Support answers client tickets from one app in minutes. The app shows client health, ML-flagged anomalies, an AI-written incident brief with a client reply, a Genie box for follow-up questions, and triage notes saved to Lakebase.

> All clients, sites, studies, users and log lines are **synthetic**, produced by `scripts/generate_otel_logs.py`. No customer data is included.

- Business deck: [`deck/helix-support-triage.md`](deck/helix-support-triage.md) ([PDF](deck/helix-support-triage.pdf))
- Execution evidence: [`evidence/README.md`](evidence/README.md)
- Certification form: select the **`submission/`** folder (text-only pack), not this workspace root.
- Architecture deep-dive (Fluent Bit at scale, token broker, OTLP gRPC vs HTTP): [`docs/architecture.md`](docs/architecture.md)

Workspace used: `fevm-ai` (AWS us-east-1, serverless), catalog `accessdemo`, dev schema `dev_jesus_zaragoza_helix_support`.

## Architecture

```text
 synthetic K8s app logs ─▶ Fluent Bit 5.1 ──OTLP gRPC──▶ Lakeflow Connect: Zerobus ──▶ UC bronze (OTEL v2)
                                                                                          │
                                     Lakeflow Spark Declarative Pipeline (serverless, triggered)
                                                                                          ▼
                                   silver_otel_logs  (typed, deduped, column masks + client row filter)
                                                                                          ▼
                 gold_client_health · gold_incident_summary · gold_error_signatures · gold_service_volume
                       │                               │                                   │
            MLflow IsolationForest → gold_client_anomalies → ai_query → gold_incident_briefs
                                                                   └── gold_brief_inference (prompt/response log)
                                                                                         Genie Agent
                       │                               │                                   │
                       └──────── Lakebase synced tables (Postgres) ─────────┐              │
                                                                            ▼              ▼
                                         Databricks App "Helix Support Console" (FastAPI)
                                               └── writes support_app.triage_notes ─▶ Lakebase
```

The Lakeflow Job `helix_support_triage` runs these steps in order: pipeline refresh → governance → train and score → AI briefs → Lakebase sync. It's defined, together with the pipeline and the app, in a Declarative Automation Bundle (`databricks.yml`).

## Stage to artifact map

| Stage | Databricks capability | Code | Evidence |
|---|---|---|---|
| Ingest | Lakeflow Connect: **Zerobus** OTLP gRPC from Fluent Bit | `fluent-bit.yaml`, `scripts/run_load_test.sh`, `scripts/generate_otel_logs.py`, `scripts/mint_zerobus_token.py`, `sql/create_bronze.sql` | [`01_ingest_load_test.log`](evidence/01_ingest_load_test.log) |
| Transform | **Lakeflow Spark Declarative Pipelines** (silver + 4 gold) | `src/fluentbit_otel_etl/transformations/`, `resources/fluentbit_otel_etl.pipeline.yml` | [`02_pipeline_and_tables.md`](evidence/02_pipeline_and_tables.md) |
| Govern | **Unity Catalog**: masks, row filter, tags, comments, grants, lineage | `sql/governance_functions.sql`, `sql/governance.sql`, `src/notebooks/01_governance.py` | [`evidence/notebooks/01_governance.md`](evidence/notebooks/01_governance.md) |
| ML | **MLflow** + UC model registry (IsolationForest, alias `champion`) | `src/notebooks/02_train_anomaly_model.py`, `src/config/incidents.json` | [`evidence/notebooks/02_train_anomaly_model.md`](evidence/notebooks/02_train_anomaly_model.md), [`03_ml_and_genai.md`](evidence/03_ml_and_genai.md) |
| Gen AI | **AI Functions** `ai_query`; reads `gold_client_anomalies`; logs `gold_brief_inference` | `src/notebooks/03_incident_briefs.py` | [`evidence/notebooks/03_incident_briefs.md`](evidence/notebooks/03_incident_briefs.md), [`03_ml_and_genai.md`](evidence/03_ml_and_genai.md) |
| Serve | **Lakebase** Autoscaling: 3 synced tables + native `triage_notes` | `src/lakebase/sync.py`, `sql/triage_notes.sql`, `src/app/app.py` | [`evidence/notebooks/04_lakebase_sync.md`](evidence/notebooks/04_lakebase_sync.md), [`04_lakebase_serving.md`](evidence/04_lakebase_serving.md) |
| Orchestrate | **Lakeflow Jobs** in a bundle | `databricks.yml`, `resources/support_triage.job.yml` | [`05_job_run.md`](evidence/05_job_run.md) |
| Ask | **Genie Agent** (instructions, sample questions, trusted SQL, benchmarks) | `src/genie/space.json`, `scripts/create_genie_space.py` | [`06_genie_conversation.md`](evidence/06_genie_conversation.md) |
| Act | **Databricks Apps** (FastAPI; Lakebase, SQL warehouse and Genie resources) | `src/app/`, `resources/support_console.app.yml` | [`07_app_api.md`](evidence/07_app_api.md) |

## Synthetic scenario

The generator simulates 24 hours of traffic for 6 client tenants and 6 services, compressed into the run time. It injects 3 incidents (`src/config/incidents.json`), which are also the ML labels:

| Incident | Client / site | Services | Simulated time | Injected signal |
|---|---|---|---|---|
| `INC-UPLOAD-204` | Fabrikam CRO / site-204 | trial-upload-api, dicom-router | 17:30–19:00 | 35 % errors, 6× latency |
| `INC-ESIGN-503` | Contoso Therapeutics / all sites | econsent-web | 09:00–09:45 | 25 % errors (e-signature 503s), 3× latency |
| `INC-ARCHIVE-SLOW-101` | Northwind Bio / site-101 | imaging-archive | 03:00–03:30 | 40 % warnings ("S3 put slow"), 5× latency |

The sixth tenant, `wingtip-gx`, is an isolated client: its rows are in bronze but hidden from Support by a Unity Catalog row filter.

## Governance in Unity Catalog

- **Column masks** on `silver_otel_logs`: `user_email` shows `***@client.example` and `study_id` shows `FAB-***` unless the caller is in the `helix_support_analysts` account group.
- **Row filter** `client_isolation_filter(client_id)` hides the isolated tenant unless the caller is in `helix_wingtip_pod`.
- Masks and the filter are declared in the pipeline's table schema (SDP), so they survive full refreshes.
- **Tags** (within workspace tag policies): `domain`, `layer`, `contains_pii`, `data_classification`, `pii_category=email`, `serving=lakebase`.
- **Comments** on the schema, tables and columns.
- **Grants**: `account users` can read gold; the app service principal gets `USE CATALOG`, `USE SCHEMA` and `SELECT`.
- **Lineage** from `system.access.table_lineage`: silver → gold → ML and AI tables → Lakebase synced tables.

## How to run

Prerequisites:

- Fluent Bit 5.x on your `PATH`.
- The Databricks CLI (tested with v1.21), logged in with `databricks auth login --profile <profile>`.
- Python 3.11+ with the packages in `requirements-dev.txt`.
- A service principal for Zerobus, configured in `.env` (copy it from `.env.example`). It needs explicit `USE CATALOG`, `USE SCHEMA` and `SELECT`+`MODIFY` on the bronze table.

Never commit `.env` or `logs/.zerobus_token`.

```bash
# 0. bronze table (once)
./scripts/apply_bronze.sh

# 1. Ingest: 24 simulated hours in 10 minutes at 3 MB/s through Fluent Bit -> Zerobus
DURATION=600 MBPS=3 ./scripts/run_load_test.sh

# 2. Deploy pipeline, job and app (Lakebase project `helix-support` must exist)
databricks bundle deploy -t dev

# 3. Genie Agent (writes src/genie/space_id.txt; set var genie_space_id in databricks.yml, redeploy)
python scripts/create_genie_space.py --schema accessdemo.dev_<user>_helix_support --warehouse <warehouse-id> --ask

# 4. Run the whole chain: pipeline -> governance -> ML -> Gen AI -> Lakebase sync
databricks bundle run support_triage -t dev

# 5. Start the app, grant its service principal read access to the synced Postgres schema
databricks bundle run support_console -t dev
python scripts/lakebase_grant_and_verify.py --app helix-support-console

# 6. Capture text evidence
python scripts/capture_data_evidence.py
python scripts/capture_app_evidence.py
```

To run the notebooks locally with Databricks Connect (serverless) and keep their outputs, set `DATABRICKS_CONFIG_PROFILE` and run `jupyter nbconvert --to notebook --execute --inplace src/notebooks/0X_*.ipynb`. Each notebook reads job parameters from widgets when run as a job, and from environment variables when run locally.

## Repo layout

| Path | Role |
|---|---|
| `databricks.yml`, `resources/` | Bundle: schema, SDP pipeline, Lakeflow Job, Databricks App |
| `src/fluentbit_otel_etl/transformations/` | Silver (Python) and gold (SQL) pipeline code |
| `src/notebooks/` | Governance, ML training/scoring, AI briefs, Lakebase sync (committed with outputs) |
| `src/app/` | Support Console (FastAPI + single-page UI) |
| `src/genie/` | Genie space definition and id |
| `src/config/incidents.json` | Injected incidents (generator input and ML labels) |
| `sql/` | Bronze DDL, UC functions (masks/filter), tags/comments/grants |
| `scripts/` | Generator, load test, token mint, Genie create/ask, Lakebase grants, evidence capture |
| `samples/token-broker/` | Sample OAuth token broker for running Fluent Bit at fleet scale |
| `src/dashboard/otel_ingest.json` | Optional AI/BI ingest-operations dashboard |
| `deck/` | Business presentation (markdown + PDF) |
| `evidence/` | Text execution evidence |

## Known limits

- A laptop can't sustain production scale (about 48 k lines per second); the load test runs at 3 MB/s. `docs/architecture.md` covers DaemonSet sizing.
- The Zerobus token lasts one hour, and `run_load_test.sh` mints a new one per run. For production, see `samples/token-broker/`.
- The anomaly model favors recall (precision 0.53). Briefs carry a severity, so analysts start with SEV1.
- Synced tables use SNAPSHOT mode and refresh at the end of each job run. CONTINUOUS mode is the production option.
- The analyst account groups that the masks and row filter reference (`helix_support_analysts`, `helix_wingtip_pod`) are not populated in this workspace, so every caller sees masked values and no isolated-tenant rows.
