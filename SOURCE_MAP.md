# Source map — what to open in the fetched tree

The certification form uploads **local files** and skips binaries (including many `.ipynb` files) plus huge trees like `.venv`. This map is all **text**: `.py`, `.sql`, `.yml`, `.md`, `.log`.

| Required layer | Files (open these) | Proof in this fetch |
|---|---|---|
| **Lakeflow ingest (Zerobus)** | `fluent-bit.yaml`, `sql/create_bronze.sql`, `docs/lakeflow-ingest.md`, `scripts/run_load_test.sh` | `evidence/01_ingest_load_test.log` — 2,879 HTTP 200, 1.64M rows, 0 failures |
| **Lakeflow transform (SDP)** | `resources/fluentbit_otel_etl.pipeline.yml`, `src/fluentbit_otel_etl/transformations/silver_otel_logs.py`, `src/fluentbit_otel_etl/transformations/gold_*.sql` | `evidence/02_pipeline_and_tables.md` — bronze 1,637,120 → silver 1,440,832, 0 expectation failures |
| **Unity Catalog** | `sql/governance_functions.sql`, `sql/governance.sql`, `src/notebooks/01_governance.py` | `evidence/notebooks/01_governance.md` — masks, row filter, 196,288 isolated rows hidden |
| **ML** | `src/notebooks/02_train_anomaly_model.py` | `evidence/notebooks/02_train_anomaly_model.md` — recall 1.0, 130 windows, 3/3 incidents |
| **Gen AI** | `src/notebooks/03_incident_briefs.py` (reads `gold_client_anomalies`, writes briefs **and** `gold_brief_inference`) | `evidence/notebooks/03_incident_briefs.md` — 10 briefs, 10 inference rows |
| **Lakebase serving** | `src/lakebase/sync.py`, `sql/triage_notes.sql`, `src/app/app.py` (`POST /api/notes`) | `evidence/notebooks/04_lakebase_sync.md`, `evidence/04_lakebase_serving.md` — 3 synced tables ONLINE, 2 triage notes |
| **Job** | `resources/support_triage.job.yml` | `evidence/05_job_run.md`, `evidence/05_job_run.log` — SUCCESS 612 s |
| **Genie + App** | `src/genie/space.json`, `src/app/` | `evidence/06_genie_conversation.md`, `evidence/07_app_api.md` |

**If you are uploading this repo in a browser:** select the `submission/` folder (text-only pack), not the parent workspace that contains `.venv` and `.build`.
