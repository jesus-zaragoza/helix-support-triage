# Lakeflow Job evidence: helix_support_triage

Job `1031613634051044`, run `195381314710847`, triggered with `databricks bundle run support_triage -t dev`.

Result: **SUCCESS**, started 2026-11-03 00:55:13 UTC, duration 612 s, serverless compute.

| order | task | depends on | type | result | duration (s) |
|---|---|---|---|---|---|
| 1 | `governance_functions` | - | notebook 01_governance | SUCCESS | 25 |
| 2 | `refresh_pipeline` | governance_functions | pipeline | SUCCESS | 83 |
| 3 | `governance_post` | refresh_pipeline | notebook 01_governance | SUCCESS | 44 |
| 4 | `train_score_anomalies` | refresh_pipeline | notebook 02_train_anomaly_model | SUCCESS | 400 |
| 5 | `incident_briefs` | train_score_anomalies | notebook 03_incident_briefs | SUCCESS | 43 |
| 6 | `lakebase_sync` | incident_briefs, governance_post | notebook 04_lakebase_sync | SUCCESS | 60 |

## CLI output

```
Run URL: https://fevm-serverless-stable-2xts9s.cloud.databricks.com/jobs/1031613634051044/runs/195381314710847?o=7474654402210824

2026-11-02 16:55:13 "[dev jesus_zaragoza] helix_support_triage" RUNNING
2026-11-02 17:05:33 "[dev jesus_zaragoza] helix_support_triage" TERMINATED SUCCESS
Output:
=======
Task governance_functions:

=======
Task governance_post:

=======
Task train_score_anomalies:
{"run_id": "7d730d65bafe45ec9320ef0c8610056b", "model": "accessdemo.dev_jesus_zaragoza_helix_support.client_anomaly_model", "version": 2, "anomalies": 130, "precision": 0.5308, "recall": 1.0, "roc_auc": 0.9999, "average_precision": 0.95, "flagged_windows": 130.0, "training_windows": 26000.0}
=======
Task incident_briefs:

=======
Task lakebase_sync:
```
