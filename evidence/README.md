# Execution evidence

Everything here was produced by running the prototype on the `fevm-ai` workspace (AWS us-east-1, serverless) on 2 November 2026. All data is synthetic. Service-principal IDs and user emails are redacted as `<app-sp>` and `<user>`.

| Stage | Evidence | What it shows |
|---|---|---|
| Ingest (Lakeflow Connect: Zerobus) | [`01_ingest_load_test.log`](01_ingest_load_test.log) | Fluent Bit 5.1.3 → OTLP gRPC → Zerobus. 1,635,120 generated rows (1.8 GB in 600 s), 2,879 HTTP 200 flushes, 0 failures, drain to end of file |
| Transform (Lakeflow SDP) | [`02_pipeline_and_tables.md`](02_pipeline_and_tables.md) | Rows per layer (bronze 1,637,120, silver 1,440,832 visible), 0 expectation failures, top gold error windows, pipeline update history |
| Govern (Unity Catalog) | [`../src/notebooks/01_governance.ipynb`](../src/notebooks/01_governance.ipynb) | Masks and row filter bound to silver, tags, grants, masked read, isolated tenant hidden (196,288 bronze rows vs 0 silver), lineage from `system.access.table_lineage` |
| ML (MLflow + UC registry) | [`../src/notebooks/02_train_anomaly_model.ipynb`](../src/notebooks/02_train_anomaly_model.ipynb), [`03_ml_and_genai.md`](03_ml_and_genai.md) | IsolationForest run, champion v4: precision 0.53, recall 1.0 (each injected incident fully recalled), ROC AUC 0.9999; 130 flagged windows |
| Gen AI (`ai_query`) | [`../src/notebooks/03_incident_briefs.ipynb`](../src/notebooks/03_incident_briefs.ipynb), [`03_ml_and_genai.md`](03_ml_and_genai.md) | 10 structured incident briefs (severity, cause, next step, client reply); both SEV1s match injected incidents |
| Serve (Lakebase) | [`../src/notebooks/04_lakebase_sync.ipynb`](../src/notebooks/04_lakebase_sync.ipynb), [`04_lakebase_serving.md`](04_lakebase_serving.md) | 3 synced tables online; Postgres row counts and queries; `triage_notes` rows written by the app |
| Orchestrate (Lakeflow Jobs) | [`05_job_run.md`](05_job_run.md) | Six-task job run: pipeline → governance → ML → Gen AI → Lakebase sync, all SUCCESS in 612 s |
| Ask (Genie Agent) | [`06_genie_conversation.md`](06_genie_conversation.md) | Five sample questions through the Conversation API, with Genie's SQL, result rows and answer |
| Act (Databricks Apps) | [`07_app_api.md`](07_app_api.md) | Live app calls: health (Lakebase as the app principal), client list and detail, triage-note write and read, Genie via the app |

Scripts that regenerate this folder: `scripts/run_load_test.sh`, `scripts/capture_data_evidence.py`, `scripts/lakebase_grant_and_verify.py`, `scripts/create_genie_space.py --ask` and `scripts/capture_app_evidence.py`.
